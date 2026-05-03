import uvicorn
import multiprocessing
from app.utils import create_ssl_cert
from app.main import app

if __name__ == "__main__":
    # 1. Windows Multiprocessing Fix
    multiprocessing.freeze_support()

    # 2. Ensure SSL is ready
    key_path, cert_path = create_ssl_cert()
    
    print("\n" + "="*60)
    print("   SECURE OTA SERVER (MODULAR)")
    print("   Running at https://0.0.0.0:8443")
    print("="*60 + "\n")

    # 3. Start Uvicorn
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8443, 
        ssl_keyfile=str(key_path), 
        ssl_certfile=str(cert_path),
        log_level="info"
    )