import json, time, random, requests, urllib3
from threading import Thread
from http.server import BaseHTTPRequestHandler, HTTPServer

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

try:
    with open("config.json") as f: cfg = json.load(f)
except:
    cfg = {"device_id": "iot-001", "server_url": "https://192.168.8.102:8443", "telemetry_interval": 5}

ID = cfg.get("device_id", "iot-001")
URL = cfg.get("server_url", "https://192.168.8.102:8443")
INT = cfg.get("telemetry_interval", 5)
VER = "1.0.0"

def send_loop():
    session = requests.Session()
    session.verify = False
    print(f"📡 Client {ID} started. Target: {URL}")
    
    while True:
        try:
            is_high_load = "002" in ID
            data = {
                "device_id": ID, "version": VER,
                "cpu": round(random.uniform(86, 99) if is_high_load else random.uniform(20, 60), 1),
                "mem": round(random.uniform(80, 95) if is_high_load else random.uniform(30, 50), 1),
                "temp": round(random.uniform(35, 75), 1), "timestamp": int(time.time())
            }
            resp = session.post(f"{URL}/telemetry", json=data, timeout=5)
            if resp.status_code == 200: print(f"   [Sent] CPU: {data['cpu']}% | Status: OK")
            elif resp.status_code == 403: print(f"❌ Access Denied: Not whitelisted!")
        except: print("❌ Connection Failed")
        time.sleep(INT)

class OTAHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path == "/ota-trigger":
            self.send_response(200); self.end_headers()
            print(f"\n⚡ [OTA] Trigger received! Updating..."); Thread(target=perform_update).start()
    def log_message(self, format, *args): return

def perform_update():
    global VER
    try:
        r = requests.get(f"{URL}/firmware/latest.bin", verify=False, timeout=10)
        if r.status_code == 200:
            time.sleep(2); VER = "2.1.5"; print(f"✅ [OTA] SUCCESS: Updated to v{VER}")
    except: print("❌ Update Failed")

if __name__ == "__main__":
    try:
        httpd = HTTPServer(("", 8000), OTAHandler)
        Thread(target=httpd.serve_forever, daemon=True).start()
        send_loop()
    except: pass