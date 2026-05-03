# server/app/routes/admin.py
from fastapi import APIRouter, Query, UploadFile, File
from app.state import devices, ota_log
from app.utils import load_json, FIRMWARE_DIR
from app.services import trigger_device_update

router = APIRouter()


@router.get("/ota-check")
async def ota_check(device_id: str = Query(...)):
    """Return firmware URL only if device is stable and outdated."""
    target_fw = load_json("ota_settings.json").get("target_firmware_version", "")
    device    = devices.get(device_id, {})
    current_fw = device.get("version", "")
    status     = device.get("status", "Unknown")

    if current_fw != target_fw and "ANOMALY" not in status:
        device["firmware_update_available"] = True
        return f"https://0.0.0.0:8443/firmware/latest.bin"

    device["firmware_update_available"] = False
    return ""


@router.post("/admin/upload-firmware")
async def upload_firmware(file: UploadFile = File(...)):
    """Upload a .bin firmware file to the server."""
    dest    = FIRMWARE_DIR / "latest.bin"
    content = await file.read()
    dest.write_bytes(content)
    return {
        "filename": "latest.bin",
        "size_kb":  round(len(content) / 1024, 1)
    }


@router.post("/admin/deploy/{device_id}")
async def deploy_firmware(device_id: str):
    """
    Trigger OTA update on a specific device.
    Server calls back: POST http://{device_ip}:{ota_port}/ota-trigger
    ESP32 then downloads /firmware/latest.bin and self-flashes.
    """
    # Check device exists
    device = devices.get(device_id)
    if not device:
        return {"status": "blocked", "reason": f"Device '{device_id}' not found"}

    # Check firmware file exists on server
    fw_path = FIRMWARE_DIR / "latest.bin"
    if not fw_path.exists():
        return {"status": "blocked", "reason": "No firmware file on server. Upload latest.bin first."}

    # Block OTA if device is in ANOMALY state
    if "ANOMALY" in device.get("status", ""):
        return {"status": "blocked", "reason": f"Device is in ANOMALY state — OTA blocked for safety."}

    # Get device IP and OTA port
    ip       = device.get("ip")
    ota_port = device.get("ota_port", 8000)

    if not ip:
        return {"status": "blocked", "reason": "Device IP not known. Wait for telemetry."}

    # Trigger OTA — calls POST http://{ip}:{ota_port}/ota-trigger
    ota_log.append(f"🚀 OTA deploy triggered → {device_id} @ {ip}:{ota_port}")
    await trigger_device_update(device_id, ip)

    return {
        "status":    "triggered",
        "device_id": device_id,
        "ip":        ip,
        "ota_port":  ota_port,
        "firmware":  "latest.bin"
    }