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
    "esc to interrupt",  # OpenCode's actual in-flight hint text
)

# A pane whose content changed within this many seconds counts as
# active even without a recognized marker -- a working OpenCode TUI
# redraws its spinner/status constantly, while an idle one is static.
RECENT_CHANGE_SECONDS = 3.0

# Subset of markers that indicate output is being produced (the reply
# leg of the round trip) rather than the request being worked on.
RESPONSE_MARKERS = ("generating",)

# How long a fresh burst of activity counts as the UPLOAD phase before
# settling into PROCESSING.
UPLOAD_SECONDS = 2.0


class AIActivityState(str, Enum):
    ACTIVE = "ACTIVE"
    IDLE = "IDLE"
    OFFLINE = "OFFLINE"
    ERROR = "ERROR"


class AIFlowPhase(str, Enum):
    """Direction/meaning of the animated Earth <-> AI Core data flow.

    Derived purely from observable signals (visible OpenCode status
    words, service state) -- never from model internals.
    """

    IDLE = "IDLE"
    UPLOAD = "UPLOAD"
    PROCESSING = "PROCESSING"
    RESPONSE = "RESPONSE"
    ERROR = "ERROR"


@dataclass(frozen=True)
class PaneObservation:
    """What the last pane capture showed, without any pane content."""

    active: bool = False
    response_marker: bool = False
    active_seconds: float = 0.0
    changed_recently: bool = False


def has_active_marker(pane: str, final_lines: int = FINAL_LINES) -> bool:
    """True when the last visible lines of a pane capture contain a
    recognized in-flight status indicator."""
    lines = [line for line in pane.splitlines() if line.strip()]
    tail = "\n".join(lines[-final_lines:]).lower()
    return any(marker in tail for marker in ACTIVE_MARKERS)


def has_response_marker(pane: str, final_lines: int = FINAL_LINES) -> bool:
    """True when the final visible lines indicate output is being
    generated (the reply leg), as opposed to the request being worked on."""
    lines = [line for line in pane.splitlines() if line.strip()]
    tail = "\n".join(lines[-final_lines:]).lower()
    return any(marker in tail for marker in RESPONSE_MARKERS)


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
    recent_window: float = RECENT_CHANGE_SECONDS
    _last_pane: Optional[str] = None
    _content_since: Optional[float] = None
    _last_seen_change: Optional[float] = None
    _next_poll: float = 0.0
    _opencode_active: bool = False
    _active_since: Optional[float] = None
    _response_marker: bool = False

    def update(self, pane: Optional[str], now: float) -> bool:
        """Fold one pane capture into the monitor state.

        Pure with respect to I/O -- callers (and tests) supply the
        capture and the clock. Returns whether OpenCode looks active.

        Active means either of two observable signals:
        - a recognized status marker in the final visible lines, no
          older than ``stale_after`` (so frozen output stops matching);
        - the pane content actually changed within ``recent_window``
          (a working TUI redraws constantly; the very first capture is
          a baseline, not a change).
        """
        if pane is None:
            self._last_pane = None
            self._content_since = None
            self._last_seen_change = None
            self._opencode_active = False
            self._active_since = None
            self._response_marker = False
            return False
        if self._last_pane is None:
            self._last_pane = pane
            self._content_since = now
        elif pane != self._last_pane:
            self._last_pane = pane
            self._content_since = now
            self._last_seen_change = now

        marker_fresh = (
            has_active_marker(pane)
            and self._content_since is not None
            and (now - self._content_since) <= self.stale_after
        )
        changed_recently = (
            self._last_seen_change is not None
            and (now - self._last_seen_change) <= self.recent_window
        )
        active = marker_fresh or changed_recently
        if active and not self._opencode_active:
            self._active_since = now
        elif not active:
            self._active_since = None
        self._opencode_active = active
        self._response_marker = active and has_response_marker(pane)
        return self._opencode_active

    @property
    def pane_seen(self) -> bool:
        """Whether the most recent capture actually returned a pane --
        proof the tmux session exists, independent of list-sessions."""
        return self._last_pane is not None

    def observation(self, now: float) -> PaneObservation:
        """Snapshot of the latest pane state for flow-phase derivation."""
        active_seconds = 0.0
        if self._opencode_active and self._active_since is not None:
            active_seconds = max(0.0, now - self._active_since)
        changed_recently = (
            self._last_seen_change is not None
            and (now - self._last_seen_change) <= self.recent_window
        )
        return PaneObservation(
            active=self._opencode_active,
            response_marker=self._response_marker,
            active_seconds=active_seconds,
            changed_recently=changed_recently,
        )

    def poll(self, now: float) -> bool:
        """Rate-limited capture + update; at most one tmux call per
        ``poll_interval`` seconds, otherwise returns the cached answer."""
        if now < self._next_poll:
            return self._opencode_active
        self._next_poll = now + self.poll_interval
        return self.update(capture_pane(self.session), now)


def flow_phase(state: AIActivityState, obs: PaneObservation) -> AIFlowPhase:
    """Map the observable activity state to a data-flow phase.

    - A fresh burst of activity reads as UPLOAD (request going up).
    - Sustained activity reads as PROCESSING (Earth -> AI Core).
    - A visible response indicator reads as RESPONSE (AI Core -> Earth).
    - Everything else keeps the link quiet.
    """
    if state == AIActivityState.ERROR:
        return AIFlowPhase.ERROR
    if state != AIActivityState.ACTIVE or not obs.active:
        return AIFlowPhase.IDLE
    if obs.response_marker:
        return AIFlowPhase.RESPONSE
    if obs.active_seconds < UPLOAD_SECONDS:
        return AIFlowPhase.UPLOAD
    return AIFlowPhase.PROCESSING


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
