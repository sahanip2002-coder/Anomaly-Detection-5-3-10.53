# server/app/routes/telemetry.py
from fastapi import APIRouter, Request, HTTPException
from app.state.device_store import update_device, get_devices
from app.utils import load_json
import time

router = APIRouter()


@router.post("/telemetry")
async def receive_telemetry(request: Request):
    """Receive telemetry from ESP32 devices."""
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    device_id = data.get("device_id")
    if not device_id:
        raise HTTPException(status_code=400, detail="Missing device_id")

    # Check if device is in allowed list
    allowed = load_json("devices.json").get("allowed_devices", [])
    if allowed and device_id not in allowed:
        raise HTTPException(status_code=403, detail=f"Device '{device_id}' not authorized")

    timestamp = time.time()
    update_device(device_id, data, timestamp)

    return {"status": "ok", "device_id": device_id, "timestamp": timestamp}


@router.get("/api/devices")
async def get_all_devices():
    """Return all known devices and their latest telemetry."""
    raw = get_devices()
    result = {}

    for device_id, info in raw.items():
        last = info.get("last_data", {})
        result[device_id] = {
            # Identity
            "device_id": device_id,
            "status":    info.get("status", "OFFLINE"),
            "version":   last.get("version", "—"),
            "ip":        last.get("ip", info.get("ip", "—")),
            "ota_port":  last.get("ota_port", info.get("ota_port", 8000)),
            # Telemetry
            "cpu":         last.get("cpu", 0),
            "mem":         last.get("mem", 0),
            "temp":        last.get("temp", 0),
            "battery":     last.get("battery", 100),
            "latency_ms":  last.get("latency_ms", 0),
            "error_count": last.get("error_count", 0),
            "rssi":        last.get("rssi", 0),
            "uptime_sec":  last.get("uptime_sec", 0),
            "storage":     last.get("storage", 0),
            # Meta
            "last_seen":              info.get("last_seen"),
            "firmware_update_available": info.get("firmware_update_available", False),
        }

    return result


@router.get("/api/stats")
async def get_stats():
    """Return aggregate stats and log entries."""
    from app.state.device_store import ota_log, anomaly_count
    raw = get_devices()
    anomalies = sum(1 for d in raw.values() if "ANOMALY" in d.get("status", ""))
    return {
        "anomalies": anomalies + anomaly_count,
        "log":       list(ota_log)[-50:],   # last 50 entries
        "total":     len(raw),
        "online":    sum(1 for d in raw.values() if d.get("status") == "ONLINE"),
        "offline":   sum(1 for d in raw.values() if d.get("status") == "OFFLINE"),
    }