"""Shaggoth status parsing, learning counters, and the ingestion feed.

Every test here is offline: the parsers take raw payload dicts, and the
counter/feed take status objects, so none of this needs a running daemon.
"""
from __future__ import annotations

import pytest

from command_center import shaggoth
from command_center.shaggoth import (
    LearningCounter,
    LearningFeed,
    ShaggothState,
    ShaggothStatus,
    marquee_text,
    marquee_window,
)


# --------------------------------------------------------------------------
# Payload parsing
# --------------------------------------------------------------------------


def test_parse_scheduler_response_reads_thread_health() -> None:
    parsed = shaggoth.parse_scheduler_response(
        {
            "enabled": True,
            "interval_minutes": 60,
            "buffered_messages": 4,
            "thread_alive": True,
        }
    )
    assert parsed == {
        "enabled": True,
        "alive": True,
        "interval_minutes": 60,
        "buffered_messages": 4,
    }


def test_parse_scheduler_response_tolerates_garbage() -> None:
    assert shaggoth.parse_scheduler_response(None)["enabled"] is False
    assert shaggoth.parse_scheduler_response({"interval_minutes": "oops"})["interval_minutes"] == 0


def test_parse_curiosity_response_extracts_live_counters() -> None:
    parsed = shaggoth.parse_curiosity_response(
        {
            "is_running": False,
            "total_episodes": 1,
            "knowledge_entries": 307,
            "last_episode": {
                "episode_id": "curiosity-61f07b79",
                "topic": "aeroponic farming",
                "words_learned": 3253,
                "ended_at": 900.0,
            },
            "scraper_stats": {
                "pages_stored": 38,
                "total_words": 238431,
                "seeds_pending": 27,
                "errors": 11,
                "last_error": "HTTP Error 403: Blocked",
            },
            "freshness": {
                "fresh_count": 237,
                "stale_count": 70,
                "fresh_topics": [{"topic": "Machine Learning", "word_count": 2257}],
                "stale_topics": [{"topic": "Algebra", "word_count": 2151}],
            },
        },
        now=1000.0,
    )
    assert parsed["knowledge_entries"] == 307
    assert parsed["total_words"] == 238431
    assert parsed["last_episode_age_seconds"] == 100.0
    assert parsed["last_episode_id"] == "curiosity-61f07b79"
    assert parsed["last_episode_words"] == 3253
    # Fresh and stale topics are merged -- the feed only cares about the union.
    assert parsed["topics"] == {"Machine Learning": 2257, "Algebra": 2151}


def test_parse_curiosity_response_skips_malformed_topic_entries() -> None:
    parsed = shaggoth.parse_curiosity_response(
        {"freshness": {"fresh_topics": ["not-a-dict", {"topic": "", "word_count": 5}]}},
        now=0.0,
    )
    assert parsed["topics"] == {}


def test_parse_model_response_reads_openai_fields() -> None:
    parsed = shaggoth.parse_model_response(
        {"name": "openai", "openai": True, "openai_model": "gpt-4o-mini", "configured": True, "trained": True}
    )
    assert parsed == {
        "name": "openai",
        "openai": True,
        "openai_model": "gpt-4o-mini",
        "configured": True,
    }


def test_parse_model_response_tolerates_garbage() -> None:
    parsed = shaggoth.parse_model_response(None)
    assert parsed == {"name": "none", "openai": False, "openai_model": "", "configured": False}


def test_parse_critic_response_reads_fields() -> None:
    parsed = shaggoth.parse_critic_response(
        {
            "running": True,
            "model": "claude-haiku-4-5-20251001",
            "available": True,
            "judged": 20,
            "good": 1,
            "weak": 3,
            "bad": 16,
            "last_error": "",
        }
    )
    assert parsed["running"] is True
    assert parsed["model"] == "claude-haiku-4-5-20251001"
    assert parsed["judged"] == 20
    assert parsed["good"] == 1
    assert parsed["weak"] == 3
    assert parsed["bad"] == 16


