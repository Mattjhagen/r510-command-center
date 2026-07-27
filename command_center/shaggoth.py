"""Shaggoth AI service, curiosity, and knowledge-base status detection.

Shaggoth is the self-hosted AI running on this box. Unlike Ollama, which
either serves a model or does not, Shaggoth has a second axis worth
watching: it is supposed to be *continuously learning*. A daemon that
answers ``/health`` but whose curiosity scheduler thread has died is
technically up and quietly useless, so the two are reported separately.

State is derived from three independent signals:

1. ``systemctl is-active shaggoth`` -- is the unit itself running?
2. ``/health`` -- is the HTTP daemon actually answering?
3. ``/curiosity/scheduler`` and ``/curiosity/status`` -- is the background
   learning loop alive, and has it accumulated any knowledge?

Every HTTP call uses a short timeout so a hung daemon can never freeze the
render loop, and every parse tolerates missing or malformed fields --
Shaggoth is a fast-moving codebase and the dashboard should degrade to
"unknown" rather than crash when a payload shape shifts.
"""
from __future__ import annotations

import json
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

DEFAULT_TIMEOUT = 0.6
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8420

# A scheduler that has not researched anything in this long is reported as
# STALLED even though its thread is alive -- catches the case where the
# trigger threshold is never met and nothing is actually being learned.
STALLED_AFTER_SECONDS = 6 * 60 * 60


class ShaggothState(str, Enum):
    LEARNING = "LEARNING"  # serving requests and actively researching
    ONLINE = "ONLINE"      # serving requests, curiosity loop healthy but idle
    STALLED = "STALLED"    # serving requests, curiosity loop not progressing
    IDLE = "IDLE"          # serving requests, no knowledge accumulated yet
    OFFLINE = "OFFLINE"    # not running
    ERROR = "ERROR"        # unit active but API unreachable


@dataclass
class ShaggothStatus:
    """A point-in-time snapshot of Shaggoth's health and learning progress."""

    state: ShaggothState = ShaggothState.OFFLINE
    version: str = "-"
    detail: str = ""

    # Curiosity / learning loop
    scheduler_enabled: bool = False
    scheduler_alive: bool = False
    interval_minutes: int = 0
    buffered_messages: int = 0
    is_researching: bool = False
    current_topic: str = ""
    total_episodes: int = 0
    last_episode_age_seconds: Optional[float] = None

    # Knowledge base
    knowledge_entries: int = 0
    stale_entries: int = 0
    fresh_entries: int = 0

    # Scraper
    pages_stored: int = 0
    total_words: int = 0
    seeds_pending: int = 0
    scrape_errors: int = 0
    last_scrape_error: str = ""

    @property
    def is_up(self) -> bool:
        return self.state not in (ShaggothState.OFFLINE, ShaggothState.ERROR)

    @property
    def learning_healthy(self) -> bool:
        """True when the background learning loop is genuinely progressing."""
        return self.scheduler_enabled and self.scheduler_alive and self.state is not ShaggothState.STALLED

    @property
    def summary(self) -> str:
        """One-line human summary for the dashboard status strip."""
        if not self.is_up:
            return self.detail or "offline"
        if self.is_researching and self.current_topic:
            return f"researching {self.current_topic}"
        return f"{self.knowledge_entries} topics · {self.total_words:,} words"


