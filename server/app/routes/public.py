from fastapi import APIRouter
from fastapi.responses import FileResponse
from app.state import devices, ota_log, anomaly_count
from app.utils import FIRMWARE_DIR

router = APIRouter()

@router.get("/firmware/latest.bin")
async def get_firmware():
    fw_path = FIRMWARE_DIR / "firmware.bin"
    if not fw_path.exists():
        fw_path.write_bytes(b"IOTFW-MODULAR-FIRMWARE-v2.1.5")
    return FileResponse(fw_path)

@router.get("/api/devices")
async def get_devices(): return devices

@router.get("/api/stats")
async def get_stats():
    return {"total": len(devices), "anomalies": anomaly_count, "log": ota_log[-20:]}