def test_parse_critic_response_tolerates_garbage() -> None:
    parsed = shaggoth.parse_critic_response(None)
    assert parsed["running"] is False
    assert parsed["model"] == ""
    assert parsed["judged"] == 0


# --------------------------------------------------------------------------
# Service uptime
# --------------------------------------------------------------------------


class _FakeCompletedProcess:
    def __init__(self, stdout: str = "") -> None:
        self.stdout = stdout


def test_service_uptime_reads_monotonic_timestamp(monkeypatch) -> None:
    monkeypatch.setattr(
        shaggoth.subprocess, "run",
        lambda *a, **k: _FakeCompletedProcess("1000000000"),  # 1000s since boot
    )
    monkeypatch.setattr(shaggoth.time, "clock_gettime", lambda clk: 1283.5)
    uptime = shaggoth.service_uptime_seconds()
    assert uptime == pytest.approx(283.5)


def test_service_uptime_none_when_never_active(monkeypatch) -> None:
    monkeypatch.setattr(shaggoth.subprocess, "run", lambda *a, **k: _FakeCompletedProcess("0"))
    assert shaggoth.service_uptime_seconds() is None


def test_service_uptime_none_when_systemctl_missing(monkeypatch) -> None:
    def raise_missing(*a, **k):
        raise FileNotFoundError()

    monkeypatch.setattr(shaggoth.subprocess, "run", raise_missing)
    assert shaggoth.service_uptime_seconds() is None


def test_service_uptime_none_on_timeout(monkeypatch) -> None:
    import subprocess as sp

    def raise_timeout(*a, **k):
        raise sp.TimeoutExpired(cmd="systemctl", timeout=2.0)

    monkeypatch.setattr(shaggoth.subprocess, "run", raise_timeout)
    assert shaggoth.service_uptime_seconds() is None


def test_service_uptime_none_on_malformed_output(monkeypatch) -> None:
    monkeypatch.setattr(shaggoth.subprocess, "run", lambda *a, **k: _FakeCompletedProcess("not-a-number"))
    assert shaggoth.service_uptime_seconds() is None


def test_service_uptime_never_negative(monkeypatch) -> None:
    """A clock or timestamp mismatch must clamp to 0, not report negative uptime."""
    monkeypatch.setattr(shaggoth.subprocess, "run", lambda *a, **k: _FakeCompletedProcess("5000000"))
    monkeypatch.setattr(shaggoth.time, "clock_gettime", lambda clk: 1.0)
    assert shaggoth.service_uptime_seconds() == 0.0


# --------------------------------------------------------------------------
# HTTP fetch resilience
# --------------------------------------------------------------------------


class _FakeResponse:
    def __init__(self, status=200, body=b"{}"):
        self.status = status
        self._body = body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_http_get_json_retries_once_before_giving_up(monkeypatch) -> None:
    """Verified live: a request that drops mid-response under load succeeds
    immediately on retry. One retry must absorb that."""
    calls = []

    def flaky_urlopen(url, timeout):
        calls.append(url)
        if len(calls) == 1:
            raise OSError("broken pipe")
        return _FakeResponse(body=b'{"ok": true}')

    monkeypatch.setattr(shaggoth.urllib.request, "urlopen", flaky_urlopen)
    result = shaggoth._http_get_json("http://x/y", timeout=0.1)
    assert result == {"ok": True}
    assert len(calls) == 2


def test_http_get_json_gives_up_after_retries_exhausted(monkeypatch) -> None:
    def always_fails(url, timeout):
        raise OSError("broken pipe")

    monkeypatch.setattr(shaggoth.urllib.request, "urlopen", always_fails)
    assert shaggoth._http_get_json("http://x/y", timeout=0.1) is None


