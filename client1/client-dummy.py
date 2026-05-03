import json
import time
import random
import requests
import urllib3
from threading import Thread
from http.server import BaseHTTPRequestHandler, HTTPServer

# Suppress SSL warnings (since we use self-signed certs for simulation)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- LOAD CONFIGURATION ---
try:
    with open("config.json") as f: 
        cfg = json.load(f)
except FileNotFoundError:
    print("❌ Error: config.json not found.")
    print("   Please ensure config.json exists in this folder.")
    exit(1)

# --- CLIENT SETTINGS ---
ID = cfg.get("device_id", "iot-unknown")
URL = cfg.get("server_url", "https://127.0.0.1:8443") 
INT = cfg.get("telemetry_interval", 5)
OTA_PORT = cfg.get("ota_port", 8000)  # Critical: Reads specific port from config
VER = cfg.get("current_version", "1.0.0")

# --- TELEMETRY LOGIC ---
def generate_telemetry():
    # SIMULATION LOGIC:
    # If this device is 'iot-002', we intentionally generate HIGH CPU/MEM
    # to trigger the Anomaly Detection Engine on the server.
    is_high_load = "002" in ID 
    
    return {
        "device_id": ID, 
        "version": VER,
        # Simulating High Load vs Normal Load
        "cpu": round(random.uniform(86, 99) if is_high_load else random.uniform(20, 60), 1),
        "mem": round(random.uniform(80, 95) if is_high_load else random.uniform(30, 50), 1),
        "temp": round(random.uniform(35, 75), 1),
        "timestamp": int(time.time()),
        "ota_port": OTA_PORT  # We tell the server which port to call us back on
    }

def send_loop(): 
    session = requests.Session()
    session.verify = False # Allow self-signed certs
    
    print(f"📡 Client {ID} started.")
    print(f"   → Target Server: {URL}")
    print(f"   → Telemetry Interval: {INT}s")
    
    while True:
        try:
            data = generate_telemetry()
            
            # POST data to server
            resp = session.post(f"{URL}/telemetry", json=data, timeout=5)
            
            if resp.status_code == 200:
                status_icon = "🔴" if "002" in ID else "🟢"
                print(f"   {status_icon} [Sent] CPU: {data['cpu']}% | Mem: {data['mem']}% | Status: OK")
            elif resp.status_code == 403:
                print(f"❌ Access Denied: Device {ID} is not in the server whitelist!")
            else:
                print(f"⚠️ Server returned error: {resp.status_code}")
                
        except requests.exceptions.ConnectionError:
            print(f"❌ Connection Failed: Could not reach {URL}")
        except Exception as e:
            print(f"⚠️ Error: {e}")
            
        time.sleep(INT)

# --- OTA LISTENER (Receives Updates from Server) ---
class OTAHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path == "/ota-trigger":
            self.send_response(200)
            self.end_headers()
            print(f"\n⚡ [OTA] Trigger received! Starting firmware download...")
            # Run update in a separate thread so we don't block the response
            Thread(target=perform_update).start()
            
    def log_message(self, format, *args):
        return # Suppress noisy HTTP logs

def perform_update():
    global VER
    try:
        print(f"   Downloading firmware from {URL}...")
        r = requests.get(f"{URL}/firmware/latest.bin", verify=False, timeout=10)
        
        if r.status_code == 200:
            # Simulate saving binary file
            with open("firmware_update.bin", "wb") as f:
                f.write(r.content)
            
            print("   Verifying signature...")
            time.sleep(2) # Simulate installation time
            
            VER = "2.1.5" # Update the version in memory
            print(f"✅ [OTA] SUCCESS: Firmware updated to v{VER}")
        else:
            print(f"❌ [OTA] Download failed: Status {r.status_code}")
            
    except Exception as e:
        print(f"❌ [OTA] Update failed: {e}")

# --- MAIN STARTUP ---
if __name__ == "__main__":
    # 1. Start OTA Listener on the port defined in config.json
    try:
        httpd = HTTPServer(("", OTA_PORT), OTAHandler)
        Thread(target=httpd.serve_forever, daemon=True).start()
        print(f"🎧 OTA Listener active on port {OTA_PORT}")
    except OSError:
        print(f"❌ Error: Port {OTA_PORT} is busy. Are you running two clients with the same config?")
        exit(1)

    # 2. Start Sending Telemetry
    try:
        send_loop()
    except KeyboardInterrupt:
        print("\nClient stopping...")