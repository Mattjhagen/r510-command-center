#!/usr/bin/env python3
"""
Scanner API Server - R510 command center live API for the 911-Command-Center app.

Single consolidating service on port 8898.

  GET  /health
  GET  /status
  GET  /api/scanner/recent?minutes=&limit=     whisper transcriptions from listener feed
  GET  /api/scanner/live                        latest scanner message for polling
  GET  /api/scanner/talkgroups                 talkgroup id/name list
  GET  /api/cameras                             NDOT DOT cameras (transformed for app)
  GET  /api/cameras/proxy?url=                 CORS proxy for camera images
  GET  /api/crime                               Omaha PD incidents (crime.json)
  GET  /api/incidents                           alias of /api/crime
  GET  /api/transcripts?since=N                 proxy passthrough to whisper server
  GET  /live                                    endless chunked MP3 radio stream
  POST /clip                                    poller pushes downloaded clips (raw mp3 body)
"""

import json
import logging
import os
import queue
import re
import threading
import time
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

from flask import Flask, Response, jsonify, request, stream_with_context
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("scanner-api")

HERE = Path(__file__).resolve().parent
LOG_FILE = HERE / "calls-poller.log"
CRIME_FILE = Path(os.environ.get("CRIME_JSON", "/home/matt/r510-web/crime.json"))
WHISPER = os.environ.get("WHISPER_URL", "http://127.0.0.1:8424")
SIL = Path("/tmp/opencode/r510/sil.mp3")
MAX_MESSAGES = 200
MAX_CLIP_BYTES = 4 * 1024 * 1024

# Real agency names for handled ORION talkgroups
TALKGROUP_MAP = {
    "2361-710": "UNO PD",
    "2361-711": "UNMC PS",
    "2361-12": "DCSO CIVIC",
    "2361-3075": "NSP TROOP A",
    "2361-458": "OFD VFD DISPATCH",
    "2361-210": "LIFENET HELO",
    "2361-331": "CREIGHTON EMS",
    "2361-802": "MAT TRANSIT",
    "2361-809": "MAT TRANSIT TAC",
}

# ---- live audio mixer ----
_audio_clips = queue.Queue(maxsize=512)
_listener_queues = set()
_listener_lock = threading.Lock()
_silence_bytes = SIL.read_bytes() if SIL.exists() else b""


def _distributor_loop():
    while True:
        try:
            data = _audio_clips.get(timeout=1.0)
        except queue.Empty:
            data = _silence_bytes or None
        if data is None:
            time.sleep(1.0)
            continue
        with _listener_lock:
            qs = list(_listener_queues)
        for q in qs:
            try:
                q.put_nowait(data)
            except Exception:
                pass


def parse_log_line(line):
    """Parse a calls-poller.log line into structured dispatch data."""
    ts_match = re.match(r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
    if not ts_match:
        return None
    timestamp_str = ts_match.group(1)
    tg_match = re.search(r'\[(\d+)\] (2361-\d+) dur=(\d+)s -> (.*)$', line)
    if not tg_match:
        return None
    seq_num = tg_match.group(1)
    talkgroup_id = tg_match.group(2)
    duration = int(tg_match.group(3))
    transcription = tg_match.group(4).strip()
    if not transcription:
        return None
    dt = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
    time_str = dt.strftime("%I:%M:%S %p")

    severity = "low"
    text_lower = transcription.lower()
    high_keywords = ["10-33", "emergency", "shots", "weapon", "pursuit", "assault", "robbery", "fire"]
    medium_keywords = ["10-97", "alarm", "suspicious", "disturbance", "check", "traffic", "accident"]
    if any(kw in text_lower for kw in high_keywords):
        severity = "high"
    elif any(kw in text_lower for kw in medium_keywords):
        severity = "medium"

    ten_codes = re.findall(r'10-\d+[A-Z]?', transcription, re.IGNORECASE)

    return {
        "id": f"live-{int(dt.timestamp())}-{seq_num}",
        "unit": f"UNIT {seq_num}",
        "time": time_str,
        "rawTransmission": transcription,
        "translatedText": transcription,
        "tenCodesDetected": ten_codes,
        "severity": severity,
        "talkgroup": TALKGROUP_MAP.get(talkgroup_id, talkgroup_id),
        "audioDurationSec": duration,
        "timestamp": dt.isoformat(),
    }


def load_recent_messages(minutes=30):
    if not LOG_FILE.exists():
        return []
    cutoff = datetime.now() - timedelta(minutes=minutes)
    messages = []
    try:
        with open(LOG_FILE, "r") as f:
            lines = f.readlines()[-2000:]
        for line in lines:
            msg = parse_log_line(line)
            if msg:
                msg_dt = datetime.fromisoformat(msg["timestamp"])
                if msg_dt >= cutoff:
                    messages.append(msg)
        messages.sort(key=lambda m: m["timestamp"], reverse=True)
    except Exception as e:
        log.warning("load_recent_messages: %s", e)
    return messages


def read_crime():
    data = json.loads(CRIME_FILE.read_text())
    incidents = data.get("incidents", []) if isinstance(data, dict) else []
    meta = {k: v for k, v in data.items() if k != "incidents"} if isinstance(data, dict) else {}
    meta["count"] = len(incidents)
    return incidents, meta


@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "ok": True,
        "service": "r510-scanner-api",
        "log_file": str(LOG_FILE),
        "log_exists": LOG_FILE.exists(),
        "crime_exists": CRIME_FILE.exists(),
        "listeners": len(_listener_queues),
    })