def test_get_status_reports_error_when_curiosity_status_fetch_fails(monkeypatch) -> None:
    """A dropped connection on /curiosity/status alone must not be read as
    an empty knowledge base. Falling through to normal classification would
    report IDLE with 0 entries, and LearningCounter -- which processes any
    ``is_up`` sample -- would read that as the knowledge base having shrunk
    to zero and silently re-baseline all session growth tracking to
    nothing. Verified live: this exact endpoint dropped a real 809-entry
    knowledge base to a reported zero under load."""
    monkeypatch.setattr(shaggoth, "systemctl_is_active", lambda service, timeout=2.0: True)

    def fake_get(url, timeout, retries=1):
        if url.endswith("/health"):
            return {"ok": True, "version": "0.1.0"}
        if url.endswith("/curiosity/status"):
            return None  # simulates the dropped connection
        return {}

    monkeypatch.setattr(shaggoth, "_http_get_json", fake_get)
    status = shaggoth.get_status()
    assert status.state == ShaggothState.ERROR
    assert "curiosity/status" in status.detail
    assert status.is_up is False


def test_get_status_reports_healthy_state_when_all_endpoints_answer(monkeypatch) -> None:
    monkeypatch.setattr(shaggoth, "systemctl_is_active", lambda service, timeout=2.0: True)
    monkeypatch.setattr(shaggoth, "service_uptime_seconds", lambda service, timeout=2.0: 4321.0)

    def fake_get(url, timeout, retries=1):
        if url.endswith("/health"):
            return {"ok": True, "version": "0.1.0"}
        if url.endswith("/curiosity/scheduler"):
            return {"enabled": True, "thread_alive": True, "interval_minutes": 15, "buffered_messages": 0}
        if url.endswith("/curiosity/status"):
            return {
                "knowledge_entries": 809,
                "is_running": False,
                "total_episodes": 215,
                "scraper_stats": {"total_words": 275035},
                "freshness": {},
            }
        if url.endswith("/feedback"):
            return {"total": 6, "bad": 6, "repair_queue": 6}
        if url.endswith("/model/status"):
            return {"name": "openai", "openai": True, "openai_model": "gpt-4o-mini", "configured": True}
        if url.endswith("/critic"):
            return {"running": True, "model": "claude-haiku-4-5-20251001", "available": True, "judged": 20, "good": 1, "weak": 3, "bad": 16}
        return {}

    monkeypatch.setattr(shaggoth, "_http_get_json", fake_get)
    status = shaggoth.get_status()
    assert status.state == ShaggothState.ONLINE
    assert status.knowledge_entries == 809
    assert status.feedback_repair_queue == 6
    assert status.uptime_seconds == 4321.0
    assert status.generation_model == "openai"
    assert status.generation_openai is True
    assert status.generation_openai_model == "gpt-4o-mini"
    assert status.critic_running is True
    assert status.critic_model == "claude-haiku-4-5-20251001"
    assert status.critic_judged == 20


def test_get_status_older_shaggoth_without_model_or_critic_routes_degrades_quietly(monkeypatch) -> None:
    """An older Shaggoth without /model/status or /critic must not error --
    _http_get_json already returns None for a 404, same as any other gap."""
    monkeypatch.setattr(shaggoth, "systemctl_is_active", lambda service, timeout=2.0: True)
    monkeypatch.setattr(shaggoth, "service_uptime_seconds", lambda service, timeout=2.0: None)

    def fake_get(url, timeout, retries=1):
        if url.endswith("/health"):
            return {"ok": True, "version": "0.1.0"}
        if url.endswith("/curiosity/status"):
            return {"knowledge_entries": 5, "is_running": False, "scraper_stats": {}, "freshness": {}}
        if url.endswith(("/model/status", "/critic")):
            return None
        return {}

    monkeypatch.setattr(shaggoth, "_http_get_json", fake_get)
    status = shaggoth.get_status()
    assert status.generation_model == "none"
    assert status.critic_running is False
    assert status.uptime_seconds is None


