#!/usr/bin/env python3
"""Poll Broadcastify Calls for Omaha ORION clips and feed new ones to Whisper.

The live-calls API accepts exactly ONE groups[] entry per request (multi-group
requests 502). We round-robin over the configured talkgroups so all monitored
channels contribute traffic.
"""

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ENV_PATH = Path(os.environ.get("BCFY_ENV", "/tmp/opencode/r510/bcfy_session.env"))
API = "https://www.broadcastify.com/calls/apis/live-calls"
WHISPER = os.environ.get("WHISPER_URL", "http://127.0.0.1:8424")
HUB = os.environ.get("HUB_URL", "http://127.0.0.1:8898")
LOG = HERE / "calls-poller.log"
POLL_S = float(os.environ.get("POLL_S", "6"))
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    " (KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36"
)

_session = {}
_seen = set()
_errors = 0

POS_FILE = Path("/tmp/r510-bcfy-pos")


def _load_pos() -> int:
    try:
        return int(POS_FILE.read_text().strip() or 0)
    except Exception:
        return 0


def _save_pos(pos: int) -> None:
    try:
        POS_FILE.write_text(str(pos))
    except OSError:
        pass


def log(msg: str):
    line = "%s %s" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg)
    with LOG.open("a") as f:
        f.write(line + "\n")
    print(line, flush=True)


def load_session():
    for raw in ENV_PATH.read_text().splitlines():
        raw = raw.strip()
        if not raw or raw.startswith("#") or "=" not in raw:
            continue
        k, _, v = raw.partition("=")
        v = v.strip().strip("'").strip('"')
        if not v or v == "0":
            continue
        k = k.lower()
        if k.startswith("bcfy_"):
            _session[k] = v


def groups() -> list:
    raw = os.environ.get("BCFY_GROUPS", _session.get("bcfy_groups", "2361-458"))
    return [g.strip() for g in raw.split(",") if "-" in g]


def api_post(pos: int, do_init: int, group: str) -> dict:
    body = urllib.parse.urlencode({
        "groups[]": group,
        "pos": pos,
        "doInit": do_init,
        "systemId": _session.get("bcfy_systemid", "0"),
        "sid": _session.get("bcfy_sid", "0"),
        "sessionKey": _session.get("bcfy_sessionkey", ""),
    }).encode()
    req = urllib.request.Request(API, data=body, method="POST")
    req.add_header("content-type", "application/x-www-form-urlencoded; charset=UTF-8")
    req.add_header("x-requested-with", "XMLHttpRequest")
    req.add_header("referer", "https://www.broadcastify.com/calls/tg/2361/458")
    req.add_header("origin", "https://www.broadcastify.com")
    req.add_header("user-agent", UA)
    if _session.get("bcfy_cookie"):
        req.add_header("cookie", _session["bcfy_cookie"])
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode())


def fetch_clip(system_id: int, hash_: str, filename: str, enc: str) -> bytes:
    url = "https://calls.broadcastify.com/%s/%s/%s.%s" % (hash_, system_id, filename, enc)
    req = urllib.request.Request(url)
    req.add_header("user-agent", UA)
    req.add_header("referer", "https://www.broadcastify.com/calls/tg/2361/458")
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read()


def send_to_whisper(mp3: bytes) -> str:
    boundary = "----whisperpoller"
    body = (
        ("--%s\r\n" % boundary).encode()
        + b'Content-Disposition: form-data; name="audio"; filename="clip.mp3"\r\n'
        + b"Content-Type: audio/mpeg\r\n\r\n"
        + mp3
        + b"\r\n"
        + ("--%s--\r\n" % boundary).encode()
    )
    req = urllib.request.Request(
        WHISPER + "/transcribe?language=en",
        data=body,
        method="POST",
        headers={"Content-Type": "multipart/form-data; boundary=%s" % boundary},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())["text"]


def send_to_hub(mp3: bytes) -> None:
    req = urllib.request.Request(
        HUB + "/clip",
        data=mp3,
        method="POST",
        headers={"Content-Type": "audio/mpeg"},
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        json.loads(r.read().decode())


def main():
    load_session()
    if not _session.get("bcfy_cookie"):
        log("FATAL: no bcfy_cookie in %s" % ENV_PATH)
        return
    grp = groups()
    log("poller start groups=%s cookie_len=%d sessionKey=%s..." % (
        ",".join(grp), len(_session.get("bcfy_cookie", "")),
        _session.get("bcfy_sessionkey", "")[:8]))

    baseline = _load_pos()
    first = not baseline
    processed = 0

    def poll_group(g: str) -> None:
        nonlocal baseline, first, processed
        try:
            data = api_post(baseline, 1 if first else 0, g)
            first = False
        except urllib.error.HTTPError as e:
            log("API HTTP %s %s (session may need refreshing from browser DevTools) g=%s" % (e.code, e.reason, g))
            return
        except Exception as e:
            log("poller err: %s: %s" % (type(e).__name__, e))
            return
        last_pos = data.get("lastPos") or 0
        if last_pos > baseline:
            baseline = last_pos
            _save_pos(last_pos)
        calls = data.get("calls", [])
        if not calls:
            return
        tg = int(g.split("-")[1])
        new_calls = [c for c in calls if c.get("ts", 0) > 0 and c.get("call_tg") == tg]
        new_calls.sort(key=lambda c: c.get("ts", 0))
        for c in new_calls:
            key = (c.get("ts"), c.get("filename"))
            if key in _seen:
                continue
            _seen.add(key)
            try:
                mp3 = fetch_clip(
                    c.get("systemId", 3563), c.get("hash", ""),
                    c.get("filename", ""), c.get("enc", "mp3"))
                if not mp3 or len(mp3) < 1000:
                    log("tiny/missing clip (%dB) g=%s ts=%d" % (len(mp3), g, c.get("ts")))
                    continue
                try:
                    send_to_hub(mp3)
                except Exception as e:
                    log("hub push err g=%s ts=%d %s: %s" % (g, c.get("ts"), type(e).__name__, e))
                text = send_to_whisper(mp3)
                processed += 1
                log("[%d] %s dur=%ss -> %s" % (
                    processed, g, c.get("call_duration"), text[:160]))
            except Exception as e:
                log("clip/whisper err g=%s ts=%d %s: %s" % (g, c.get("ts"), type(e).__name__, e))

    fast = set()
    for f in (os.environ.get("BCFY_FAST_GROUPS", ""), _session.get("bcfy_fast_groups", "")):
        if f:
            fast |= {x.strip() for x in f.split(",") if x.strip()}
    interval = {g: (5 if g in fast else 15) for g in grp}
    next_poll = {g: 0.0 for g in grp}
    log("poll cadence fast=%s every 5s, others 15s" % ("," .join(sorted(fast)) if fast else "none"))
    while True:
        now = time.time()
        for g in grp:
            if now >= next_poll[g]:
                try:
                    poll_group(g)
                except Exception as e:
                    log("poller fatal-ish err: %s: %s" % (type(e).__name__, e))
                next_poll[g] = time.time() + interval[g]
        time.sleep(1.5)


if __name__ == "__main__":
    main()