@app.route("/status", methods=["GET"])
def status():
    return jsonify({
        "ok": True,
        "listeners": len(_listener_queues),
        "audio_queued": _audio_clips.qsize(),
        "crime": CRIME_FILE.exists(),
        "endpoints": ["/health", "/status", "/api/scanner/recent", "/api/scanner/live",
                      "/api/scanner/talkgroups", "/api/cameras", "/api/cameras/proxy",
                      "/api/crime", "/api/incidents", "/api/transcripts", "/live", "/clip"],
    })


@app.route("/api/scanner/recent", methods=["GET"])
def get_recent():
    minutes = int(request.args.get("minutes", 30))
    limit = int(request.args.get("limit", 50))
    messages = load_recent_messages(minutes)[:limit]
    return jsonify({
        "count": len(messages),
        "messages": messages,
        "updated_at": datetime.now().isoformat(),
    })


@app.route("/api/scanner/live", methods=["GET"])
def get_live():
    messages = load_recent_messages(5)
    return jsonify({
        "latest": messages[0] if messages else None,
        "updated_at": datetime.now().isoformat(),
    })


@app.route("/api/scanner/talkgroups", methods=["GET"])
def get_talkgroups():
    return jsonify({
        "talkgroups": [{"id": k, "name": v} for k, v in TALKGROUP_MAP.items()]
    })


@app.route("/api/incidents", methods=["GET"])
@app.route("/api/crime", methods=["GET"])
def get_crime():
    try:
        incidents, meta = read_crime()
        return jsonify({"ok": True, "incidents": incidents, **meta})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e), "incidents": []}), 500


@app.route("/api/transcripts", methods=["GET"])
def get_transcripts():
    since = int(request.args.get("since", 0) or 0)
    try:
        with urllib.request.urlopen("%s/transcripts?since=%d" % (WHISPER, since), timeout=6) as r:
            return Response(r.read().decode(), mimetype="application/json")
    except Exception as e:
        return jsonify({"ok": False, "error": str(e), "entries": []})


@app.route("/live")
def live_audio():
    q = queue.Queue(maxsize=256)
    with _listener_lock:
        _listener_queues.add(q)

    def gen():
        try:
            while True:
                try:
                    data = q.get(timeout=2.0)
                except queue.Empty:
                    break
                if data:
                    yield data
        finally:
            with _listener_lock:
                _listener_queues.discard(q)

    resp = Response(stream_with_context(gen()), mimetype="audio/mpeg")
    resp.headers["Cache-Control"] = "no-cache, no-store"
    resp.headers["X-Accel-Buffering"] = "no"
    return resp


@app.route("/clip", methods=["POST"])
def clip_ingest():
    data = request.get_data(cache=False)
    if not data or len(data) > MAX_CLIP_BYTES:
        return jsonify({"ok": False, "error": "bad body"}), 400
    try:
        _audio_clips.put_nowait(data)
    except Exception:
        return jsonify({"ok": False, "error": "queue full"}), 503
    return jsonify({"ok": True, "bytes": len(data), "listeners": len(_listener_queues)})


@app.route("/api/cameras", methods=["GET"])
def get_cameras():
    cameras_file = HERE / "cameras.json"
    if not cameras_file.exists():
        return jsonify({"count": 0, "cameras": [], "error": "cameras.json not found"}), 404
    try:
        with open(cameras_file, "r") as f:
            data = json.load(f)
        cameras = []
        for cam in data.get("cameras", [])[:100]:
            direction = "PANORAMIC"
            name_lower = cam.get("name", "").lower()
            if "northbound" in name_lower or " n " in name_lower:
                direction = "NORTHBOUND"
            elif "southbound" in name_lower or " s " in name_lower:
                direction = "SOUTHBOUND"
            elif "eastbound" in name_lower or " e " in name_lower or " eb" in name_lower:
                direction = "EASTBOUND"
            elif "westbound" in name_lower or " w " in name_lower or " wb" in name_lower:
                direction = "WESTBOUND"

            highway = "Highway"
            name = cam.get("name", "")
            if "I-80" in name or "80-" in name:
                highway = "Interstate 80"
            elif "I-29" in name or "29-" in name:
                highway = "Interstate 29"
            elif "I-480" in name or "480-" in name:
                highway = "Interstate 480"
            elif "I-680" in name or "680-" in name:
                highway = "Interstate 680"
            elif "US-75" in name or "75-" in name:
                highway = "US Highway 75"
            elif "Dodge" in name:
                highway = "US-6 (Dodge Street)"

            cameras.append({
                "id": cam.get("id", f"cam-{len(cameras)}"),
                "name": cam.get("name", "Unknown Camera"),
                "highway": highway,
                "crossStreet": name.split("·")[1].strip() if "·" in name else "",
                "lat": cam.get("lat", 0),
                "lng": cam.get("lng", 0),
                "direction": direction,
                "status": "ONLINE",
                "snapshotUrl": cam.get("url", ""),
                "videoUrl": cam.get("video", ""),
                "lastUpdated": "Live",
                "source": cam.get("src", "NDOT"),
            })
        return jsonify({
            "count": len(cameras),
            "cameras": cameras,
            "sources": data.get("sources", []),
            "generated": data.get("generated", ""),
        })
    except Exception as e:
        return jsonify({"count": 0, "cameras": [], "error": str(e)}), 500


@app.route("/api/cameras/proxy", methods=["GET"])
def proxy_camera():
    url = request.args.get("url")
    if not url:
        return jsonify({"error": "Missing url parameter"}), 400
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://511.nebraska.gov/",
        })
        with urllib.request.urlopen(req, timeout=10) as response:
            image_data = response.read()
        return Response(image_data, mimetype="image/jpeg", headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    threading.Thread(target=_distributor_loop, daemon=True).start()
    msgs = load_recent_messages(30)
    log.info("scanner-api on :8898 (recent=%d, listeners=distributor on)", len(msgs))
    app.run(host="0.0.0.0", port=8898, debug=False, threaded=True)