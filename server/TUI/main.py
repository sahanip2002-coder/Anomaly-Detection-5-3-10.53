import requests
import time
import urllib3
import sys
import os
from datetime import datetime, timedelta
from collections import deque
from rich.console import Console, Group
from rich.live import Live
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.align import Align
from rich.ansi import AnsiDecoder
from rich.style import Style

# --- 1. ROBUST KEY LISTENER ---
try:
    import msvcrt
    def get_key():
        if msvcrt.kbhit():
            ch = msvcrt.getch()
            if ch in (b'\x00', b'\xe0'):
                msvcrt.getch()
                return None
            try:
                return ch.decode('utf-8').lower()
            except UnicodeDecodeError:
                return None
        return None
except ImportError:
    def get_key(): return None

# Suppress SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

console = Console()

# --- 2. CONFIGURATION ---
SERVER_URL = "https://127.0.0.1:8443"
REFRESH_RATE = 0.5
HISTORY_LEN = 60

session = requests.Session()
session.verify = False

# --- 3. STATE MANAGEMENT ---
current_view = '1'
selected_device_idx = 0
device_history = {}

# --- 4. DATA FETCHING ---
def fetch_data():
    try:
        resp_dev = session.get(f"{SERVER_URL}/api/devices", timeout=1)
        devices = resp_dev.json() if resp_dev.status_code == 200 else {}
        resp_stat = session.get(f"{SERVER_URL}/api/stats", timeout=1)
        stats = resp_stat.json() if resp_stat.status_code == 200 else {"anomalies": 0, "log": []}
        return devices, stats
    except:
        return None, None

def update_history(devices):
    for d_id, data in devices.items():
        if d_id not in device_history:
            device_history[d_id] = {
                'cpu': deque([0]*HISTORY_LEN, maxlen=HISTORY_LEN),
                'mem': deque([0]*HISTORY_LEN, maxlen=HISTORY_LEN),
                'temp': deque([0]*HISTORY_LEN, maxlen=HISTORY_LEN)
            }
        device_history[d_id]['cpu'].append(data.get('cpu', 0))
        device_history[d_id]['mem'].append(data.get('mem', 0))
        device_history[d_id]['temp'].append(data.get('temp', 0))

def format_uptime(boot_time):
    if not boot_time: return "-"
    try:
        uptime_seconds = int(time.time()) - int(boot_time)
        return str(timedelta(seconds=uptime_seconds)).split('.')[0]
    except: return "-"

