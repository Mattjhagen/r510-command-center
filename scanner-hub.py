#!/usr/bin/env python3
"""scanner-hub: live radio audio mixer + CORS API for the 911 Command Center app.

Serves on 0.0.0.0:8571
  GET  /live                endless chunked MP3 stream (real clips + silence)
  POST /clip                poller pushes a downloaded clip (raw mp3 body)
  GET  /api/transcripts     proxy to whisper /transcripts (CORS)
  GET  /api/incidents       Omaha PD incident data (crime.json)
  GET  /api/cameras         NDOT highway cameras (cameras.json)
  GET  /health              status json
"""
import json
import logging
import os
import queue
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HOST = os.environ.get("HUBS_HOST", "0.0.0.0")
PORT = int(os.environ.get("HUBS_PORT", "8571"))
WHISPER = os.environ.get("WHISPER_URL", "http://127.0.0.1:8424")
INCIDENTS = Path(os.environ.get("INCIDENTS_JSON", "/home/matt/r510-web/crime.json"))
CAMERAS = Path(os.environ.get("CAMERAS_JSON", "/home/matt/r510-command-center/cameras.json"))
SIL = Path("/tmp/opencode/r510/sil.mp3")
MAX_CLIP_BYTES = 4 * 1024 * 1024

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("hub")

_clips = queue.Queue()
_peers = set()
_peers_lock = threading.Lock()


def _silence():
    return SIL.read_bytes() if SIL.exists() else b""


class Hub(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "ScannerHub/0.1"

    def log_message(self, fmt, *args):
        log.info("%s %s" % (self.address_string(), fmt % args))

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def _read_body(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0 or length > MAX_CLIP_BYTES:
            return None
        return self.rfile.read(length)

    def do_POST(self):
        if self.path.split("?")[0] != "/clip":
            self._json({"ok": False, "error": "not found"}, 404)
            return
        body = self._read_body()
        if not body:
            self._json({"ok": False, "error": "bad body"}, 400)
            return
        _clips.put(body)
        with _peers_lock:
            n = len(_peers)
        self._json({"ok": True, "bytes": len(body), "peers": n})

    def _send_chunk(self, data):
        self.wfile.write((b"%X\r\n" % len(data)) + data + b"\r\n")
        self.wfile.flush()

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/health":
            with _peers_lock:
                peers = len(_peers)
            self._json({"ok": True, "peers": peers, "queued": _clips.qsize(),
                        "incidents": INCIDENTS.exists(), "cameras": CAMERAS.exists()})
            return
        if path == "/live":
            self.do_live()
            return
        if path == "/api/transcripts":
            since = 0
            for q in self.path.split("?")[1:]:
                for kv in q.split("&"):
                    k, _, v = kv.partition("=")
                    if k == "since" and v.isdigit():
                        since = int(v)
            try:
                with urllib.request.urlopen("%s/transcripts?since=%d" % (WHISPER, since), timeout=6) as r:
                    self._json(json.loads(r.read().decode()))
            except Exception as e:
                self._json({"ok": False, "error": str(e), "entries": []})
            return
        if path == "/api/incidents":
            try:
                data = json.loads(INCIDENTS.read_text())
                incidents = data.get("incidents", []) if isinstance(data, dict) else []
                self._json({"ok": True, "count": len(incidents), "incidents": incidents,
                            "generated_at": data.get("generated_at") if isinstance(data, dict) else None})
            except Exception as e:
                self._json({"ok": False, "error": str(e), "incidents": []})
            return
        if path == "/api/cameras":
            try:
                data = json.loads(CAMERAS.read_text())
                self._json({"ok": True, "cameras": data.get("cameras", []) if isinstance(data, dict) else []})
            except Exception as e:
                self._json({"ok": False, "error": str(e), "cameras": []})
            return
        if path in ("/", "/status"):
            self._json({"name": "scanner-hub", "endpoints": ["/live", "/clip", "/api/transcripts", "/api/incidents", "/api/cameras", "/health"]})
            return
        self._json({"ok": False, "error": "not found"}, 404)

    def do_live(self):
        sock = self.request
        self.send_response(200)
        self.send_header("Content-Type", "audio/mpeg")
        self.send_header("Transfer-Encoding", "chunked")
        self.send_header("Cache-Control", "no-cache, no-store")
        self._cors()
        self.end_headers()
        with _peers_lock:
            _peers.add(sock)
        try:
            while True:
                if sock not in _safe_peers():
                    break
                data = _clips.get(timeout=1.0)
                self._send_chunk(data)
        except queue.Empty:
            sil = _silence()
            if sil:
                try:
                    self._send_chunk(sil)
                except Exception:
                    pass
        except Exception:
            pass
        finally:
            with _peers_lock:
                _peers.discard(sock)


def _safe_peers():
    with _peers_lock:
        return set(_peers)


def mixer_loop():
    while True:
        try:
            data = _clips.get(timeout=1.0)
        except queue.Empty:
            data = None
        if data is None:
            sil = _silence()
            if not sil:
                time.sleep(1.0)
                continue
            data = sil
        for sock in list(_safe_peers()):
            try:
                sock.sendall((b"%X\r\n" % len(data)) + data + b"\r\n")
            except Exception:
                with _peers_lock:
                    _peers.discard(sock)


def main():
    # delay so peers only get streamed from the mixer thread
    t = threading.Thread(target=mixer_loop, daemon=True)
    t.start()
    srv = ThreadingHTTPServer((HOST, PORT), Hub)
    log.info("scanner-hub on %s:%d (whisper=%s)" % (HOST, PORT, WHISPER))
    srv.serve_forever()


if __name__ == "__main__":
    main()