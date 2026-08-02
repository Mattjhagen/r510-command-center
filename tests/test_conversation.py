"""The generative dialogue: Ollama asks, Shaggoth answers, rendered as a
script the animation can play back. Everything the render loop touches is
lock-guarded, so this runs without a real network.
"""
from __future__ import annotations

import threading
import time

from command_center.conversation import (
    CORE,
    EARTH,
    MAX_LINES,
    ConversationEngine,
    condense,
)


# --------------------------------------------------------------------------
# Condensing a reply into a bubble
# --------------------------------------------------------------------------


def test_condense_leaves_short_replies_alone():
    assert condense("Short answer.") == "Short answer."


def test_condense_keeps_whole_sentences():
    text = "First sentence here. " + "x" * 300
    out = condense(text, max_chars=60)
    assert out == "First sentence here."


def test_condense_cuts_a_long_sentence_at_a_word_boundary():
    out = condense("word " * 100, max_chars=40)
    assert len(out) <= 41  # plus the ellipsis
    assert not out.rstrip("…").endswith("wor")


def test_condense_normalises_whitespace():
    assert condense("  a\n\n b  ") == "a b"


def test_condense_handles_empty_input():
    assert condense("") == ""
    assert condense(None) == ""


# --------------------------------------------------------------------------
# The engine's non-networked surface
# --------------------------------------------------------------------------


class FakeEngine(ConversationEngine):
    """A ConversationEngine with both HTTP calls replaced by scripted values."""

    def __init__(self, ollama_replies=(), shaggoth_replies=(), **kwargs):
        super().__init__("http://unused", turn_seconds=kwargs.pop("turn_seconds", 5), **kwargs)
        self._ollama_replies = list(ollama_replies)
        self._shaggoth_replies = list(shaggoth_replies)
        self.asked = []

    def _ask_ollama(self) -> str:
        return self._ollama_replies.pop(0) if self._ollama_replies else ""

    def _ask_shaggoth(self, message: str) -> str:
        self.asked.append(message)
        return self._shaggoth_replies.pop(0) if self._shaggoth_replies else ""


def test_script_starts_empty():
    engine = FakeEngine()
    assert engine.script() == []
    assert engine.live is False


def test_append_bounds_the_script_to_max_lines():
    engine = FakeEngine()
    for i in range(MAX_LINES + 10):
        engine._append(CORE, f"line {i}")
    assert len(engine.script()) == MAX_LINES


def test_append_drops_a_blank_reply():
    engine = FakeEngine()
    engine._append(EARTH, "   ")
    assert engine.script() == []


def test_script_returns_a_copy_so_the_renderer_cannot_mutate_state():
    engine = FakeEngine()
    engine._append(CORE, "a line of dialogue")
    snapshot = engine.script()
    snapshot.clear()
    assert engine.script()


def test_stop_is_idempotent_and_start_does_not_double_spawn():
    engine = FakeEngine()
    engine.start()
    first = engine._thread
    engine.start()
    assert engine._thread is first
    engine.stop()
    engine.stop()
    engine._thread.join(timeout=2)


# --------------------------------------------------------------------------
# One full run of the loop, driven for real through start()/stop()
# --------------------------------------------------------------------------


def _run_until(engine, predicate, timeout=2.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return False


def test_a_successful_turn_renders_both_speakers_and_goes_live():
    engine = FakeEngine(
        ollama_replies=["What is the boiling point of tungsten?"],
        shaggoth_replies=["Tungsten boils at 5,930°C."],
    )
    engine.start()
    try:
        assert _run_until(engine, lambda: len(engine.script()) >= 2)
        speakers = [who for who, _text in engine.script()]
        assert EARTH in speakers
        assert CORE in speakers
        assert engine.live is True
        assert engine.asked == ["What is the boiling point of tungsten?"]
    finally:
        engine.stop()
        engine._thread.join(timeout=2)


def test_ollama_returning_nothing_keeps_the_scene_silent_and_not_live():
    engine = FakeEngine(ollama_replies=[""])
    engine.start()
    try:
        time.sleep(0.2)
        assert engine.script() == []
        assert engine.live is False
    finally:
        engine.stop()
        engine._thread.join(timeout=2)


def test_shaggoth_returning_nothing_still_shows_the_question_but_not_live():
    """An unreachable Shaggoth must not silence the question that was asked,
    but must not claim the exchange is live either."""
    engine = FakeEngine(
        ollama_replies=["What is the Coriolis effect?"],
        shaggoth_replies=[""],
    )
    engine.start()
    try:
        assert _run_until(engine, lambda: len(engine.script()) >= 1)
        speakers = [who for who, _text in engine.script()]
        assert speakers == [EARTH]
        assert engine.live is False
    finally:
        engine.stop()
        engine._thread.join(timeout=2)


def test_script_is_safe_to_read_while_the_thread_writes():
    """The render loop calls script() every frame; it must never tear."""
    engine = FakeEngine(turn_seconds=5)
    stop = threading.Event()

    def writer():
        while not stop.is_set():
            engine._append(CORE, "a line of dialogue")

    t = threading.Thread(target=writer, daemon=True)
    t.start()
    try:
        for _ in range(300):
            for who, text in engine.script():
                assert who in (EARTH, CORE)
                assert isinstance(text, str)
    finally:
        stop.set()
        t.join(timeout=2)


# --------------------------------------------------------------------------
# The real HTTP calls degrade to "" rather than raising
# --------------------------------------------------------------------------


def test_ask_ollama_returns_empty_string_when_unreachable():
    engine = ConversationEngine("http://unused", ollama_host="127.0.0.1", ollama_port=1)
    assert engine._ask_ollama() == ""


def test_ask_shaggoth_returns_empty_string_when_unreachable():
    engine = ConversationEngine("http://127.0.0.1:1")
    assert engine._ask_shaggoth("hello") == ""
