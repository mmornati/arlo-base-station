"""
Arlo RTSP Snapshot Service
Grabs a single JPEG frame from a camera's RTSP stream when motion triggers it.
Stores the frame in memory so HA can retrieve it without re-waking the camera.

Flow:
  1. PIR motion → server.py → POST /snapshot/{serial} → wakes camera, grabs frame, stores in memory
  2. HA requests still image → GET /snapshot/{serial} → returns last stored frame (no RTSP)

No polling. No cache TTL. Frame is only refreshed on motion trigger.
"""
import os
import io
import time
import threading
import logging
import requests
import av
from PIL import Image
from flask import Flask, Response, abort, jsonify, request

ARLO_API = os.environ.get("ARLO_API", "http://arlo-cam-api:5000")
SNAPSHOT_PORT = int(os.environ.get("SNAPSHOT_PORT", "8000"))
RTSP_TIMEOUT_US = int(os.environ.get("RTSP_TIMEOUT_US", "8000000"))
DEVICE_CACHE_TTL = int(os.environ.get("DEVICE_CACHE_TTL", "60"))
MAX_WIDTH = int(os.environ.get("MAX_WIDTH", "1280"))
JPEG_QUALITY = int(os.environ.get("JPEG_QUALITY", "75"))
USERSTREAM_TTL = int(os.environ.get("USERSTREAM_TTL", "30"))
STREAM_WARMUP_SEC = float(os.environ.get("STREAM_WARMUP_SEC", "6"))
RTSP_RETRIES = int(os.environ.get("RTSP_RETRIES", "3"))
RTSP_RETRY_DELAY = float(os.environ.get("RTSP_RETRY_DELAY", "2"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("arlo-snapshot")

app = Flask(__name__)

device_cache = {"data": None, "ts": 0}
device_lock = threading.Lock()

store = {}
store_lock = threading.Lock()

stream_state = {}


def get_devices():
    now = time.time()
    with device_lock:
        if device_cache["data"] is not None and (now - device_cache["ts"]) < DEVICE_CACHE_TTL:
            return device_cache["data"]
        try:
            r = requests.get(f"{ARLO_API}/device", timeout=5)
            r.raise_for_status()
            device_cache["data"] = {d["serial_number"]: d for d in r.json()}
            device_cache["ts"] = now
            log.info(f"Refreshed device cache: {list(device_cache['data'].keys())}")
            return device_cache["data"]
        except Exception as e:
            log.error(f"Failed to fetch devices from {ARLO_API}: {e}")
            if device_cache["data"] is not None:
                return device_cache["data"]
            return {}


def activate_stream(serial):
    try:
        r = requests.post(
            f"{ARLO_API}/device/{serial}/userstreamactive",
            json={"active": True},
            timeout=5,
        )
        return r.json().get("result", False)
    except Exception as e:
        log.error(f"Failed to activate stream for {serial}: {e}")
        return False


def grab_frame(ip):
    last_err = None
    for port in (555, 554):
        try:
            container = av.open(
                f"rtsp://{ip}:{port}/live",
                options={"rtsp_transport": "tcp", "stimeout": str(RTSP_TIMEOUT_US)},
            )
            for stream in container.streams:
                if stream.type != "video":
                    continue
                for frame in container.decode(stream):
                    container.close()
                    return frame.to_image()
            container.close()
        except Exception as e:
            last_err = e
            log.warning(f"[{ip}] RTSP :{port} failed: {e}")
            continue
    raise last_err or RuntimeError("no RTSP port worked")


def make_jpeg(pil_img):
    if pil_img.width > MAX_WIDTH:
        ratio = MAX_WIDTH / pil_img.width
        new_size = (MAX_WIDTH, int(pil_img.height * ratio))
        pil_img = pil_img.resize(new_size, Image.LANCZOS)
    buf = io.BytesIO()
    if pil_img.mode != "RGB":
        pil_img = pil_img.convert("RGB")
    pil_img.save(buf, format="JPEG", quality=JPEG_QUALITY)
    return buf.getvalue()


def grab_and_store(serial):
    devices = get_devices()
    dev = devices.get(serial)
    if not dev:
        log.warning(f"[{serial}] camera not found in arlo-cam-api")
        return False, "Camera not registered"

    ip = dev["ip"]
    now = time.time()
    last_activation = stream_state.get(serial, 0)
    if now - last_activation > USERSTREAM_TTL:
        log.info(f"[{serial}] activating userstream (last: {int(now - last_activation)}s ago)")
        if not activate_stream(serial):
            return False, "Failed to activate camera stream"
        stream_state[serial] = now
        time.sleep(STREAM_WARMUP_SEC)
    else:
        log.info(f"[{serial}] userstream already active ({int(now - last_activation)}s ago)")

    try:
        pil_img = grab_frame(ip)
        jpeg = make_jpeg(pil_img)
    except Exception as e:
        log.error(f"[{serial}] grab failed: {e}")
        stream_state.pop(serial, None)
        return False, str(e)

    with store_lock:
        store[serial] = {"ts": time.time(), "data": jpeg}

    log.info(f"[{serial}] snapshot stored, {len(jpeg)} bytes")
    return True, jpeg


@app.route("/")
def health():
    return jsonify({"status": "ok", "service": "arlo-snapshot"})


@app.route("/devices")
def devices():
    return jsonify(get_devices())


@app.route("/snapshot/<serial>", methods=["POST"])
def trigger_snapshot(serial):
    ok, result = grab_and_store(serial)
    if not ok:
        return jsonify({"ok": False, "error": result}), 502
    return jsonify({"ok": True, "serial": serial, "bytes": len(result)})


@app.route("/snapshot/<serial>", methods=["GET"])
def get_snapshot(serial):
    with store_lock:
        data = store.get(serial)
    if data is None:
        abort(404, description=f"No snapshot available for {serial}")
    return Response(data["data"], mimetype="image/jpeg")


if __name__ == "__main__":
    log.info(f"Starting arlo-snapshot on port {SNAPSHOT_PORT}, ARLO_API={ARLO_API}")
    app.run(host="0.0.0.0", port=SNAPSHOT_PORT, threaded=True)