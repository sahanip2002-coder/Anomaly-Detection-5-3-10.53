import requests
from app.state import devices, ota_log, increment_anomaly, save_state
from app.utils import load_json

# --- ANOMALY ENGINE ---
def check_telemetry_health(data):
    cfg = load_json("thresholds.json", {"global": {}}).get("global", {})
    cpu_th = cfg.get("cpu_threshold", 85.0)
    mem_th = cfg.get("mem_threshold", 90.0)

    if data.cpu > cpu_th or data.mem > mem_th:
        increment_anomaly()
        return "ANOMALY (High Load)", False
    
    return "Stable", True

def log_security_events(device_id, is_anomaly, cpu_val):
    prev_device = devices.get(device_id, {})
    prev_status = prev_device.get("status", "Unknown")

    if is_anomaly and "ANOMALY" not in prev_status:
        ota_log.append(f"⚠️ ALERT → {device_id} entered ANOMALY state (CPU:{cpu_val}%)")
        save_state()
    elif not is_anomaly and "ANOMALY" in prev_status:
        ota_log.append(f"ea RECOVERY → {device_id} returned to Stable state")
        save_state()

# --- OTA SERVICE WITH VALIDATION ---
async def trigger_device_update(device_id, ip_address):
    """
    Triggers OTA update with Version Validation.
    """
    # 1. Load Target Version from Config
    ota_settings = load_json("ota_settings.json", {"target_firmware_version": "2.1.5"})
    target_ver = ota_settings.get("target_firmware_version", "2.1.5")

    # 2. Get Device Current Version
    device_info = devices.get(device_id, {})
    current_ver = device_info.get("version", "0.0.0")
    target_port = device_info.get("ota_port", 8000)

    print(f"🔍 Validating {device_id}: Current={current_ver} -> Target={target_ver}")

    # 3. VALIDATION LOGIC
    if current_ver == target_ver:
        msg = f"🛑 SKIPPED → {device_id} is already on v{target_ver}"
        ota_log.append(msg)
        print(msg)
        save_state()
        return # Stop execution
    
    # Optional: Prevent Downgrades (Simple string comparison, ideally use semantic versioning lib)
    if current_ver > target_ver:
        msg = f"🛑 BLOCKED → Downgrade attack prevention. {device_id} (v{current_ver}) > Target (v{target_ver})"
        ota_log.append(msg)
        print(msg)
        save_state()
        return

    # 4. Proceed if Valid
    print(f"🚀 Validation Passed. Triggering OTA for {device_id}...")
    
    try:
        url = f"http://{ip_address}:{target_port}/ota-trigger"
        # We send the target version in the request so client knows what to expect
        requests.post(url, json={"target_version": target_ver}, timeout=5)
        ota_log.append(f"✅ SUCCESS → {device_id} updated to v{target_ver}")
    except Exception as e:
        ota_log.append(f"⚠️ FAILED → Connection error with {device_id}: {e}")
    
    save_state()