"""Tests for observable AI activity detection (tmux pane inspection)."""
from __future__ import annotations

from command_center.activity import (
    ActivityMonitor,
    AIActivityState,
    derive_state,
    has_active_marker,
)
from command_center.ollama import OllamaState

OPENCODE_ACTIVE_PANE = (
    "opencode session\n"
    "> refactor the telemetry module\n"
    "  Thinking...\n"
    "  esc interrupt\n"
)

OPENCODE_QUIET_PANE = (
    "opencode session\n"
    "> refactor the telemetry module\n"
    "  Done. 3 files changed.\n"
    "> \n"
)

CLOUD_MODEL_PANE = (
    "opencode  model: gpt-oss:120b:cloud\n"
    "> summarize the repo\n"
    "  Generating response\n"
    "  esc interrupt\n"
)


def test_has_active_marker_matches_status_words() -> None:
    assert has_active_marker(OPENCODE_ACTIVE_PANE)
    assert has_active_marker(CLOUD_MODEL_PANE)
    assert not has_active_marker(OPENCODE_QUIET_PANE)


def test_marker_outside_final_lines_is_ignored() -> None:
    pane = "Thinking...\n" + "\n".join(f"output line {i}" for i in range(20))
    assert not has_active_marker(pane)


def test_changing_pane_with_active_marker_is_active() -> None:
    monitor = ActivityMonitor(session="opencode")
    assert monitor.update(OPENCODE_ACTIVE_PANE, now=0.0) is True
    assert monitor.update(OPENCODE_ACTIVE_PANE + "more\nesc interrupt\n", now=1.0) is True


def test_stale_inactive_pane_is_idle() -> None:
    monitor = ActivityMonitor(session="opencode")
    assert monitor.update(OPENCODE_QUIET_PANE, now=0.0) is False
    assert monitor.update(OPENCODE_QUIET_PANE, now=60.0) is False
    assert derive_state(OllamaState.ONLINE, False) == AIActivityState.IDLE


def test_frozen_pane_with_marker_goes_stale() -> None:
    """A status word left on screen stops counting once the pane stops changing."""
    monitor = ActivityMonitor(session="opencode", stale_after=10.0)
    assert monitor.update(OPENCODE_ACTIVE_PANE, now=0.0) is True
    assert monitor.update(OPENCODE_ACTIVE_PANE, now=5.0) is True
    assert monitor.update(OPENCODE_ACTIVE_PANE, now=30.0) is False


def test_missing_tmux_session_is_idle() -> None:
    monitor = ActivityMonitor(session="opencode")
    assert monitor.update(None, now=0.0) is False
    assert derive_state(OllamaState.ONLINE, False) == AIActivityState.IDLE


def test_markerless_changing_pane_is_active() -> None:
    """A real OpenCode TUI may not show any recognized status word, but
    it redraws constantly while working -- recent pane changes alone
    must count as activity."""
    monitor = ActivityMonitor(session="opencode")
    assert monitor.update("spinner frame 1\n", now=0.0) is False  # baseline capture
    assert monitor.update("spinner frame 2\n", now=1.0) is True
    assert monitor.update("spinner frame 3\n", now=2.0) is True
    # Pane goes static: activity drops once the change window passes.
    assert monitor.update("spinner frame 3\n", now=10.0) is False


def test_esc_to_interrupt_marker_matches() -> None:
    pane = "opencode\n> do the thing\n  working  (esc to interrupt)\n"
    monitor = ActivityMonitor(session="opencode")
    assert monitor.update(pane, now=0.0) is True


def test_cloud_model_activity_is_active() -> None:
    monitor = ActivityMonitor(session="opencode")
    opencode_active = monitor.update(CLOUD_MODEL_PANE, now=0.0)
    assert opencode_active is True
    # Cloud requests never appear in /api/ps, so Ollama looks quiet.
    assert derive_state(OllamaState.ONLINE, opencode_active) == AIActivityState.ACTIVE


def test_opencode_activity_wins_even_if_ollama_offline() -> None:
    assert derive_state(OllamaState.OFFLINE, True) == AIActivityState.ACTIVE


def test_derive_state_maps_service_states() -> None:
    assert derive_state(OllamaState.OFFLINE, False) == AIActivityState.OFFLINE
    assert derive_state(OllamaState.ERROR, False) == AIActivityState.ERROR
    assert derive_state(OllamaState.IDLE, False) == AIActivityState.IDLE


def test_poll_is_rate_limited(monkeypatch) -> None:
    calls: list[float] = []

    def fake_capture(session: str, timeout: float = 0.5):
        calls.append(1.0)
        return OPENCODE_ACTIVE_PANE

    monkeypatch.setattr("command_center.activity.capture_pane", fake_capture)
    monitor = ActivityMonitor(session="opencode", poll_interval=1.0)
    assert monitor.poll(now=0.0) is True
    assert monitor.poll(now=0.3) is True  # cached, no new capture
    assert monitor.poll(now=0.9) is True
    assert monitor.poll(now=1.1) is True
    assert len(calls) == 2
