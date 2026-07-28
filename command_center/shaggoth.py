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

    # Feedback loop. A growing repair queue means users are marking answers
    # wrong faster than the scheduler is repairing them -- a training-quality
    # problem the topic/word counts cannot show (the KB can grow while every
    # new answer is judged bad).
    feedback_total: int = 0
    feedback_bad: int = 0
    feedback_repair_queue: int = 0

    # Topic name -> word count, for every entry in the knowledge base. Used
    # to diff successive samples into an ingestion feed.
    topics: dict = field(default_factory=dict)
    last_episode_id: str = ""
    last_episode_topic: str = ""
    last_episode_words: int = 0

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

    @property
    def stale_ratio(self) -> float:
        return (self.stale_entries / self.knowledge_entries) if self.knowledge_entries else 0.0

    def training_issues(self) -> list[str]:
        """Problems worth surfacing on the dashboard, most severe first.

        Returns ``[]`` when nothing is wrong. A dashboard that can only show
        green is decoration; this is the half that reports trouble. Every
        entry is derived from a real counter Shaggoth reports, not a guess.
        """
        issues: list[str] = []
        if not self.is_up:
            issues.append(f"Shaggoth {self.state.value.lower()}: {self.detail or 'unreachable'}")
            return issues
        if self.state is ShaggothState.STALLED:
            issues.append(f"STALLED — up but not learning ({self.detail or 'no recent research'})")
        if self.scheduler_enabled and not self.scheduler_alive:
            issues.append("curiosity thread DEAD — daemon answers but has stopped learning")
        if not self.scheduler_enabled:
            issues.append("curiosity scheduler DISABLED — no autonomous learning")
        if self.feedback_repair_queue > 0:
            issues.append(
                f"feedback repair backlog: {self.feedback_repair_queue} answer(s) "
                f"flagged wrong and awaiting re-research"
            )
        if self.scrape_errors > 0:
            tail = f" (last: {self.last_scrape_error[:48]})" if self.last_scrape_error else ""
            issues.append(f"{self.scrape_errors} scrape error(s){tail}")
        if self.knowledge_entries and self.stale_ratio >= 0.5:
            issues.append(
                f"{self.stale_entries:,}/{self.knowledge_entries:,} entries stale "
                f"({self.stale_ratio*100:.0f}%) — refresh backlog"
            )
        return issues


@dataclass
class LearningCounter:
    """Tracks knowledge-base growth across dashboard refreshes.

    The dashboard's job is to make learning *visible*, so a bare total is
    not enough -- 307 topics looks identical whether the loop is working or
    dead. This records a baseline on the first healthy sample and reports
    everything gained since, plus a short "just grew" pulse the renderer
    uses to highlight the counter the moment a research episode lands.

    Offline samples are ignored rather than treated as zero, so a restart
    or a momentarily unreachable daemon cannot fake a huge negative delta.
    If the totals genuinely shrink (a rebuilt or pruned knowledge base) the
    baseline is quietly reset instead of reporting a negative gain.
    """

    baseline_entries: Optional[int] = None
    baseline_words: Optional[int] = None
    baseline_episodes: Optional[int] = None

    entries: int = 0
    words: int = 0
    episodes: int = 0
    last_growth_at: Optional[float] = None

    def update(self, status: "ShaggothStatus", now: Optional[float] = None) -> None:
        """Fold a fresh status sample into the counter."""
        if not status.is_up:
            return

        import time

        now = time.time() if now is None else now

        if self.baseline_entries is None:
            self.baseline_entries = status.knowledge_entries
            self.baseline_words = status.total_words
            self.baseline_episodes = status.total_episodes
        elif (
            status.knowledge_entries < self.baseline_entries
            or status.total_words < (self.baseline_words or 0)
        ):
            # Knowledge base shrank -- rebuilt, pruned, or pointed at new
            # data. Re-baseline rather than report a negative gain.
            self.baseline_entries = status.knowledge_entries
            self.baseline_words = status.total_words
            self.baseline_episodes = status.total_episodes

        grew = (
            status.knowledge_entries > self.entries
            or status.total_words > self.words
            or status.total_episodes > self.episodes
        )

        self.entries = status.knowledge_entries
        self.words = status.total_words
        self.episodes = status.total_episodes

        if grew:
            self.last_growth_at = now

    @property
    def gained_entries(self) -> int:
        return max(0, self.entries - (self.baseline_entries or 0))

    @property
    def gained_words(self) -> int:
        return max(0, self.words - (self.baseline_words or 0))

    @property
    def gained_episodes(self) -> int:
        return max(0, self.episodes - (self.baseline_episodes or 0))

    def is_pulsing(self, now: Optional[float] = None, window: float = 30.0) -> bool:
        """True for ``window`` seconds after the counters last moved."""
        if self.last_growth_at is None:
            return False
        import time

        now = time.time() if now is None else now
        return (now - self.last_growth_at) <= window


