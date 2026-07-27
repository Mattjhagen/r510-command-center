"""Shaggoth status parsing, learning counters, and the ingestion feed.

Every test here is offline: the parsers take raw payload dicts, and the
counter/feed take status objects, so none of this needs a running daemon.
"""
from __future__ import annotations

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
