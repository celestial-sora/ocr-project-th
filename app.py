from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from flask import Flask, jsonify, render_template, request
import re

import line_notify
import plate_whitelist
import database
import esp_serial

BASE_DIR = Path(__file__).resolve().parent
MAIN_PY = BASE_DIR / "main.py"
API_KEYS_FILE = BASE_DIR / "app_secrets.py"

database.init_db()

app = Flask(__name__)
main_process: subprocess.Popen[str] | None = None


def _is_running() -> bool:
    global main_process
    if main_process is None:
        return False
    if main_process.poll() is None:
        return True
    main_process = None
    return False


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/status")
def status():
    # ตรวจสอบสถานะ process และสถานะบอร์ด ESP8266
    is_run = _is_running()
    esp_info = esp_serial.get_device_status()
    return jsonify({
        "running": is_run,
        "esp": esp_info,
    })


@app.post("/api/run-main")
def run_main():
    global main_process
    if _is_running():
        return jsonify({"ok": True, "message": "main.py is already running"})

    child_env = os.environ.copy()
    child_env["PYTHONIOENCODING"] = "utf-8"

    main_process = subprocess.Popen(
        [sys.executable, str(MAIN_PY)],
        cwd=str(BASE_DIR),
        text=True,
        env=child_env,
    )
    return jsonify({"ok": True, "message": "Started main.py"})


@app.post("/api/stop-main")
def stop_main():
    global main_process
    if not _is_running():
        return jsonify({"ok": False, "message": "main.py is not running"}), 400
    assert main_process is not None
    main_process.terminate()
    main_process = None
    return jsonify({"ok": True, "message": "Stopped main.py"})


@app.get("/api/whitelist")
def get_whitelist():
    items = sorted(plate_whitelist.load_whitelist())
    return jsonify({"items": items})


@app.post("/api/whitelist")
def add_whitelist():
    data = request.get_json(silent=True) or {}
    plate = str(data.get("plate", "")).strip()
    if not plate:
        return jsonify({"ok": False, "message": "plate is required"}), 400
    items = sorted(plate_whitelist.add_plate(plate))
    return jsonify({"ok": True, "items": items})


@app.delete("/api/whitelist")
def delete_whitelist():
    data = request.get_json(silent=True) or {}
    plate = str(data.get("plate", "")).strip()
    if not plate:
        return jsonify({"ok": False, "message": "plate is required"}), 400
    items = sorted(plate_whitelist.remove_plate(plate))
    return jsonify({"ok": True, "items": items})


@app.get("/api/logs")
def get_logs():
    limit = request.args.get("limit", default=50, type=int)
    logs = database.get_logs(limit)
    return jsonify({"logs": logs})


@app.post("/api/logs/clear")
def clear_logs():
    database.clear_logs()
    return jsonify({"ok": True, "message": "Cleared all logs"})


@app.post("/api/test-line")
def test_line():
    if not line_notify.messaging_push_ready():
        return jsonify({"ok": False, "message": "LINE token or destination is not configured"}), 400
    ok = line_notify.send_push_text("Test message from whitelist dashboard")
    if ok:
        return jsonify({"ok": True, "message": "LINE test message sent"})
    return jsonify({"ok": False, "message": "Failed to send LINE message"}), 500


@app.get("/api/line-keys")
def get_line_keys():
    """Return current LINE credentials from app_secrets.py."""
    import app_secrets as ak
    return jsonify({
        "token": ak.LINE_CHANNEL_ACCESS_TOKEN,
        "push_to": ak.LINE_PUSH_TO,
    })


@app.post("/api/line-keys")
def save_line_keys():
    """Overwrite LINE credentials in app_secrets.py."""
    data = request.get_json(silent=True) or {}
    token = str(data.get("token", "")).strip()
    push_to = str(data.get("push_to", "")).strip()
    if not token or not push_to:
        return jsonify({"ok": False, "message": "Both token and push_to are required"}), 400

    content = API_KEYS_FILE.read_text(encoding="utf-8")
    content = re.sub(
        r'^LINE_CHANNEL_ACCESS_TOKEN\s*=\s*".*?"',
        f'LINE_CHANNEL_ACCESS_TOKEN = "{token}"',
        content,
        flags=re.MULTILINE,
    )
    content = re.sub(
        r'^LINE_PUSH_TO\s*=\s*".*?"',
        f'LINE_PUSH_TO = "{push_to}"',
        content,
        flags=re.MULTILINE,
    )
    API_KEYS_FILE.write_text(content, encoding="utf-8")

    # Reload modules so changes take effect immediately
    import importlib
    import app_secrets as ak
    importlib.reload(ak)
    # line_notify imports app_secrets at module level — must reload it too
    importlib.reload(line_notify)

    return jsonify({"ok": True, "message": "LINE credentials saved successfully"})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
