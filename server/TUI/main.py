import requests
import time
import urllib3
from collections import deque
from datetime import timedelta
from rich.console import Console, Group
from rich.live import Live
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.align import Align

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ---------------- KEY LISTENER ----------------
try:
    import msvcrt
    def get_key():
        if msvcrt.kbhit():
            ch = msvcrt.getch()
            if ch in (b'\x00', b'\xe0'): msvcrt.getch(); return None
            try: return ch.decode('utf-8').lower()
            except UnicodeDecodeError: return None
        return None
except ImportError:
    def get_key(): return None

# ---------------- CONFIG ----------------
SERVER_URL   = "https://192.168.8.102:8443"
REFRESH_RATE = 0.5
HISTORY_LEN  = 60

console = Console()
session = requests.Session()
session.verify = False

# ---------------- STATE ----------------
current_view        = '1'
selected_device_idx = 0
device_history      = {}

def g(d, key, default=0):
    """Safe getter — returns default if key missing or None."""
    if not isinstance(d, dict): return default
    v = d.get(key)
    return v if v is not None else default

def gf(d, key, default=0.0) -> float:
    """Safe float getter — never crashes :.1f format strings."""
    try:    return float(g(d, key, default))
    except: return float(default)

def gi(d, key, default=0) -> int:
    """Safe int getter."""
    try:    return int(g(d, key, default))
    except: return int(default)

def gs(d, key, default='') -> str:
    """Safe string getter."""
    try:    return str(g(d, key, default))
    except: return str(default)

# ---------------- FETCH ----------------
def fetch_data():
    devices, stats = {}, {"anomalies": 0, "log": []}
    try:
        r = session.get(f"{SERVER_URL}/api/devices", timeout=3)
        if r.status_code == 200 and r.content:
            devices = r.json()
    except Exception: pass
    try:
        r = session.get(f"{SERVER_URL}/api/stats", timeout=3)
        if r.status_code == 200 and r.content:
            stats = r.json()
    except Exception: pass
    return devices, stats

# ---------------- HISTORY ----------------
def update_history(devices):
    for d_id, data in devices.items():
        if d_id not in device_history:
            device_history[d_id] = {
                k: deque([0] * HISTORY_LEN, maxlen=HISTORY_LEN)
                for k in ('cpu', 'mem', 'temp', 'battery', 'latency_ms')
            }
        for k in ('cpu', 'mem', 'temp', 'battery', 'latency_ms'):
            device_history[d_id][k].append(g(data, k))

# ---------------- UTILS ----------------
def format_uptime(sec):
    if not sec: return "-"
    try: return str(timedelta(seconds=int(sec))).split('.')[0]
    except: return "-"

