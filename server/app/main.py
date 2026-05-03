from fastapi import FastAPI
from app.utils import setup_directories, load_json, CONFIG_DIR
from app.routes import telemetry, admin, public
import json

app = FastAPI(title="IOTFW Secure OTA Server (Modular)")

# Include Routers
app.include_router(telemetry.router)
app.include_router(admin.router)
app.include_router(public.router)

# Event: On Startup
@app.on_event("startup")
async def startup_event():
    setup_directories()
    
    # Create default config files if missing
    defaults = {
        "thresholds.json": {"global": {"cpu_threshold": 85.0, "mem_threshold": 90.0}},
        "devices.json": {"allowed_devices": ["iot-001", "iot-002", "sensor-03"]},
        "ota_settings.json": {"target_firmware_version": "2.1.5"}
    }
    for f, d in defaults.items():
        if not load_json(f): 
            (CONFIG_DIR / f).write_text(json.dumps(d, indent=4))
            
    print("✅ Server Modules Loaded Successfully")