def format_delta(value: int) -> str:
    """Render a session gain as ``" (+12)"``, or empty when nothing grew."""
    return f" (+{value:,})" if value > 0 else ""


MAX_FEED_EVENTS = 40


@dataclass
class LearningFeed:
    """A rolling log of ingestion events, diffed out of status samples.

    Shaggoth has no event stream -- it only reports totals -- so "what did
    it just learn?" has to be recovered by comparing successive snapshots.
    Each poll, any topic name that was not in the previous sample becomes a
    feed line, as does a finished research episode or a new scrape error.

    The first sample only establishes the baseline: without that guard the
    feed would open with one line per existing topic (307 of them) and the
    ticker would spend its first several minutes replaying old news.
    """

    events: list = field(default_factory=list)
    known_topics: set = field(default_factory=set)
    seeded: bool = False
    last_episode_id: str = ""
    scrape_errors: int = 0

    def observe(self, status: "ShaggothStatus") -> list:
        """Fold in a status sample; returns the events newly appended."""
        if not status.is_up:
            return []

        new_events: list = []
        topics = status.topics or {}

        if not self.seeded:
            self.seeded = True
            self.known_topics = set(topics)
            self.last_episode_id = status.last_episode_id
            self.scrape_errors = status.scrape_errors
            count = status.knowledge_entries or len(topics)
            new_events.append(
                f"[{count}] BASE  knowledge base online: "
                f"{count:,} topics, {status.total_words:,} words ingested"
            )
        else:
            index = len(self.known_topics)
            for name in sorted(set(topics) - self.known_topics):
                index += 1
                words = topics.get(name, 0)
                new_events.append(f"[{index}] OK   {name}: {words:,} words")
            self.known_topics |= set(topics)

            if status.last_episode_id and status.last_episode_id != self.last_episode_id:
                self.last_episode_id = status.last_episode_id
                topic = status.last_episode_topic or "unknown topic"
                new_events.append(
                    f"[*] RESEARCH  {topic}: {status.last_episode_words:,} words learned"
                )

            if status.scrape_errors > self.scrape_errors:
                delta = status.scrape_errors - self.scrape_errors
                self.scrape_errors = status.scrape_errors
                detail = status.last_scrape_error or "unknown error"
                new_events.append(f"[!] FAIL  {delta} scrape error(s): {detail}")

        if status.is_researching and status.current_topic:
            marker = f"[~] LIVE  researching {status.current_topic}"
            if marker not in self.events[-1:]:
                new_events.append(marker)

        self.events.extend(new_events)
        if len(self.events) > MAX_FEED_EVENTS:
            del self.events[: len(self.events) - MAX_FEED_EVENTS]
        return new_events


def marquee_text(events, prompt: str = "matt@r510:~$ ", separator: str = "   ") -> str:
    """Join feed events into the single line the ticker scrolls.

    Rendered shell-style, deliberately: the point is that the box looks
    like it is mid-ingestion, which is exactly what it is.
    """
    if not events:
        return ""
    return prompt + separator.join(events)


EARTH_ALIEN = 0
SATELLITE_ALIEN = 1


def alien_script(status: "ShaggothStatus", counter: "LearningCounter", feed=None) -> list:
    """Build the two aliens' running commentary from real telemetry.

    Returns ``(speaker, line)`` pairs, alternating between the Earth alien
    (``0``) and the satellite alien (``1``). Every line is derived from a
    number the dashboard is already showing, so the bit stays honest --
    if the aliens are talking about 307 topics, there are 307 topics.

    Falls back to a short offline exchange rather than an empty script, so
    the scene never goes silent when Shaggoth is down.
    """
    if not status.is_up:
        return [
            (EARTH_ALIEN, "it's not answering."),
            (SATELLITE_ALIEN, status.detail or "no signal at all."),
            (EARTH_ALIEN, "did you try turning the r510 off and on."),
            (SATELLITE_ALIEN, "i am not touching that machine."),
        ]

    lines: list = []

    if status.is_researching and status.current_topic:
        topic = status.current_topic
        lines += [
            (EARTH_ALIEN, f"it's reading about {topic}. nobody asked."),
            (SATELLITE_ALIEN, f"{topic}. voluntarily. on a saturday."),
        ]

    if feed is not None and feed.events:
        newest = feed.events[-1]
        # Feed lines look like "[42] OK   Photosynthesis: 2,388 words".
        subject = newest.split("  ", 1)[-1].strip() if "  " in newest else newest
        lines.append((EARTH_ALIEN, f"latest ingest: {subject}"))
        lines.append((SATELLITE_ALIEN, "cool. still can't hold a conversation."))

    lines += [
        (EARTH_ALIEN, f"{status.knowledge_entries:,} topics known."),
        (SATELLITE_ALIEN, f"{status.total_words:,} words in. zero opinions out."),
    ]

    if counter.gained_entries:
        lines += [
            (EARTH_ALIEN, f"+{counter.gained_entries} topics since you sat down."),
            (SATELLITE_ALIEN, "learning faster than it is explaining."),
        ]
    else:
        lines += [
            (EARTH_ALIEN, "nothing new since you sat down."),
            (SATELLITE_ALIEN, "it's thinking. allegedly."),
        ]

    if status.total_episodes == 0:
        lines += [
            (EARTH_ALIEN, "zero research runs. ever."),
            (SATELLITE_ALIEN, "the curiosity loop is a rumour."),
        ]
    else:
        plural = "" if status.total_episodes == 1 else "s"
        lines += [
            (EARTH_ALIEN, f"{status.total_episodes} research run{plural} on record."),
            (SATELLITE_ALIEN, "it went and looked something up. unprompted."),
        ]

    if status.scrape_errors:
        detail = status.last_scrape_error or "something refused it"
        lines += [
            (EARTH_ALIEN, f"{status.scrape_errors} scrape errors. latest: {detail}"),
            (SATELLITE_ALIEN, "the internet said no. again."),
        ]

    if status.stale_entries:
        lines += [
            (EARTH_ALIEN, f"{status.stale_entries} topics are going stale."),
            (SATELLITE_ALIEN, "it forgets like the rest of us."),
        ]

    if status.buffered_messages:
        lines += [
            (EARTH_ALIEN, f"{status.buffered_messages} clues buffered from the chat."),
            (SATELLITE_ALIEN, "it is absolutely reading over your shoulder."),
        ]

    lines += [
        (EARTH_ALIEN, f"pages scraped: {status.pages_stored:,}."),
        (SATELLITE_ALIEN, f"{status.seeds_pending} seeds still pending. no rush."),
        (EARTH_ALIEN, "it lives on a dell r510 in a house."),
        (SATELLITE_ALIEN, "and it thinks that is normal."),
    ]

    return lines


