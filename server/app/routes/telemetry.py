from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from app.state import devices
from app.utils import load_json
from app.services import check_telemetry_health, log_security_events

router = APIRouter()

# 1. DEFINE DATA MODEL
# This MUST match the fields sent by your client/client.py
class TelemetryModel(BaseModel):
    # Core Fields
    device_id: str
    cpu: float
    mem: float
    temp: float
    version: str
    timestamp: int
    ota_port: int = 8000 
    
    # Extended Fields (These were missing!)
    disk_usage: Optional[float] = 0.0
    net_sent_mb: Optional[float] = 0.0
    net_recv_mb: Optional[float] = 0.0
    boot_time: Optional[int] = 0       # <--- Critical for Uptime
    cpu_cores: Optional[int] = 1

@router.post("/telemetry")
async def receive_telemetry(data: TelemetryModel, request: Request):
    # Security Whitelist Check
    allowed = load_json("devices.json", {}).get("allowed_devices", [])
    if allowed and data.device_id not in allowed:
        print(f"⛔ BLOCKED unauthorized device: {data.device_id}")
        raise HTTPException(status_code=403, detail="Unauthorized")

    # Logic Check (Anomaly Detection)
    status, is_stable = check_telemetry_health(data)
    
    # Logging
    log_security_events(data.device_id, not is_stable, data.cpu)

    # 2. CAPTURE AND SAVE CLIENT DETAILS
    # Now that 'boot_time' is in the model, data.dict() will include it!
    devices[data.device_id] = {
        **data.dict(), 
        "ip": request.client.host,
        "last_seen": datetime.now().strftime("%H:%M:%S"),
        "status": status,
        "is_stable": is_stable
    }
    
    return {"status": "ok"}