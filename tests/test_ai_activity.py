"""Tests for the AI ACTIVITY telemetry row helper."""
from __future__ import annotations

from command_center.app import AI_BUSY_PHASES, AI_PHASE_TICKS, _ai_activity_text
from command_center.ollama import OllamaState


def test_online_and_idle_stand_by() -> None:
    assert _ai_activity_text(OllamaState.ONLINE, 0, False) == "standing by for uplink"
    assert _ai_activity_text(OllamaState.IDLE, 123, True) == "standing by for uplink"


def test_offline() -> None:
    assert _ai_activity_text(OllamaState.OFFLINE, 0, False) == "uplink offline"


def test_error() -> None:
    assert _ai_activity_text(OllamaState.ERROR, 7, False) == "telemetry unavailable"


def test_busy_starts_with_first_phase() -> None:
    text = _ai_activity_text(OllamaState.BUSY, 0, False)
    assert text.startswith(AI_BUSY_PHASES[0])


def test_busy_rotates_phases_every_interval() -> None:
    seen = [
        _ai_activity_text(OllamaState.BUSY, i * AI_PHASE_TICKS, False).rsplit(" ", 1)[0]
        for i in range(len(AI_BUSY_PHASES))
    ]
    assert seen == list(AI_BUSY_PHASES)


def test_busy_wraps_around_after_last_phase() -> None:
    tick = AI_PHASE_TICKS * len(AI_BUSY_PHASES)
    text = _ai_activity_text(OllamaState.BUSY, tick, False)
    assert text.startswith(AI_BUSY_PHASES[0])


def test_busy_dot_suffix_animates() -> None:
    suffixes = {
        _ai_activity_text(OllamaState.BUSY, tick, False).rsplit(" ", 1)[1]
        for tick in range(0, 12)
    }
    assert suffixes == {"·", "··", "···"}


def test_busy_ascii_only_uses_plain_dots() -> None:
    text = _ai_activity_text(OllamaState.BUSY, 8, True)
    assert "·" not in text
    assert text.endswith(".")
