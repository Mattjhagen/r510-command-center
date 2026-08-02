"""Generative dialogue between Earth and the AI core.

Now powered by a local Ollama model generating deep factual questions
which are sent to Shaggoth for 24/7 continuous learning.
"""
from __future__ import annotations

import json
import re
import threading
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Optional

EARTH = 0   # asks (Ollama)
CORE = 1    # Shaggoth answers

DEFAULT_TURN_SECONDS = 60.0
DEFAULT_TIMEOUT = 20.0
MAX_LINES = 24
MAX_BUBBLE_CHARS = 110

_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")

def condense(text: str, max_chars: int = MAX_BUBBLE_CHARS) -> str:
    """Reduce a reply to the most it can say inside one speech bubble."""
    text = " ".join((text or "").split())
    if not text:
        return ""
    if len(text) <= max_chars:
        return text

    out = ""
    for sentence in _SENTENCE_END.split(text):
        candidate = f"{out} {sentence}".strip()
        if len(candidate) > max_chars:
            break
        out = candidate
    if out:
        return out

    clipped = text[:max_chars].rsplit(" ", 1)[0]
    return (clipped or text[:max_chars]).rstrip(",;:") + "…"

@dataclass
class ConversationState:
    """Snapshot handed to the renderer. Never mutated by the reader."""
    lines: list = field(default_factory=list)
    turn: int = 0
    live: bool = False

class ConversationEngine:
    """Drives the drifting dialogue on a background thread using Ollama."""
    def __init__(
        self,
        base_url: str,
        ollama_host: str = "127.0.0.1",
        ollama_port: int = 11434,
        ollama_model: str = "qwen2.5-coder:7b",
        turn_seconds: float = DEFAULT_TURN_SECONDS,
        timeout: float = DEFAULT_TIMEOUT,
        session_id: str = "ollama-tutor",
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._ollama_url = f"http://{ollama_host}:{ollama_port}/api/generate"
        self._ollama_model = ollama_model
        self._turn_seconds = max(5.0, turn_seconds)
        self._timeout = timeout
        self._session_id = session_id

        self._lock = threading.Lock()
        self._lines: list = []
        self._turn = 0
        self._live = False
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run, name="shaggoth-dialogue", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def script(self) -> list:
        with self._lock:
            return list(self._lines)

    @property
    def live(self) -> bool:
        with self._lock:
            return self._live

    def _append(self, speaker: int, text: str) -> None:
        text = condense(text)
        if not text:
            return
        with self._lock:
            self._lines.append((speaker, text))
            if len(self._lines) > MAX_LINES:
                del self._lines[: len(self._lines) - MAX_LINES]

    def _ask_ollama(self) -> str:
        prompt = "Generate a single, random, obscure but interesting factual question about science, history, engineering, or technology. Output ONLY the question text, no conversational filler or preamble."
        payload = json.dumps({
            "model": self._ollama_model,
            "prompt": prompt,
            "stream": False
        }).encode()
        request = urllib.request.Request(
            self._ollama_url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:  # noqa: S310
                body = json.loads(response.read().decode("utf-8"))
                return str(body.get("response", "")).strip()
        except Exception:
            return ""

    def _ask_shaggoth(self, message: str) -> str:
        payload = json.dumps({
            "message": message,
            "session_id": self._session_id,
            "research": True,
        }).encode()
        request = urllib.request.Request(
            f"{self._base_url}/chat",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:  # noqa: S310
                body = json.loads(response.read().decode("utf-8"))
                return str(body.get("reply", "")).strip()
        except Exception:
            return ""

    def _run(self) -> None:
        while not self._stop.is_set():
            question = self._ask_ollama()
            if question:
                self._append(EARTH, question)
                reply = self._ask_shaggoth(question)
                if reply:
                    self._append(CORE, reply)
                    with self._lock:
                        self._live = True
                        self._turn += 1
                else:
                    with self._lock:
                        self._live = False
            else:
                with self._lock:
                    self._live = False
            self._stop.wait(self._turn_seconds)