def test_get_status_does_not_report_uptime_when_service_inactive(monkeypatch) -> None:
    """A stale ActiveEnterTimestampMonotonic from a previous run must not be
    reported as current uptime once the unit is confirmed no longer active."""
    monkeypatch.setattr(shaggoth, "systemctl_is_active", lambda service, timeout=2.0: False)
    calls = []
    monkeypatch.setattr(
        shaggoth, "service_uptime_seconds",
        lambda service, timeout=2.0: calls.append(1) or 9999.0,
    )
    monkeypatch.setattr(shaggoth, "_http_get_json", lambda *a, **k: None)
    status = shaggoth.get_status()
    assert status.state == ShaggothState.OFFLINE
    assert calls == []  # never even asked, since active is False


# --------------------------------------------------------------------------
# ShaggothStatus display properties
# --------------------------------------------------------------------------


def test_uptime_text_unknown_when_none() -> None:
    assert ShaggothStatus().uptime_text == "-"


def test_uptime_text_formats_seconds() -> None:
    assert ShaggothStatus(uptime_seconds=4321.0).uptime_text == "1h 12m"


def test_generation_summary_plain_model() -> None:
    assert ShaggothStatus(generation_model="markov").generation_summary == "markov"


def test_generation_summary_openai_configured() -> None:
    status = ShaggothStatus(
        generation_model="openai", generation_openai=True,
        generation_openai_model="gpt-4o-mini", generation_configured=True,
    )
    assert status.generation_summary == "openai:gpt-4o-mini"


def test_generation_summary_openai_missing_key() -> None:
    status = ShaggothStatus(
        generation_model="openai", generation_openai=True,
        generation_openai_model="gpt-4o-mini", generation_configured=False,
    )
    assert "key missing" in status.generation_summary


def test_critic_summary_not_configured() -> None:
    assert ShaggothStatus().critic_summary == "not configured"


def test_critic_summary_configured_but_not_running() -> None:
    status = ShaggothStatus(critic_model="qwen2.5-coder:7b", critic_running=False)
    assert "not running" in status.critic_summary


def test_critic_summary_running_but_unavailable() -> None:
    status = ShaggothStatus(critic_model="qwen2.5-coder:7b", critic_running=True, critic_available=False)
    assert "unavailable" in status.critic_summary


def test_critic_summary_healthy() -> None:
    status = ShaggothStatus(critic_model="qwen2.5-coder:7b", critic_running=True, critic_available=True)
    assert status.critic_summary == "qwen2.5-coder:7b"


def test_training_issues_flags_critic_configured_but_not_running() -> None:
    status = ShaggothStatus(state=ShaggothState.ONLINE, critic_model="qwen2.5-coder:7b", critic_running=False)
    assert any("critic" in issue and "not running" in issue for issue in status.training_issues())


def test_training_issues_flags_critic_unavailable() -> None:
    status = ShaggothStatus(
        state=ShaggothState.ONLINE, critic_model="qwen2.5-coder:7b",
        critic_running=True, critic_available=False,
    )
    assert any("unavailable" in issue for issue in status.training_issues())


def test_training_issues_silent_when_critic_healthy() -> None:
    status = ShaggothStatus(
        state=ShaggothState.ONLINE, scheduler_enabled=True, scheduler_alive=True,
        critic_model="qwen2.5-coder:7b", critic_running=True, critic_available=True,
    )
    assert status.training_issues() == []


def test_training_issues_does_not_surface_stale_last_error() -> None:
    """A critic that recovered from a one-off error must not show a
    permanent issue -- /critic never clears last_error on success."""
    status = ShaggothStatus(
        state=ShaggothState.ONLINE, scheduler_enabled=True, scheduler_alive=True,
        critic_model="qwen2.5-coder:7b", critic_running=True, critic_available=True,
        critic_last_error="bad parameter or other API misuse",
    )
    assert status.training_issues() == []