def make_sparkline(data, height=4, color="green", max_val=100.0):
    if not data: return ""
    levels = [" ", "▂", "▃", "▄", "▅", "▆", "▇", "█"]
    lines  = [""] * height
    for val in data:
        norm        = (val / max_val) * (height * 8)
        full_blocks = int(norm // 8)
        remainder   = int(norm % 8)
        for i in range(height):
            idx = height - 1 - i
            if   idx < full_blocks:  lines[i] += levels[7]
            elif idx == full_blocks: lines[i] += levels[remainder]
            else:                    lines[i] += " "
    return "\n".join(f"[{color}]{l}[/{color}]" for l in lines)

def battery_bar(pct):
    filled = min(10, max(0, round(pct / 10)))
    bar    = "█" * filled + "░" * (10 - filled)
    color  = "color(196)" if pct < 20 else "color(214)" if pct < 40 else "color(46)"
    return f"[{color}]{bar}[/] {pct:.0f}%"

def signal_color(rssi):
    if rssi >= -50: return "color(46)"
    if rssi >= -60: return "color(82)"
    if rssi >= -70: return "color(214)"
    return "color(196)"

# ---------------- VIEW 1 — OVERVIEW ----------------
def render_overview(devices, height=None):
    table = Table(expand=True, box=None, header_style="bold color(39)")
    table.add_column("Device",          min_width=16)
    table.add_column("Status",          min_width=18)
    table.add_column("Version",         min_width=8)
    table.add_column("CPU %",  justify="right", min_width=6)
    table.add_column("Mem %",  justify="right", min_width=6)
    table.add_column("Temp",   justify="right", min_width=7)
    table.add_column("Battery",          min_width=16)
    table.add_column("Storage %", justify="right", min_width=9)
    table.add_column("Latency",  justify="right", min_width=8)
    table.add_column("Errors",   justify="right", min_width=7)
    table.add_column("Uptime",           min_width=10)
    table.add_column("Signal",           min_width=10)

    if not devices:
        return Panel(Align.center("[yellow]No devices connected.[/]"),
                     title="[1] Network Summary", height=height)

    for d_id, data in devices.items():
        status    = gs(data, 'status', 'Unknown')
        is_update = "UPDATING" in str(status)
        is_anom   = "ANOMALY"  in str(status)

        st = Text()
        if   is_update: st.append("⟳ " + status, style="bold color(226)")
        elif is_anom:   st.append("⚠ " + status, style="bold color(196)")
        else:           st.append("● " + status, style="color(46)")

        cpu     = gf(data, 'cpu')
        mem     = gf(data, 'mem')
        temp    = gf(data, 'temp')
        bat     = gf(data, 'battery', 100)
        storage = gf(data, 'storage')
        lat     = gf(data, 'latency_ms')
        errs    = gi(data, 'error_count')
        uptime  = gi(data, 'uptime_sec')
        rssi    = gi(data, 'rssi')
        ver     = gs(data, 'version', '-')

        cpu_st  = "color(196)" if cpu  > 85  else "color(46)"
        mem_st  = "color(196)" if mem  > 90  else "color(46)"
        lat_st  = "color(196)" if lat  > 2000 else "color(46)"
        err_st  = "color(196)" if errs > 0   else "color(46)"
        sto_st  = "color(196)" if storage > 80 else "color(46)"

        table.add_row(
            d_id,
            st,
            f"v{ver}",
            f"[{cpu_st}]{cpu:.1f}%[/]",
            f"[{mem_st}]{mem:.1f}%[/]",
            f"{temp:.1f}°C",
            battery_bar(bat),
            f"[{sto_st}]{storage:.1f}%[/]",
            f"[{lat_st}]{lat:.0f}ms[/]",
            f"[{err_st}]{errs}[/]",
            format_uptime(uptime),
            f"[{signal_color(rssi)}]{rssi}dBm[/]",
        )

    return Panel(table, title="[1] Network Summary",
                 border_style="color(39)", height=height)

# ---------------- VIEW 2 — LIVE GRAPHS ----------------
def render_graphs(devices, height=None):
    if not devices:
        return Panel("No devices.", title="[2] Live Graphs", height=height)

    global selected_device_idx
    ids = list(devices.keys())
    if selected_device_idx >= len(ids): selected_device_idx = 0
    d_id = ids[selected_device_idx]
    data = devices[d_id]
    hist = device_history.get(d_id, {k: [] for k in
           ('cpu','mem','temp','battery','latency_ms')})

    gh = max(3, ((height or 28) - 12) // 2)

    top = Table.grid(expand=True)
    top.add_column(ratio=1); top.add_column(ratio=1); top.add_column(ratio=1)
    top.add_row(
        Panel(make_sparkline(hist['cpu'],  gh, "color(33)"),
              title=f"CPU  {gf(data,'cpu'):.1f}%",     border_style="color(33)"),
        Panel(make_sparkline(hist['mem'],  gh, "color(207)"),
              title=f"Mem  {gf(data,'mem'):.1f}%",     border_style="color(207)"),
        Panel(make_sparkline(hist['temp'], gh, "color(214)"),
              title=f"Temp {gf(data,'temp'):.1f}°C",   border_style="color(214)"),
    )

    bot = Table.grid(expand=True)
    bot.add_column(ratio=1); bot.add_column(ratio=1)
    bot.add_row(
        Panel(make_sparkline(hist['battery'],   gh, "color(46)",  max_val=100),
              title=f"Battery  {gf(data,'battery',100):.0f}%  {gs(data,'battery_status')}",
              border_style="color(46)"),
        Panel(make_sparkline(hist['latency_ms'],gh, "color(39)",  max_val=3000),
              title=f"Latency  {gf(data,'latency_ms'):.0f}ms",
              border_style="color(39)"),
    )

    info = (f"[bold]{d_id}[/]  |  "
            f"IP:[color(39)]{gs(data,'ip','-')}[/]  |  "
            f"v[color(46)]{gs(data,'version','-')}[/]  |  "
            f"Storage:[color(214)]{gf(data,'storage'):.1f}%[/]  |  "
            f"Errors:[color(196)]{gi(data,'error_count')}[/]  |  "
            f"Uptime:{format_uptime(gi(data,'uptime_sec'))}  |  "
            f"[dim]d=switch device[/]")

    return Panel(
        Group(top, bot, Align.center(info)),
        title=f"[2] Live Performance — {d_id} ({selected_device_idx+1}/{len(ids)})",
        border_style="color(46)", height=height,
    )

# ---------------- VIEW 3 — SECURITY & OTA LOGS ----------------
def render_security(stats, height=None):
    logs  = stats.get('log', [])
    table = Table(expand=True, show_header=False)
    table.add_column("Log")
    if not logs:
        table.add_row("[dim]No events recorded.[/dim]")
    else:
        for entry in reversed(logs[-(max(1,(height or 20)-4)):]):
            if   "BLOCKED"  in entry: style = "bold color(196)"
            elif "CRITICAL" in entry: style = "bold color(196)"
            elif "ALERT"    in entry: style = "color(208)"
            elif "SPIKE"    in entry: style = "color(208)"
            elif "LATENCY"  in entry: style = "color(208)"
            elif "FAILED"   in entry: style = "color(196)"
            elif "SUCCESS"  in entry: style = "color(46)"
            elif "OTA"      in entry: style = "color(39)"
            elif "ONLINE"   in entry: style = "color(46)"
            elif "RECOVERY" in entry: style = "color(46)"
            else:                     style = "dim"
            table.add_row(f"[{style}]{entry}[/]")
    return Panel(table, title="[3] Security & OTA Logs",
                 border_style="color(196)", height=height)

# ---------------- VIEW 4 — RAW JSON ----------------
def render_raw(devices, height=None):
    import json
    if not devices:
        return Panel("No Data", title="[4] Raw JSON Debug", height=height)
    return Panel(json.dumps(devices, indent=2, default=str),
                 title="[4] Raw JSON Debug",
                 border_style="color(226)", height=height)

# ---------------- LAYOUT ----------------
def make_layout():
    layout = Layout()
    layout.split(Layout(name="header", size=3), Layout(name="body"))
    return layout

def update_layout(layout, devices, stats, view_mode):
    body_height = console.size.height - 3
    ht = Table.grid(expand=True)
    ht.add_column(justify="left"); ht.add_column(justify="right")
    ht.add_row(
        (f"[bold white]IOTFW SECURE DASHBOARD[/]  |  "
         f"Devices:[color(39)]{len(devices)}[/]  |  "
         f"Anomalies:[color(196)]{stats.get('anomalies',0)}[/]"),
        "[dim]1=Overview  2=Graphs  3=Logs  4=Raw  d=Switch  q=Quit[/]",
    )
    layout["header"].update(Panel(ht, style="white on color(235)"))

    if   view_mode == '1': layout["body"].update(render_overview(devices, body_height))
    elif view_mode == '2': layout["body"].update(render_graphs(devices,   body_height))
    elif view_mode == '3': layout["body"].update(render_security(stats,   body_height))
    elif view_mode == '4': layout["body"].update(render_raw(devices,      body_height))

# ---------------- MAIN ----------------
def handle_key(key) -> bool:
    """Process a keypress. Returns True if quit requested."""
    global current_view, selected_device_idx  # valid here — inside a function
    if   key in ['1','2','3','4']: current_view = key
    elif key == 'd':               selected_device_idx += 1
    elif key == 'q':               return True
    return False

def run():
    console.clear()
    layout = make_layout()
    try:
        with Live(layout, refresh_per_second=4, screen=True):
            while True:
                if handle_key(get_key()):
                    break
                devices, stats = fetch_data()
                if devices: update_history(devices)
                update_layout(layout, devices, stats, current_view)
                time.sleep(REFRESH_RATE)
    except KeyboardInterrupt:
        console.print("[bold red]Dashboard stopped.[/]")

if __name__ == "__main__":
    run()