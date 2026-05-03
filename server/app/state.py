import json
from pathlib import Path

# Define storage file path relative to this file
# app/state.py -> parent=app -> parent=server -> data_store.json
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_STORE = BASE_DIR / "data_store.json"

# In-memory storage
devices = {}
ota_log = []
anomaly_count = 0

def increment_anomaly():
    global anomaly_count
    anomaly_count += 1
    save_state()

def save_state():
    """Saves the current in-memory state to a JSON file."""
    state = {
        "devices": devices,
        "ota_log": ota_log,
        "anomaly_count": anomaly_count
    }
    try:
        DATA_STORE.write_text(json.dumps(state, indent=4))
    except Exception as e:
        print(f"⚠️ Error saving state: {e}")

def load_state():
    """Loads state from JSON file into memory."""
    global devices, ota_log, anomaly_count
    if DATA_STORE.exists():
        try:
            data = json.loads(DATA_STORE.read_text())
            
            # Update devices dictionary (don't overwrite the object reference)
            saved_devices = data.get("devices", {})
            devices.update(saved_devices)
            
            # Restore logs
            saved_logs = data.get("ota_log", [])
            if saved_logs:
                ota_log.clear()
                ota_log.extend(saved_logs)
                
            anomaly_count = data.get("anomaly_count", 0)
            print(f"✅ State Loaded: {len(devices)} devices, {len(ota_log)} logs.")
        except Exception as e:
            print(f"⚠️ Error loading state: {e}")