def marquee_window(text: str, offset: int, width: int, gap: str = "     ") -> str:
    """Return the ``width``-column slice of ``text`` visible at ``offset``.

    The text wraps around continuously, separated by ``gap`` so the end and
    the restart do not run together. Text that already fits is left static
    and padded rather than scrolled -- a short line jittering in place reads
    as a glitch, not as activity.
    """
    if width <= 0 or not text:
        return ""
    if len(text) <= width:
        return text.ljust(width)
    loop = text + gap
    start = offset % len(loop)
    return (loop + loop)[start : start + width]


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


def _collect_topics(freshness: dict) -> dict:
    """Flatten ``freshness`` into a ``{topic: word_count}`` map.

    Shaggoth reports its knowledge base split into ``fresh_topics`` and
    ``stale_topics``; the ingestion feed only cares about the union, so the
    two lists are merged and any malformed entry is skipped.
    """
    topics: dict = {}
    for key in ("fresh_topics", "stale_topics"):
        entries = freshness.get(key)
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            name = str(entry.get("topic") or "").strip()
            if name:
                topics[name] = _as_int(entry.get("word_count"))
    return topics


def parse_scheduler_response(data: Optional[dict]) -> dict:
    """Extract scheduler health from a ``/curiosity/scheduler`` payload."""
    data = _as_dict(data)
    return {
        "enabled": bool(data.get("enabled", False)),
        "alive": bool(data.get("thread_alive", False)),
        "interval_minutes": _as_int(data.get("interval_minutes")),
        "buffered_messages": _as_int(data.get("buffered_messages")),
    }


def parse_feedback_response(data: Optional[dict]) -> dict:
    """Extract the feedback / repair-queue depth from a ``/feedback`` payload.

    Missing endpoint or malformed body -> all zeros, so an older Shaggoth
    without the feedback loop simply reports nothing rather than erroring.
    """
    data = _as_dict(data)
    return {
        "total": _as_int(data.get("total")),
        "bad": _as_int(data.get("bad")),
        "repair_queue": _as_int(data.get("repair_queue")),
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
    last_id = last_topic = ""
    last_words = 0
    if isinstance(last, dict):
        started = last.get("ended_at") or last.get("started_at") or last.get("finished_at")
        if isinstance(started, (int, float)) and started > 0:
            last_age = max(0.0, now - float(started))
        last_id = str(last.get("episode_id") or "")
        last_topic = str(last.get("topic") or "")
        last_words = _as_int(last.get("words_learned"))

    last_error = scraper.get("last_error")

    return {
        "topics": _collect_topics(freshness),
        "last_episode_id": last_id,
        "last_episode_topic": last_topic,
        "last_episode_words": last_words,
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
    feedback = parse_feedback_response(
        _http_get_json(f"{base_url}/feedback", timeout)
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
        feedback_total=feedback["total"],
        feedback_bad=feedback["bad"],
        feedback_repair_queue=feedback["repair_queue"],
        topics=curiosity["topics"],
        last_episode_id=curiosity["last_episode_id"],
        last_episode_topic=curiosity["last_episode_topic"],
        last_episode_words=curiosity["last_episode_words"],
    )
