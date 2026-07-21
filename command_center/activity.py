"""Honest AI activity detection from observable signals.

A loaded model in Ollama's ``/api/ps`` only means the model is resident
in memory, not that anything is being generated -- and OpenCode requests
against ``:cloud`` models never show up there at all. So instead of
guessing from the API, activity is detected by looking at what is
actually visible: the OpenCode tmux pane. When its final visible lines
show a recognized status indicator (``Thinking``, ``Generating``,
``esc interrupt``, ...) and the pane has changed recently, work is in
progress.

Only coarse status words from the interface chrome are inspected; no
prompt or response content is ever parsed, stored, or displayed.
"""
from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from .ollama import OllamaState

CAPTURE_TIMEOUT = 0.5
CAPTURE_LINES = 30
POLL_INTERVAL = 1.0
STALE_SECONDS = 10.0
FINAL_LINES = 8

# Status words OpenCode shows in its interface while a request is in
# flight. Matched case-insensitively against the final visible lines.
ACTIVE_MARKERS = (
    "build",
    "thinking",
    "processing",
    "generating",
    "working",
    "running tool",
    "esc interrupt",
)


class AIActivityState(str, Enum):
    ACTIVE = "ACTIVE"
    IDLE = "IDLE"
    OFFLINE = "OFFLINE"
    ERROR = "ERROR"


def has_active_marker(pane: str, final_lines: int = FINAL_LINES) -> bool:
    """True when the last visible lines of a pane capture contain a
    recognized in-flight status indicator."""
    lines = [line for line in pane.splitlines() if line.strip()]
    tail = "\n".join(lines[-final_lines:]).lower()
    return any(marker in tail for marker in ACTIVE_MARKERS)


def capture_pane(session: str, timeout: float = CAPTURE_TIMEOUT) -> Optional[str]:
    """Capture the recent visible contents of a tmux session's pane.

    Returns ``None`` when tmux is missing, the session does not exist,
    or the capture times out.
    """
    if shutil.which("tmux") is None:
        return None
    try:
        result = subprocess.run(
            ["tmux", "capture-pane", "-p", "-t", session, "-S", f"-{CAPTURE_LINES}"],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    return result.stdout


@dataclass
class ActivityMonitor:
    """Tracks OpenCode activity across polls without threads.

    Remembers the previous pane capture so a status word frozen on
    screen (e.g. an interrupted session left showing ``Thinking``)
    stops counting as active once the pane has been unchanged for
    ``stale_after`` seconds.
    """

    session: str
    poll_interval: float = POLL_INTERVAL
    stale_after: float = STALE_SECONDS
    _last_pane: Optional[str] = None
    _last_change: Optional[float] = None
    _next_poll: float = 0.0
    _opencode_active: bool = False

    def update(self, pane: Optional[str], now: float) -> bool:
        """Fold one pane capture into the monitor state.

        Pure with respect to I/O -- callers (and tests) supply the
        capture and the clock. Returns whether OpenCode looks active.
        """
        if pane is None:
            self._last_pane = None
            self._last_change = None
            self._opencode_active = False
            return False
        if pane != self._last_pane:
            self._last_pane = pane
            self._last_change = now
        fresh = self._last_change is not None and (now - self._last_change) <= self.stale_after
        self._opencode_active = fresh and has_active_marker(pane)
        return self._opencode_active

    def poll(self, now: float) -> bool:
        """Rate-limited capture + update; at most one tmux call per
        ``poll_interval`` seconds, otherwise returns the cached answer."""
        if now < self._next_poll:
            return self._opencode_active
        self._next_poll = now + self.poll_interval
        return self.update(capture_pane(self.session), now)


def derive_state(ollama_state: OllamaState, opencode_active: bool) -> AIActivityState:
    """Combine the Ollama service state with observed OpenCode activity.

    OpenCode activity wins even when the local API looks quiet, because
    ``:cloud`` model requests are invisible to ``/api/ps``.
    """
    if opencode_active:
        return AIActivityState.ACTIVE
    if ollama_state == OllamaState.OFFLINE:
        return AIActivityState.OFFLINE
    if ollama_state == OllamaState.ERROR:
        return AIActivityState.ERROR
    return AIActivityState.IDLE
