# server/app/services.py
import requests
from app.state import devices, ota_log, increment_anomaly
from app.utils import load_json
from datetime import datetime

# --- TELEMETRY ENGINE ---
def check_telemetry_health(data):
    cfg = load_json("thresholds.json", {"global": {}}).get("global", {})
    cpu_th = cfg.get("cpu_threshold", 85.0)
    mem_th = cfg.get("mem_threshold", 90.0)

    is_anomaly = data.cpu > cpu_th or data.mem > mem_th
    status = "ANOMALY (High Load)" if is_anomaly else "Stable"

    # ✅ Detect version change — means OTA reboot succeeded
    prev         = devices.get(data.device_id, {})
    prev_version = prev.get("version", "")
    if prev_version and prev_version != data.version:
        msg = (f"🎉 OTA SUCCESS → {data.device_id} upgraded "
               f"v{prev_version} → v{data.version}")
        ota_log.append(msg)
        print(msg)

    # Update device in memory
    devices[data.device_id] = {
        "status":                    status,
        "cpu":                       data.cpu,
        "mem":                       data.mem,
        "temp":                      getattr(data, "temp",       0),
        "disk_usage":                getattr(data, "disk_usage", 0),
        "version":                   getattr(data, "version",    ""),
        "ip":                        getattr(data, "device_ip",  ""),
        "boot_time":                 getattr(data, "boot_time",  int(datetime.now().timestamp())),
        "ota_port":                  getattr(data, "ota_port",   8000),
        "firmware_update_available": False,
    }

    if is_anomaly:
        increment_anomaly()
        return status, False
    return status, True

# --- LOGGING ---
def log_security_events(device_id, is_anomaly, cpu_val):
    prev_status = devices.get(device_id, {}).get("status", "Unknown")

    if is_anomaly and "ANOMALY" not in prev_status:
        ota_log.append(f"⚠️ ALERT → {device_id} entered ANOMALY state (CPU:{cpu_val}%)")
    elif not is_anomaly and "ANOMALY" in prev_status:
        ota_log.append(f"✅ RECOVERY → {device_id} returned to Stable state")

# --- OTA SERVICE ---
async def trigger_device_update(device_id, ip_address):
    try:
        requests.post(f"http://{ip_address}:8000/ota-trigger", timeout=5)
        ota_log.append(f"⚡ OTA TRIGGER sent → {device_id} @ {ip_address}")
    except Exception:
        ota_log.append(f"⚠️ FAILED → Cannot reach {device_id} @ {ip_address}")