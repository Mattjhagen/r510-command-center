#!/usr/bin/env python3
"""Minimal live audio relay for the R510 whisper pipeline.

Intended deployment: archon-fly-gateway (100.82.142.55), bind to the
Tailscale interface only so nothing is exposed publicly.

Pulls an MP3/AAC source URL (e.g. Broadcastify cdnstream) and serves it to
LAN/Tailscale HTTP clients as a live chunked stream. Keeps a short tail of
recent bytes so clients who join mid-stream start with valid audio.

Usage:
  RLY_SOURCE=<stream url> RLY_BIND=100.82.142.55 RLY_PORT=8425 python3 audio-relay.py

Endpoints:
  GET /            -> live audio stream (Transfer-Encoding: chunked, audio/mpeg)
  GET /health      -> {"ok": true, "source": ..., "alive": bool, "bytes": int, "subs": int}
"""
import json
import os
import queue
import sys
import threading
import time
import urllib.request
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

SOURCE = os.environ.get("RLY_SOURCE", "").strip()
BIND = os.environ.get("RLY_BIND", "100.82.142.55").strip()
PORT = int(os.environ.get("RLY_PORT", "8425"))
TAIL_BYTES = int(os.environ.get("RLY_TAIL_BYTES", "24576"))
STALL_SECONDS = float(os.environ.get("RLY_STALL", "15"))
REPLAY = os.environ.get("RLY_REPLAY", "0") == "1"
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"}

_lock = threading.Lock()
_tail = deque(maxlen=TAIL_BYTES)
_subs = set()
_stats = {"alive": False, "bytes": 0, "err": "", "since": 0.0}
_stop = threading.Event()


def push(blk: bytes):
    with _lock:
        _tail.extend(blk)
        dead = []
        for q in _subs:
            try:
                q.put_nowait(blk)
            except queue.Full:
                dead.append(q)
        for q in dead:
            _subs.discard(q)


def _pull():
    while not _stop.is_set():
        try:
            req = urllib.request.Request(SOURCE, headers=UA)
            with urllib.request.urlopen(req, timeout=60) as resp:
                with _lock:
                    _stats["alive"] = True
                    _stats["err"] = ""
                    _stats["since"] = time.time()
                while not _stop.is_set():
                    blk = resp.read(8192)
                    if not blk:
                        break
                    push(blk)
                    with _lock:
                        _stats["bytes"] += len(blk)
            if REPLAY:
                while not _stop.is_set():
                    with _lock:
                        loop = bytes(_tail)
                    for i in range(0, len(loop), 8192):
                        if _stop.is_set():
                            break
                        push(loop[i:i + 8192])
                        time.sleep(len(loop[i:i + 8192]) / 16000.0)
        except Exception as e:
            with _lock:
                _stats["alive"] = False
                _stats["err"] = str(e)[:160]
            print("relay source error: %s" % e, flush=True)
        if _stop.wait(5):
            break
    with _lock:
        _stats["alive"] = False


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def _hdr(self, code, ctype, extra=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-cache, no-transform")
        self.send_header("Access-Control-Allow-Origin", "*")
        for k, v in (extra or []):
            self.send_header(k, v)

    def do_GET(self):
        if self.path.split("?")[0] in ("/health", "/status"):
            with _lock:
                body = json.dumps({
                    "ok": _stats["alive"],
                    "source": SOURCE,
                    "alive": _stats["alive"],
                    "err": _stats["err"],
                    "bytes": _stats["bytes"],
                    "subs": len(_subs),
                    "since": _stats["since"],
                    "tail": len(_tail),
                }).encode()
            self._hdr(200, "application/json", [("Content-Length", str(len(body)))])
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path.split("?")[0] != "/":
            self._hdr(404, "text/plain", [("Content-Length", "3")])
            self.end_headers()
            self.wfile.write(b"n/a")
            return
        q = queue.Queue(maxsize=256)
        with _lock:
            _subs.add(q)
            head = bytes(_tail)
        try:
            self._hdr(200, "audio/mpeg")
            self.end_headers()
            if head:
                self.wfile.write(b"%x\r\n%s\r\n" % (len(head), head))
            while not _stop.is_set():
                try:
                    blk = q.get(timeout=30)
                    self.wfile.write(b"%x\r\n%s\r\n" % (len(blk), blk))
                except queue.Empty:
                    self.wfile.write(b"0\r\n\r\n")
                    return
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            self.wfile.flush()
            with _lock:
                _subs.discard(q)


def main():
    if not SOURCE:
        print("RLY_SOURCE is required", file=sys.stderr)
        sys.exit(1)
    # Flask-style graceful shutdown on SIGTERM is handled by systemd kill; loop exit is best-effort.
    threading.Thread(target=_pull, daemon=True).start()
    srv = ThreadingHTTPServer((BIND, PORT), Handler)
    print("relay listening on %s:%s <- %s" % (BIND, PORT, SOURCE), flush=True)
    try:
        srv.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        _stop.set()
        srv.server_close()


if __name__ == "__main__":
    main()