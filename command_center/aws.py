"""AWS EC2 remote status collector.

Polls the Shaggoth monitor API on a remote EC2 instance over SSH tunnel
or direct HTTP, returning structured data for the unified dashboard.
Designed to degrade gracefully -- a missing or unreachable EC2 shows as
OFFLINE rather than crashing the dashboard.
"""
from __future__ import annotations

import json
import os
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


DEFAULT_TIMEOUT = 1.5


class AWSState(str, Enum):
    ONLINE   = "ONLINE"
    LEARNING = "LEARNING"
    OFFLINE  = "OFFLINE"
    ERROR    = "ERROR"


@dataclass
class AWSStatus:
    state: AWSState = AWSState.OFFLINE
    host: str = ""
    instance_type: str = "t3.small"
    region: str = "us-east-2"

    # System
    cpu_percent: float = 0.0
    ram_percent: float = 0.0
    disk_percent: float = 0.0
    uptime_seconds: float = 0.0
    load_avg: tuple = (0.0, 0.0, 0.0)
    net_rx: float = 0.0
    net_tx: float = 0.0

    # Services
    shaggoth_active: bool = False
    shaggoth_uptime: str = "-"
    cloudflared_active: bool = False
    cloudflared_uptime: str = "-"

    # Shaggoth AI
    shaggoth_version: str = "?"
    shaggoth_state: str = "OFFLINE"
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
        with urllib.request.urlopen(url, timeout=timeout) as r:
            data = json.loads(r.read().decode())
            return data if isinstance(data, dict) else None
    except Exception:
        return None


def get_status(
    base_url: str = "http://127.0.0.1:8420",
    timeout: float = DEFAULT_TIMEOUT,
) -> AWSStatus:
    """Poll the remote Shaggoth instance and return structured status."""
    now = time.time()

    health = _http_get(f"{base_url}/health", timeout)
    if not health:
        return AWSStatus(state=AWSState.OFFLINE, detail="API unreachable", last_updated=now)

    sched   = _http_get(f"{base_url}/curiosity/scheduler", timeout) or {}
    curiosity = _http_get(f"{base_url}/curiosity/status",   timeout) or {}
    sessions  = _http_get(f"{base_url}/sessions",           timeout) or {}

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

        # Shaggoth AI
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

        # Users
        active_users=int(sessions.get("active", 0)),
        total_sessions=int(sessions.get("total_sessions", 0)),
        total_messages=int(sessions.get("total_messages", 0)),
        platforms=sessions.get("platforms", {}),
    )