def make_sparkline(data, height=5, color="green"):
    if not data: return ""
    max_val = 100.0
    levels = [" ", "▂", "▃", "▄", "▅", "▆", "▇", "█"]
    lines = [""] * height
    for val in data:
        normalized = (val / max_val) * (height * 8)
        full_blocks = int(normalized // 8)
        remainder = int(normalized % 8)
        for i in range(height):
            idx = height - 1 - i
            if idx < full_blocks: lines[i] += levels[7]
            elif idx == full_blocks: lines[i] += levels[remainder]
            else: lines[i] += " "
    graph_str = ""
    for line in lines:
        graph_str += f"[{color}]{line}[/]\n"
    return graph_str.rstrip()

# --- VIEW 1: NETWORK SUMMARY ---
def render_overview(devices, height=None):
    # Using color(39) for a tech-blue header
    table = Table(expand=True, box=None, header_style="bold color(39)")
    table.add_column("Device ID", style="white")
    table.add_column("IP:Port", style="dim")
    table.add_column("Status", justify="center")
    table.add_column("Ver", justify="center")
    table.add_column("CPU", justify="right")
    table.add_column("Mem", justify="right")
    table.add_column("Disk", justify="right")
    table.add_column("Temp", justify="right")
    table.add_column("Uptime", justify="right", style="color(39)")

    if not devices: 
        return Panel("No devices connected.", title="[1] Network Summary", border_style="color(240)", height=height)

    for d_id, data in devices.items():
        status = data.get('status', 'Unknown')
        port = data.get('ota_port', '8000')
        
        # Status Styling
        if "ANOMALY" in status: 
            status_render = Text("⚠️ CRITICAL", style="bold color(196)") # Bright Red
        else: 
            status_render = Text("● Stable", style="color(46)") # Neon Green
        
        cpu = data.get('cpu', 0)
        mem = data.get('mem', 0)
        disk = data.get('disk_usage', 0)
        temp = data.get('temp', 0)
        boot = data.get('boot_time', 0)

        # Metric Color Thresholds
        cpu_st = "color(196)" if cpu > 85 else "color(46)"
        mem_st = "color(196)" if mem > 90 else "color(46)"
        disk_st = "color(196)" if disk > 90 else "color(46)"
        
        table.add_row(
            d_id, f"{data.get('ip')}:{port}", status_render, data.get('version'),
            f"[{cpu_st}]{cpu}%[/]", f"[{mem_st}]{mem}%[/]", f"[{disk_st}]{disk}%[/]",
            f"{temp}°C", format_uptime(boot)
        )
    
    return Panel(table, title="[1] Network Summary", border_style="color(39)", height=height)

# --- VIEW 2: LIVE GRAPHS ---
def render_graphs(devices, height=None):
    if not devices: 
        return Panel("No devices.", title="[2] Real-Time Graphs", height=height)
    
    device_ids = list(devices.keys())
    global selected_device_idx
    if selected_device_idx >= len(device_ids): selected_device_idx = 0
    current_id = device_ids[selected_device_idx]
    data = devices[current_id]
    
    hist = device_history.get(current_id, {'cpu':[], 'mem':[], 'temp':[]})
    
    available_h = (height or 20) - 4
    graph_h = max(3, int(available_h / 3))

    grid = Table.grid(expand=True, padding=1)
    grid.add_column(ratio=1)
    grid.add_column(ratio=1)
    grid.add_column(ratio=1)
    
    # New Colors: Dodger Blue, Hot Pink, Orange
    cpu_graph = make_sparkline(hist['cpu'], height=graph_h, color="color(33)")
    mem_graph = make_sparkline(hist['mem'], height=graph_h, color="color(207)")
    temp_graph = make_sparkline(hist['temp'], height=graph_h, color="color(214)")
    
    p_cpu = Panel(cpu_graph, title=f"CPU Load ({data.get('cpu')}%)", border_style="color(33)")
    p_mem = Panel(mem_graph, title=f"Memory ({data.get('mem')}%)", border_style="color(207)")
    p_temp = Panel(temp_graph, title=f"Temp ({data.get('temp')}°C)", border_style="color(214)")
    
    grid.add_row(p_cpu, p_mem, p_temp)
    
    info = f"[bold]{current_id}[/] | IP: {data.get('ip')}:{data.get('ota_port')} | Uptime: {format_uptime(data.get('boot_time'))} | Disk: {data.get('disk_usage')}%"
    
    return Panel(
        Group(
            Align.center(f"▼ Monitoring: [bold white on color(33)] {current_id} [/] (Press 'd' to switch device)"),
            grid,
            Align.center(info)
        ), 
        title="[2] Live Performance Telemetry", 
        border_style="color(46)",
        height=height 
    )

# --- VIEW 3: SECURITY LOGS ---
def render_security(stats, height=None):
    logs = stats.get('log', [])
    log_table = Table(expand=True, box=None, show_header=False)
    log_table.add_column("Log")
    
    if not logs: log_table.add_row("[dim]No events recorded.[/dim]")
    else:
        max_lines = (height or 20) - 2
        for entry in reversed(logs[-max_lines:]): 
            style = "dim"
            if "BLOCKED" in entry: style = "bold color(196)"
            elif "ALERT" in entry: style = "color(208)" # Orange Red
            elif "SUCCESS" in entry: style = "color(46)"
            log_table.add_row(f"[{style}]{entry}[/]")
            
    return Panel(log_table, title="[3] Security Logs", border_style="color(196)", height=height)

# --- VIEW 4: RAW JSON ---
def render_raw(devices, height=None):
    import json
    if not devices: return Panel("No Data", title="[4] Raw", height=height)
    subset = {k: devices[k] for k in list(devices)[:3]} 
    return Panel(json.dumps(subset, indent=2), title="[4] Raw JSON Debug", border_style="color(226)", height=height)

# --- 5. MAIN COMPOSITOR ---
def make_layout():
    layout = Layout()
    layout.split(Layout(name="header", size=3), Layout(name="body"))
    return layout

def update_layout(layout, devices, stats, view_mode):
    anomalies = stats.get('anomalies', 0)
    term_height = console.size.height
    body_height = term_height - 3 

    header_text = Table.grid(expand=True)
    header_text.add_column(justify="left")
    header_text.add_column(justify="right")
    # Header: Dark Grey Background (235) with White text
    header_text.add_row(
        f"[bold white]IOTFW SECURE DASHBOARD v3.1[/] | Connected: [color(39)]{len(devices)}[/] | Anomalies: [color(196)]{anomalies}[/]",
        f"[dim]Views: 1-4 | Device Select: 'd' | Quit: 'q' | Current: {view_mode}[/]"
    )
    layout["header"].update(Panel(header_text, style="white on color(235)"))
    
    if view_mode == '1': layout["body"].update(render_overview(devices, height=body_height))
    elif view_mode == '2': layout["body"].update(render_graphs(devices, height=body_height))
    elif view_mode == '3': layout["body"].update(render_security(stats, height=body_height))
    elif view_mode == '4': layout["body"].update(render_raw(devices, height=body_height))

if __name__ == "__main__":
    console.clear()
    layout = make_layout()
    console.print("[bold yellow]Connecting to Secure Server...[/]")
    
    try:
        with Live(layout, refresh_per_second=4, screen=True) as live:
            while True:
                key = get_key()
                if key in ['1', '2', '3', '4']: current_view = key
                elif key == 'd': selected_device_idx += 1
                elif key == 'q': break
                
                devices, stats = fetch_data()
                
                if devices:
                    update_history(devices)
                    update_layout(layout, devices, stats, current_view)
                else:
                    err = Panel(Align.center(f"[bold red]CONNECTION LOST[/]\n\nChecking {SERVER_URL}..."), title="Error", border_style="red")
                    layout["body"].update(err)
                
                time.sleep(REFRESH_RATE)
    except KeyboardInterrupt:
        console.print("[bold red]Dashboard Stopped[/]")