def test_training_issues_silent_when_critic_not_configured() -> None:
    """No critic at all (older Shaggoth) isn't itself an issue."""
    status = ShaggothStatus(
        state=ShaggothState.ONLINE, scheduler_enabled=True, scheduler_alive=True,
        knowledge_entries=10,
    )
    assert status.training_issues() == []


# --------------------------------------------------------------------------
# State classification
# --------------------------------------------------------------------------


def _classify(**overrides):
    scheduler = {"enabled": True, "alive": True, "interval_minutes": 60, "buffered_messages": 0}
    curiosity = {
        "is_researching": False,
        "knowledge_entries": 307,
        "last_episode_age_seconds": 60.0,
    }
    scheduler.update(overrides.pop("scheduler", {}))
    curiosity.update(overrides.pop("curiosity", {}))
    return shaggoth._classify(scheduler, curiosity, shaggoth.STALLED_AFTER_SECONDS)


def test_classify_learning_beats_everything_else() -> None:
    state, _ = _classify(curiosity={"is_researching": True})
    assert state is ShaggothState.LEARNING


def test_classify_dead_thread_is_stalled_not_online() -> None:
    state, detail = _classify(scheduler={"alive": False})
    assert state is ShaggothState.STALLED
    assert "thread" in detail


def test_classify_up_but_never_researching_is_stalled() -> None:
    state, detail = _classify(curiosity={"last_episode_age_seconds": 60 * 60 * 24})
    assert state is ShaggothState.STALLED
    assert "24h" in detail


def test_classify_empty_knowledge_base_is_idle() -> None:
    state, _ = _classify(curiosity={"knowledge_entries": 0})
    assert state is ShaggothState.IDLE


def test_classify_healthy_between_cycles_is_online() -> None:
    assert _classify()[0] is ShaggothState.ONLINE


# --------------------------------------------------------------------------
# Learning counter
# --------------------------------------------------------------------------


def _status(entries: int, words: int, episodes: int = 0) -> ShaggothStatus:
    return ShaggothStatus(
        state=ShaggothState.ONLINE,
        knowledge_entries=entries,
        total_words=words,
        total_episodes=episodes,
    )


def test_counter_first_sample_reports_no_gain() -> None:
    counter = LearningCounter()
    counter.update(_status(305, 235_178), now=100.0)
    assert counter.entries == 305
    assert counter.gained_entries == 0
    assert counter.gained_words == 0


def test_counter_reports_growth_since_baseline() -> None:
    counter = LearningCounter()
    counter.update(_status(305, 235_178, 0), now=100.0)
    counter.update(_status(307, 238_431, 1), now=200.0)
    assert counter.gained_entries == 2
    assert counter.gained_words == 3_253
    assert counter.gained_episodes == 1


def test_counter_ignores_offline_samples() -> None:
    """An unreachable daemon must not zero the counters or the baseline."""
    counter = LearningCounter()
    counter.update(_status(307, 238_431), now=100.0)
    counter.update(ShaggothStatus(state=ShaggothState.OFFLINE), now=200.0)
    assert counter.entries == 307
    assert counter.gained_entries == 0


def test_counter_rebaselines_when_knowledge_base_shrinks() -> None:
    """A rebuilt or pruned KB re-baselines instead of showing a negative gain."""
    counter = LearningCounter()
    counter.update(_status(307, 238_431), now=100.0)
    counter.update(_status(12, 9_000), now=200.0)
    assert counter.gained_entries == 0
    assert counter.gained_words == 0
    counter.update(_status(15, 11_000), now=300.0)
    assert counter.gained_entries == 3


def test_counter_pulses_only_briefly_after_growth() -> None:
    counter = LearningCounter()
    counter.update(_status(305, 235_178), now=100.0)
    counter.update(_status(307, 238_431), now=200.0)
    assert counter.is_pulsing(now=210.0, window=30.0)
    assert not counter.is_pulsing(now=400.0, window=30.0)


