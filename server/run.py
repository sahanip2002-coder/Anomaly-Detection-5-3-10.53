import uvicorn
from app.utils import create_ssl_cert

if __name__ == "__main__":
    # 1. Ensure SSL is ready before server start
    key_path, cert_path = create_ssl_cert()
    
    print("\n" + "="*60)
    print("   IOTFW SECURE OTA SERVER (MODULAR)")
    print("   Running at https://0.0.0.0:8443")
    print("="*60 + "\n")

    # 2. Start Uvicorn
    uvicorn.run(
        "app.main:app", 
        host="0.0.0.0", 
        port=8443, 
        ssl_keyfile=str(key_path), 
        ssl_certfile=str(cert_path),
        reload=True
    )