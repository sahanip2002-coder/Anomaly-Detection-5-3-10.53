import asyncio
from fastapi import APIRouter, HTTPException
from app.state import devices, ota_log
from app.services import trigger_device_update
from app.utils import load_json

# Initialize the Router (This was likely missing or named wrong)
router = APIRouter()

@router.post("/admin/deploy/{device_id}")
async def deploy_ota_manual(device_id: str):
    device = devices.get(device_id)
    if not device: raise HTTPException(404, "Device not found")

    # Security Check
    if not device.get("is_stable", True):
        msg = f"🛑 BLOCKED → OTA for {device_id} rejected (Risk: High Load)"
        ota_log.append(msg)
        return {"status": "blocked", "reason": "Anomaly Detected"}

    # Version Check
    ota_settings = load_json("ota_settings.json", {"target_firmware_version": "2.1.5"})
    target_ver = ota_settings.get("target_firmware_version", "2.1.5")
    
    if device.get("version") == target_ver:
         return {"status": "skipped", "reason": f"Device already on v{target_ver}"}

    msg = f"🚀 DEPLOYING → {device_id} (Stable). Sending trigger..."
    ota_log.append(msg)
    asyncio.create_task(trigger_device_update(device_id, device["ip"]))
    
    return {"status": "initiated", "target_ip": device["ip"], "target_ver": target_ver}