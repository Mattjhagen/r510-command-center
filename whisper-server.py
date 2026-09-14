#!/usr/bin/env python3
"""R510 Whisper transcription server (port 8424).

Two ingestion paths, ONE display buffer:

  A) Server-side puller  (WHISPER_STREAM_URL / STREAM_URL if set):
     streams an ICEcast/HTTP audio URL, windows it, transcribes, appends to buffer.
  B) Browser capture     POST /transcribe (raw PCM or wav/ogg/mp3/webm):
     the dashboard captures audio and posts chunks; results are appended too.

The dashboard polls GET /transcripts?since=<seq> and renders only real entries.

Model: Systran/faster-whisper-tiny.en (CPU int8). Env:
  WHISPER_STREAM_URL  optional radio stream URL to pull server-side
  WHISPER_HOST/PORT   default 0.0.0.0:8424
"""
import io
import itertools
import logging
import os
import tempfile
import threading
import time
from collections import deque
from pathlib import Path

import numpy as np
import uvicorn
from fastapi import FastAPI, File, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from faster_whisper import WhisperModel
from faster_whisper.audio import decode_audio

log = logging.getLogger("r510-whisper")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

SR = 16000
MODEL_NAME = "Systran/faster-whisper-tiny.en"
WINDOW_SECONDS = 12.0
MAX_WINDOW_BYTES = 600_000
_LOADED = {"model": None, "at": None, "lock": threading.Lock()}

_buf = deque(maxlen=100)
_buf_lock = threading.Lock()
_ENTRY_TTL = 90.0  # seconds a transcript stays visible

_SEQ_FILE = Path(os.environ.get("WHISPER_SEQ_FILE", "/tmp/r510-whisper-seq"))
_seq_lock = threading.Lock()
try:
    _seq_start = int(_SEQ_FILE.read_text().strip() or 0)
except FileNotFoundError:
    _seq_start = 0
_bseq = itertools.count(_seq_start + 1)


def _next_seq() -> int:
    n = next(_bseq)
    with _seq_lock:
        try:
            _SEQ_FILE.write_text(str(n))
        except OSError:
            pass
    return n


def _prune():
    now = time.time()
    with _buf_lock:
        while _buf and now - _buf[0]["ts"] > _ENTRY_TTL:
            _buf.popleft()


class Health(BaseModel):
    ok: bool
    model: str
    ready: bool
    load_time_s: float = 0.0


app = FastAPI(title="R510 Whisper API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def load_model():
    if _LOADED["model"] is None:
        with _LOADED["lock"]:
            if _LOADED["model"] is None:
                t = time.time()
                _LOADED["model"] = WhisperModel(MODEL_NAME, device="cpu", compute_type="int8", cpu_threads=4)
                _LOADED["at"] = time.time() - t
                log.info("model loaded in %.1fs", _LOADED["at"])
    return _LOADED["model"]


def _append(entry: dict) -> int:
    entry.setdefault("ts", time.time())
    with _buf_lock:
        _buf.append(entry)
        while _buf and time.time() - _buf[0]["ts"] > _ENTRY_TTL:
            _buf.popleft()
        return entry["seq"]


def _runner(arr: np.ndarray, language: str) -> str:
    model = load_model()
    segments, info = model.transcribe(
        arr,
        language=language,
        beam_size=1,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 300},
    )
    return " ".join(seg.text.strip() for seg in segments).strip()


def _transcribe_and_store(arr: np.ndarray, source: str, language: str = "en") -> str:
    text = _runner(arr, language)
    if text:
        _append({"seq": _next_seq(), "time": time.strftime("%H:%M:%S"),
                 "text": text, "duration": round(float(len(arr) / SR), 1),
                 "source": source})
        log.info("[%s] %s", source, text[:90])
    return text


# ---------------------------------------------------------------- browser path
@app.get("/health")
def health() -> Health:
    return Health(ok=True, model=MODEL_NAME, ready=_LOADED["model"] is not None, load_time_s=_LOADED["at"] or 0.0)


@app.get("/transcripts")
def transcripts(since: int = Query(0)):
    _prune()
    with _buf_lock:
        entries = [e for e in _buf if e["seq"] > since]
    return {"entries": entries, "ttl_s": _ENTRY_TTL}


