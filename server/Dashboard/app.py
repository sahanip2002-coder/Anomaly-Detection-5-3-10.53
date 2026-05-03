from flask import Flask, render_template, jsonify, request, Response
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)

SERVER_URL = "https://192.168.8.102:8443"
session = requests.Session()
session.verify = False


# -------------------------------------------------------
# DASHBOARD UI
# -------------------------------------------------------
@app.route("/")
def index():
    return render_template("dashboard.html")


# -------------------------------------------------------
# TELEMETRY — proxy /api/devices + /api/stats into one response
# -------------------------------------------------------
@app.route("/api/data")
def get_data():
    devices, stats = {}, {"anomalies": 0, "log": []}
    try:
        r = session.get(f"{SERVER_URL}/api/devices", timeout=3)
        if r.status_code == 200:
            devices = r.json()
    except Exception:
        pass
    try:
        r = session.get(f"{SERVER_URL}/api/stats", timeout=3)
        if r.status_code == 200:
            stats = r.json()
    except Exception:
        pass
    return jsonify({"devices": devices, "stats": stats})


# -------------------------------------------------------
# OTA — Step 1: forward firmware file to FastAPI
# Dashboard POSTs to /admin/upload-firmware (field: 'file')
# Flask forwards the multipart file to FastAPI unchanged
# -------------------------------------------------------
@app.route("/admin/upload-firmware", methods=["POST"])
def upload_firmware():
    if "file" not in request.files:
        return jsonify({"error": "No firmware file provided"}), 400

    fw_file = request.files["file"]
    try:
        resp = session.post(
            f"{SERVER_URL}/admin/upload-firmware",
            files={"file": (fw_file.filename, fw_file.stream, fw_file.mimetype)},
            timeout=30,
        )
        return Response(resp.content, status=resp.status_code,
                        content_type=resp.headers.get("content-type", "application/json"))
    except Exception as e:
        return jsonify({"error": str(e)}), 502


# -------------------------------------------------------
# OTA — Step 2: forward deploy trigger to FastAPI
# FastAPI calls back to ESP32 → ESP32 pulls latest.bin → flashes
# -------------------------------------------------------
@app.route("/admin/deploy/<device_id>", methods=["POST"])
def deploy_firmware(device_id):
    try:
        resp = session.post(
            f"{SERVER_URL}/admin/deploy/{device_id}",
            timeout=15,
        )
        return Response(resp.content, status=resp.status_code,
                        content_type=resp.headers.get("content-type", "application/json"))
    except Exception as e:
        return jsonify({"error": str(e)}), 502


# -------------------------------------------------------
# LEGACY — kept for backward compatibility
# -------------------------------------------------------
@app.route("/api/update/<device_id>", methods=["POST"])
def update_device(device_id):
    try:
        r = session.post(f"{SERVER_URL}/api/update/{device_id}", timeout=5)
        return jsonify({"status": "ok"} if r.status_code == 200 else {"status": "fail"})
    except Exception:
        return jsonify({"status": "error"})


# -------------------------------------------------------
# ENTRYPOINT
# -------------------------------------------------------
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)