import json
from pathlib import Path
from datetime import datetime, timedelta, timezone
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography import x509
from cryptography.x509.oid import NameOID

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = BASE_DIR / "config"
FIRMWARE_DIR = BASE_DIR / "firmware"

def setup_directories():
    CONFIG_DIR.mkdir(exist_ok=True)
    FIRMWARE_DIR.mkdir(exist_ok=True)

def load_json(filename, default=None):
    path = CONFIG_DIR / filename
    if path.exists():
        try: return json.loads(path.read_text())
        except: pass
    return default if default is not None else {}

def create_ssl_cert():
    key_path = BASE_DIR / "key.pem"
    cert_path = BASE_DIR / "cert.pem"
    
    if key_path.exists() and cert_path.exists(): 
        return key_path, cert_path

    print("Generating SSL cert...")
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "peera-server")])
    cert = x509.CertificateBuilder().subject_name(name).issuer_name(name)\
        .public_key(key.public_key()).serial_number(x509.random_serial_number())\
        .not_valid_before(datetime.now(timezone.utc))\
        .not_valid_after(datetime.now(timezone.utc) + timedelta(days=3650))\
        .sign(key, hashes.SHA256())
    
    key_path.write_text(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode())
    cert_path.write_text(cert.public_bytes(serialization.Encoding.PEM).decode())
    
    return key_path, cert_path