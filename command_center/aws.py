"""AWS EC2 remote status collector.

Polls the Shaggoth API on a remote EC2 over Cloudflare tunnel.
Uses a background thread so slow responses never block the render loop.
Last good result is cached and shown until the next successful poll.
"""
from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


DEFAULT_TIMEOUT = 8.0
POLL_INTERVAL   = 6.0   # seconds between background polls


class AWSState(str, Enum):
    ONLINE   = "ONLINE"
    LEARNING = "LEARNING"
    OFFLINE  = "OFFLINE"
    ERROR    = "ERROR"


@dataclass
class AWSStatus:
    state: AWSState = AWSState.OFFLINE
    instance_type: str = "t3.small"
    region: str = "us-east-2"

    # Shaggoth AI
    shaggoth_version: str = "?"
    is_researching: bool = False
    current_topic: str = ""
    knowledge_entries: int = 0
    knowledge_words: int = 0
    fresh_entries: int = 0
    stale_entries: int = 0
    total_episodes: int = 0
    pages_stored: int = 0
    seeds_pending: int = 0
    scrape_errors: int = 0
    last_topic: str = "-"
    last_words: int = 0
    scheduler_alive: bool = False
    buffered_messages: int = 0

    # Users
    active_users: int = 0
    total_sessions: int = 0
    total_messages: int = 0
    platforms: dict = field(default_factory=dict)

    detail: str = ""
    last_updated: float = 0.0

    @property
    def is_up(self) -> bool:
        return self.state not in (AWSState.OFFLINE, AWSState.ERROR)

    @property
    def platform_summary(self) -> str:
        if not self.platforms:
            return ""
        return "  ".join(f"{k}:{v}" for k, v in self.platforms.items())

    @property
    def user_summary(self) -> str:
        u = self.active_users
        if u == 0:
            return "no active users"
        s = "" if u == 1 else "s"
        plat = f"  [{self.platform_summary}]" if self.platforms else ""
        return f"{u} user{s} online{plat}"


def _http_get(url: str, timeout: float = DEFAULT_TIMEOUT) -> Optional[dict]:
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (compatible; ShaggothMonitor/2.0)",
            "Accept": "application/json",
        })
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode())
            return data if isinstance(data, dict) else None
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        return None
    except Exception:
        return None


def _fetch(base_url: str) -> AWSStatus:
    """Do the full poll — called from background thread only."""
    now = time.time()

    health = _http_get(f"{base_url}/health")
    if not health:
        return AWSStatus(state=AWSState.OFFLINE, detail="API unreachable", last_updated=now)

    sched    = _http_get(f"{base_url}/curiosity/scheduler") or {}
    curiosity = _http_get(f"{base_url}/curiosity/status")   or {}
    sessions  = _http_get(f"{base_url}/sessions")           or {}

    scraper   = curiosity.get("scraper_stats", {})
    freshness = curiosity.get("freshness", {})
    last_ep   = curiosity.get("last_episode") or {}
    cur_ep    = curiosity.get("current_episode") or {}

    researching = bool(curiosity.get("is_running", False))
    cur_topic   = (cur_ep.get("topic", "") if isinstance(cur_ep, dict) else "")
    state = AWSState.LEARNING if researching else AWSState.ONLINE

    return AWSStatus(
        state=state,
        last_updated=now,
        shaggoth_version=str(health.get("version", "?")),
        is_researching=researching,
        current_topic=cur_topic,
        knowledge_entries=int(curiosity.get("knowledge_entries", 0)),
        knowledge_words=int(scraper.get("total_words", 0)),
        fresh_entries=int(freshness.get("fresh_count", 0)),
        stale_entries=int(freshness.get("stale_count", 0)),
        total_episodes=int(curiosity.get("total_episodes", 0)),
        pages_stored=int(scraper.get("pages_stored", 0)),
        seeds_pending=int(scraper.get("seeds_pending", 0)),
        scrape_errors=int(scraper.get("errors", 0)),
        last_topic=str(last_ep.get("topic", "-")),
        last_words=int(last_ep.get("words_learned", 0)),
        scheduler_alive=bool(sched.get("thread_alive", False)),
        buffered_messages=int(sched.get("buffered_messages", 0)),
        active_users=int(sessions.get("active", 0)),
        total_sessions=int(sessions.get("total_sessions", 0)),
        total_messages=int(sessions.get("total_messages", 0)),
        platforms=sessions.get("platforms", {}),
    )


class AWSPoller:
    """Background thread that keeps a cached AWSStatus fresh.

    The dashboard reads ``poller.status`` at render time — always instant,
    never blocks on a slow Cloudflare round trip.
    """

    def __init__(self, base_url: str, interval: float = POLL_INTERVAL) -> None:
        self._base_url = base_url
        self._interval = interval
        self._status   = AWSStatus()
        self._lock     = threading.Lock()
        self._thread   = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    @property
    def status(self) -> AWSStatus:
        with self._lock:
            return self._status

    def _loop(self) -> None:
        while True:
            result = _fetch(self._base_url)
            with self._lock:
                self._status = result
            time.sleep(self._interval)


# Convenience wrapper kept for callers that don't want the poller
def get_status(base_url: str, timeout: float = DEFAULT_TIMEOUT) -> AWSStatus:
    return _fetch(base_url)