def systemctl_is_active(service: str = "shaggoth", timeout: float = 2.0) -> Optional[bool]:
    """Return ``True``/``False`` for a known systemctl state, or ``None`` if
    systemctl itself is unavailable (missing binary, non-systemd host, or the
    check times out).
    """
    try:
        result = subprocess.run(
            ["systemctl", "is-active", service],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None
    return result.stdout.strip() == "active"


def _http_get_json(url: str, timeout: float) -> Optional[dict]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:  # noqa: S310 - local API only
            if response.status != 200:
                return None
            payload = response.read().decode("utf-8")
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return None
    try:
        data = json.loads(payload)
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def _as_int(value: Any, default: int = 0) -> int:
    """Coerce a payload field to int, tolerating strings, floats, and None."""
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        try:
            return int(float(value))
        except ValueError:
            return default
    return default


def _as_dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def parse_scheduler_response(data: Optional[dict]) -> dict:
    """Extract scheduler health from a ``/curiosity/scheduler`` payload."""
    data = _as_dict(data)
    return {
        "enabled": bool(data.get("enabled", False)),
        "alive": bool(data.get("thread_alive", False)),
        "interval_minutes": _as_int(data.get("interval_minutes")),
        "buffered_messages": _as_int(data.get("buffered_messages")),
    }


def parse_curiosity_response(data: Optional[dict], now: float) -> dict:
    """Extract learning progress from a ``/curiosity/status`` payload.

    Handles both the flat and nested shapes Shaggoth has used for
    ``current_episode``/``last_episode`` -- either a bare topic string or an
    object carrying ``topic`` and ``started_at``.
    """
    data = _as_dict(data)
    scraper = _as_dict(data.get("scraper_stats"))
    freshness = _as_dict(data.get("freshness"))

    current = data.get("current_episode")
    if isinstance(current, dict):
        current_topic = str(current.get("topic") or "")
    elif isinstance(current, str):
        current_topic = current
    else:
        current_topic = ""

    last = data.get("last_episode")
    last_age: Optional[float] = None
    if isinstance(last, dict):
        started = last.get("started_at") or last.get("finished_at")
        if isinstance(started, (int, float)) and started > 0:
            last_age = max(0.0, now - float(started))

    last_error = scraper.get("last_error")

    return {
        "is_researching": bool(data.get("is_running", False)),
        "current_topic": current_topic,
        "total_episodes": _as_int(data.get("total_episodes")),
        "last_episode_age_seconds": last_age,
        "knowledge_entries": _as_int(data.get("knowledge_entries")),
        "stale_entries": _as_int(freshness.get("stale_count")),
        "fresh_entries": _as_int(freshness.get("fresh_count")),
        "pages_stored": _as_int(scraper.get("pages_stored")),
        "total_words": _as_int(scraper.get("total_words")),
        "seeds_pending": _as_int(scraper.get("seeds_pending")),
        "scrape_errors": _as_int(scraper.get("errors")),
        "last_scrape_error": str(last_error) if last_error else "",
    }


def _classify(
    scheduler: dict,
    curiosity: dict,
    stalled_after: float,
) -> tuple[ShaggothState, str]:
    """Decide the headline state from the two health payloads."""
    if curiosity["is_researching"]:
        return ShaggothState.LEARNING, ""

    if not scheduler["enabled"]:
        return ShaggothState.STALLED, "curiosity scheduler disabled"

    if not scheduler["alive"]:
        return ShaggothState.STALLED, "curiosity thread not alive"

    if curiosity["knowledge_entries"] <= 0:
        return ShaggothState.IDLE, "no knowledge acquired yet"

    age = curiosity["last_episode_age_seconds"]
    if age is not None and age > stalled_after:
        hours = int(age // 3600)
        return ShaggothState.STALLED, f"no research in {hours}h"

    return ShaggothState.ONLINE, ""


def get_status(
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    timeout: float = DEFAULT_TIMEOUT,
    service: str = "shaggoth",
    now: Optional[float] = None,
    stalled_after: float = STALLED_AFTER_SECONDS,
) -> ShaggothStatus:
    """Determine Shaggoth's current state.

    - ``OFFLINE``: the systemd unit is confirmed not active, or nothing is
      answering on the API port.
    - ``ERROR``: the unit is active but ``/health`` cannot be reached --
      typically a crash-loop or a port collision with a stray manual process.
    - ``IDLE``: serving requests but the knowledge base is still empty.
    - ``STALLED``: serving requests, but the curiosity loop is disabled, its
      thread is dead, or it has not researched anything in ``stalled_after``
      seconds. This is the interesting failure mode -- up but not learning.
    - ``LEARNING``: a research episode is running right now.
    - ``ONLINE``: healthy and idle between research cycles.

    Always returns promptly regardless of the daemon's actual health.
    """
    import time

    now = time.time() if now is None else now
    base_url = f"http://{host}:{port}"
    active = systemctl_is_active(service)

    health = _http_get_json(f"{base_url}/health", timeout)
    if health is None:
        if active:
            return ShaggothStatus(
                state=ShaggothState.ERROR,
                detail="service active but API unreachable",
            )
        return ShaggothStatus(
            state=ShaggothState.OFFLINE,
            detail="shaggoth API unreachable",
        )

    scheduler = parse_scheduler_response(
        _http_get_json(f"{base_url}/curiosity/scheduler", timeout)
    )
    curiosity = parse_curiosity_response(
        _http_get_json(f"{base_url}/curiosity/status", timeout), now
    )

    state, detail = _classify(scheduler, curiosity, stalled_after)

    return ShaggothStatus(
        state=state,
        version=str(health.get("version") or "-"),
        detail=detail,
        scheduler_enabled=scheduler["enabled"],
        scheduler_alive=scheduler["alive"],
        interval_minutes=scheduler["interval_minutes"],
        buffered_messages=scheduler["buffered_messages"],
        is_researching=curiosity["is_researching"],
        current_topic=curiosity["current_topic"],
        total_episodes=curiosity["total_episodes"],
        last_episode_age_seconds=curiosity["last_episode_age_seconds"],
        knowledge_entries=curiosity["knowledge_entries"],
        stale_entries=curiosity["stale_entries"],
        fresh_entries=curiosity["fresh_entries"],
        pages_stored=curiosity["pages_stored"],
        total_words=curiosity["total_words"],
        seeds_pending=curiosity["seeds_pending"],
        scrape_errors=curiosity["scrape_errors"],
        last_scrape_error=curiosity["last_scrape_error"],
    )
