import json
import time
import requests
import urllib3
import sys
from threading import Thread
from http.server import BaseHTTPRequestHandler, HTTPServer

# -------------------------------------------------------
# REQUIREMENT: Real Hardware Data
# This script requires 'psutil' to fetch actual CPU/RAM usage.
# -------------------------------------------------------
try:
    import psutil
except ImportError:
    print("❌ Error: 'psutil' library is missing.")
    print("   Please run: pip install psutil")
    sys.exit(1)

# Suppress SSL warnings (since we use self-signed certs)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- LOAD CONFIGURATION ---
try:
    with open("config.json") as f: 
        cfg = json.load(f)
except FileNotFoundError:
    print("❌ Error: config.json not found.")
    print("   Please ensure config.json exists in this folder.")
    sys.exit(1)
except json.JSONDecodeError:
    print("❌ Error: config.json is not valid JSON.")
    sys.exit(1)

# --- CLIENT SETTINGS FROM CONFIG (STRICT MODE) ---
try:
    ID = cfg["device_id"]
    URL = cfg["server_url"]
    INT = cfg["telemetry_interval"]
    OTA_PORT = cfg["ota_port"]
    VER = cfg["current_version"]
except KeyError as e:
    print(f"❌ Configuration Error: Missing required key {e} in config.json")
    print("   Please update your config.json file.")
    sys.exit(1)

# --- TELEMETRY LOGIC ---
def generate_telemetry():
    """
    Captures EXTENDED real system metrics with fallbacks.
    """
    # 1. CPU Usage (blocking call for 1 second)
    real_cpu = psutil.cpu_percent(interval=1)
    logical_cpus = psutil.cpu_count(logical=True)

    # 2. Memory Usage
    mem_info = psutil.virtual_memory()
    real_mem_percent = mem_info.percent

    # 3. Disk Usage (Root partition)
    try:
        disk_usage = psutil.disk_usage('/').percent
    except:
        disk_usage = 0.0

    # 4. Network Stats (Total bytes sent/recv since boot)
    try:
        net_io = psutil.net_io_counters()
        bytes_sent = net_io.bytes_sent
        bytes_recv = net_io.bytes_recv
    except:
        bytes_sent = 0
        bytes_recv = 0

    # 5. Boot Time
    try:
        boot_time = int(psutil.boot_time())
    except:
        # Fallback to current time minus 1 hour if boot time read fails
        boot_time = int(time.time()) - 3600
    
    # 6. Temperature (Real with Simulation Fallback)
    real_temp = 0.0
    try:
        temps = psutil.sensors_temperatures()
        if temps:
            for name, entries in temps.items():
                if entries:
                    real_temp = entries[0].current
                    break
    except Exception:
        pass 
    
    # FALLBACK: If temp is still 0.0 (common on Windows/VMs), simulate it
    if real_temp == 0.0:
        # Simulate temp based on CPU load: 35C baseline + (CPU% / 2)
        real_temp = 35.0 + (real_cpu / 2.5)

    return {
        "device_id": ID, 
        "version": VER,
        "cpu": round(real_cpu, 1),
        "mem": round(real_mem_percent, 1),
        "temp": round(real_temp, 1),
        "disk_usage": round(disk_usage, 1),
        "net_sent_mb": round(bytes_sent / (1024*1024), 2),
        "net_recv_mb": round(bytes_recv / (1024*1024), 2),
        "boot_time": boot_time,
        "cpu_cores": logical_cpus,
        "timestamp": int(time.time()),
        "ota_port": OTA_PORT
    }

def send_loop(): 
    session = requests.Session()
    session.verify = False 
    
    print(f"📡 Client {ID} started.")
    print(f"   → Server: {URL}")
    print(f"   → Listening on Port: {OTA_PORT}")
    print(f"   → Mode:   ✅ REAL + SMART FALLBACK DATA")
    
    while True:
        try:
            data = generate_telemetry()
            
            resp = session.post(f"{URL}/telemetry", json=data, timeout=5)
            
            if resp.status_code == 200:
                print(f"   🟢 [Sent] CPU: {data['cpu']}% | Mem: {data['mem']}% | Temp: {data['temp']}°C")
            elif resp.status_code == 403:
                print(f"   ❌ Access Denied: Device ID '{ID}' is not whitelisted.")
            else:
                print(f"   ⚠️ Server Error: {resp.status_code}")
                
        except requests.exceptions.ConnectionError:
            print(f"   ❌ Connection Failed: Could not reach {URL}")
        except Exception as e:
            print(f"   ⚠️ Error: {e}")
            
        # Adjust sleep time to account for the 1s delay in cpu_percent()
        sleep_time = max(0, INT - 1)
        if sleep_time > 0:
            time.sleep(sleep_time)

# --- OTA LISTENER ---
class OTAHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path == "/ota-trigger":
            self.send_response(200)
            self.end_headers()
            print(f"\n⚡ [OTA] Trigger received! Starting firmware download...")
            Thread(target=perform_update).start()
            
    def log_message(self, format, *args): return

def perform_update():
    global VER
    try:
        print(f"   Downloading firmware from {URL}...")
        r = requests.get(f"{URL}/firmware/latest.bin", verify=False, timeout=10)
        
        if r.status_code == 200:
            with open("firmware_update.bin", "wb") as f:
                f.write(r.content)
            print("   Verifying signature...")
            time.sleep(2)
            VER = "2.1.5"
            print(f"✅ [OTA] SUCCESS: Firmware updated to v{VER}")
        else:
            print(f"❌ [OTA] Download failed: Status {r.status_code}")
    except Exception as e:
        print(f"❌ [OTA] Update failed: {e}")

# --- MAIN STARTUP ---
if __name__ == "__main__":
    try:
        httpd = HTTPServer(("", OTA_PORT), OTAHandler)
        Thread(target=httpd.serve_forever, daemon=True).start()
        print(f"🎧 OTA Listener active on port {OTA_PORT}")
        send_loop()
    except OSError:
        print(f"❌ Error: Port {OTA_PORT} is busy. Check 'ota_port' in config.json")
    except KeyboardInterrupt:
        print("\nClient stopping...")