@app.get("/status")
def status():
    return {
        "ok": True,
        "ready": _LOADED["model"] is not None,
        "entries": len(_buf),
        "stream": os.environ.get("WHISPER_STREAM_URL", ""),
        "stream_alive": _STREAM.get("alive", False),
        "stream_last": _STREAM.get("last", None),
        "stream_err": _STREAM.get("err", None),
    }


def _to_float32(raw: bytes, sr: int, fmt: str) -> np.ndarray:
    if fmt == "f32":
        return np.frombuffer(raw, dtype=np.float32).astype(np.float32)
    return (np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0).astype(np.float32)


def _looks_encoded(raw: bytes) -> bool:
    for magic in (b"RIFF", b"OggS", b"fLaC", b"\x1a\x45\xdf\xa3", b"ID3"):
        if raw.startswith(magic):
            return True
    if len(raw) >= 2 and raw[0] == 0xFF and (raw[1] & 0xE0) == 0xE0:  # MP3 frame sync
        return True
    return False


@app.post("/transcribe")
def transcribe(
    audio: bytes = File(..., description="audio bytes (raw PCM or wav/ogg/mp3/webm)"),
    fmt: str = Query("i16"),
    sr: int = Query(SR),
    language: str = Query("en"),
):
    if _looks_encoded(audio) and not audio.startswith(b"RIFF"):
        with tempfile.NamedTemporaryFile(suffix=".bin") as tf:
            tf.write(audio)
            tf.flush()
            arr = decode_audio(Path(tf.name), sampling_rate=SR)
    elif audio.startswith(b"RIFF"):
        arr = decode_audio(io.BytesIO(audio), sampling_rate=SR)
    else:
        arr = _to_float32(audio, sr, fmt)
    text = _transcribe_and_store(arr, "browser", language)
    return {"text": text, "language": language, "duration": round(len(arr) / SR, 2)}


# ------------------------------------------------------------- server pull path
_STREAM = {"alive": False, "last": None, "err": None, "lock": threading.Lock()}


def _set_stream(**kw):
    with _STREAM["lock"]:
        _STREAM.update(kw)


def _process_window(data: bytes):
    if len(data) < SR // 2:  # less than ~0.5s, skip
        return
    try:
        arr = decode_audio(io.BytesIO(data), sampling_rate=SR)
    except Exception as e:  # truncated frames mid-decode
        log.debug("decode skip: %s", e)
        return
    rms = float(np.sqrt(np.mean(arr ** 2))) if len(arr) else 0.0
    if rms < 0.004:
        return  # silence
    _transcribe_and_store(arr, "stream")


def _pull_stream(url: str):
    import urllib.request

    while True:
        try:
            _set_stream(alive=True, err=None)
            req = urllib.request.Request(url, headers={"User-Agent": "R510-Command-Center/1.0", "Icy-MetaData": "0"})
            with urllib.request.urlopen(req, timeout=15) as r:
                log.info("stream connected: %s", url)
                buf = bytearray()
                window_start = time.time()
                last_seen = None
                while True:
                    try:
                        chunk = r.read(4096)
                        eof = not chunk
                    except TimeoutError:
                        chunk = b""
                        eof = False
                    if chunk:
                        buf.extend(chunk)
                        last_seen = time.time()
                        _set_stream(last=time.strftime("%H:%M:%S"), alive=True)
                    now = time.time()
                    if buf and (len(buf) >= MAX_WINDOW_BYTES or now - window_start >= WINDOW_SECONDS):
                        _process_window(bytes(buf))
                        buf = bytearray()
                        window_start = now
                    if eof:
                        log.info("stream ended")
                        if buf:
                            _process_window(bytes(buf))
                            buf = bytearray()
                        break
                    if not chunk and (last_seen is None or now - last_seen > 20):
                        log.info("stream stalled; reconnecting")
                        break
        except Exception as e:
            _set_stream(alive=False, err=str(e)[:120])
            log.warning("stream error: %s", e)
        time.sleep(5)


_win_start = {"t": None}


@app.on_event("startup")
def _startup():
    url = os.environ.get("WHISPER_STREAM_URL", "").strip()
    if url:
        t = threading.Thread(target=_pull_stream, args=(url,), daemon=True)
        t.start()
        log.info("stream puller started: %s", url)


if __name__ == "__main__":
    load_model()
    uvicorn.run(app, host=os.environ.get("WHISPER_HOST", "0.0.0.0"),
                port=int(os.environ.get("WHISPER_PORT", "8424")))