def test_format_delta_hides_zero() -> None:
    assert shaggoth.format_delta(0) == ""
    assert shaggoth.format_delta(3253) == " (+3,253)"


# --------------------------------------------------------------------------
# Ingestion feed
# --------------------------------------------------------------------------


def _feed_status(topics: dict, **kwargs) -> ShaggothStatus:
    return ShaggothStatus(
        state=kwargs.pop("state", ShaggothState.ONLINE),
        knowledge_entries=len(topics),
        total_words=sum(topics.values()),
        topics=topics,
        **kwargs,
    )


def test_feed_first_sample_only_baselines() -> None:
    """Opening the dashboard must not replay 307 already-known topics."""
    feed = LearningFeed()
    events = feed.observe(_feed_status({"Physics": 7297, "Chemistry": 4464}))
    assert len(events) == 1
    assert "BASE" in events[0]
    assert feed.known_topics == {"Physics", "Chemistry"}


def test_feed_emits_a_line_per_newly_ingested_topic() -> None:
    feed = LearningFeed()
    feed.observe(_feed_status({"Physics": 7297}))
    events = feed.observe(_feed_status({"Physics": 7297, "Biology": 6970}))
    assert events == ["[2] OK   Biology: 6,970 words"]


def test_feed_emits_research_episode_completion() -> None:
    feed = LearningFeed()
    feed.observe(_feed_status({"Physics": 7297}))
    events = feed.observe(
        _feed_status(
            {"Physics": 7297},
            last_episode_id="curiosity-61f07b79",
            last_episode_topic="aeroponic farming",
            last_episode_words=3253,
        )
    )
    assert any("RESEARCH" in e and "aeroponic farming" in e for e in events)


def test_feed_emits_scrape_failures() -> None:
    feed = LearningFeed()
    feed.observe(_feed_status({"Physics": 7297}, scrape_errors=0))
    events = feed.observe(
        _feed_status(
            {"Physics": 7297},
            scrape_errors=2,
            last_scrape_error="HTTP Error 403: Blocked",
        )
    )
    assert any("FAIL" in e and "403" in e for e in events)


def test_feed_ignores_offline_samples() -> None:
    feed = LearningFeed()
    assert feed.observe(ShaggothStatus(state=ShaggothState.OFFLINE)) == []
    assert feed.seeded is False


def test_feed_is_bounded() -> None:
    feed = LearningFeed()
    feed.observe(_feed_status({"seed": 1}))
    for i in range(shaggoth.MAX_FEED_EVENTS * 2):
        feed.observe(_feed_status({"seed": 1, f"Topic {i}": 100}))
    assert len(feed.events) <= shaggoth.MAX_FEED_EVENTS


# --------------------------------------------------------------------------
# Marquee
# --------------------------------------------------------------------------


def test_marquee_text_is_empty_without_events() -> None:
    assert marquee_text([]) == ""


def test_marquee_text_reads_like_a_shell_session() -> None:
    text = marquee_text(["[1] OK   Physics: 7,297 words"])
    assert text.startswith("matt@r510:~$ ")
    assert "Physics" in text


def test_marquee_window_scrolls_and_wraps() -> None:
    text = "ABCDEFGH"
    assert marquee_window(text, 0, 4) == "ABCD"
    assert marquee_window(text, 2, 4) == "CDEF"
    # Wrapping past the end returns to the start rather than running out.
    wrapped = marquee_window(text, len(text) + 5, 4)
    assert len(wrapped) == 4
    assert marquee_window(text, 0, 4) == marquee_window(text, len(text) + 5, 4)


def test_marquee_window_pads_short_text_instead_of_jittering() -> None:
    assert marquee_window("hi", 7, 6) == "hi    "


def test_marquee_window_handles_degenerate_sizes() -> None:
    assert marquee_window("", 0, 20) == ""
    assert marquee_window("text", 0, 0) == ""
