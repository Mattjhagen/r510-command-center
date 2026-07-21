"""Tests for the AI ACTIVITY telemetry row helper."""
from __future__ import annotations

from command_center.activity import AIActivityState
from command_center.app import AI_BUSY_PHASES, AI_PHASE_TICKS, _ai_activity_text


def test_idle_stands_by() -> None:
    assert _ai_activity_text(AIActivityState.IDLE, 0, False) == "standing by for uplink"
    assert _ai_activity_text(AIActivityState.IDLE, 123, True) == "standing by for uplink"


def test_offline() -> None:
    assert _ai_activity_text(AIActivityState.OFFLINE, 0, False) == "uplink offline"


def test_error() -> None:
    assert _ai_activity_text(AIActivityState.ERROR, 7, False) == "telemetry unavailable"


def test_active_starts_with_first_phase() -> None:
    text = _ai_activity_text(AIActivityState.ACTIVE, 0, False)
    assert text.startswith(AI_BUSY_PHASES[0])


def test_active_rotates_phases_every_interval() -> None:
    seen = [
        _ai_activity_text(AIActivityState.ACTIVE, i * AI_PHASE_TICKS, False).rsplit(" ", 1)[0]
        for i in range(len(AI_BUSY_PHASES))
    ]
    assert seen == list(AI_BUSY_PHASES)


def test_active_wraps_around_after_last_phase() -> None:
    tick = AI_PHASE_TICKS * len(AI_BUSY_PHASES)
    text = _ai_activity_text(AIActivityState.ACTIVE, tick, False)
    assert text.startswith(AI_BUSY_PHASES[0])


def test_active_dot_suffix_animates() -> None:
    suffixes = {
        _ai_activity_text(AIActivityState.ACTIVE, tick, False).rsplit(" ", 1)[1]
        for tick in range(0, 12)
    }
    assert suffixes == {"·", "··", "···"}


def test_active_ascii_only_uses_plain_dots() -> None:
    text = _ai_activity_text(AIActivityState.ACTIVE, 8, True)
    assert "·" not in text
    assert text.endswith(".")
