"""Tests for tmux session state detection."""
from __future__ import annotations

from types import SimpleNamespace

from command_center.activity import ActivityMonitor
from command_center.app import _resolve_tmux_state, _tmux_session_state


def _fake_run(stdout: str, returncode: int = 0):
    def run(*args, **kwargs):
        return SimpleNamespace(stdout=stdout, returncode=returncode)

    return run


def _patch_tmux(monkeypatch, stdout: str, returncode: int = 0) -> None:
    monkeypatch.setattr("command_center.app.shutil.which", lambda name: "/usr/bin/tmux")
    monkeypatch.setattr("command_center.app.subprocess.run", _fake_run(stdout, returncode))


def test_attached_single_client(monkeypatch) -> None:
    _patch_tmux(monkeypatch, "opencode:1\n")
    assert _tmux_session_state("opencode") == "ATTACHED"


def test_attached_multiple_clients(monkeypatch) -> None:
    # tmux reports the client COUNT; two attached clients is still ATTACHED.
    _patch_tmux(monkeypatch, "opencode:2\n")
    assert _tmux_session_state("opencode") == "ATTACHED"


def test_detached_session(monkeypatch) -> None:
    _patch_tmux(monkeypatch, "opencode:0\n")
    assert _tmux_session_state("opencode") == "DETACHED"


def test_no_matching_session(monkeypatch) -> None:
    _patch_tmux(monkeypatch, "other:1\nwork:0\n")
    assert _tmux_session_state("opencode") == "NONE"


def test_no_server_running(monkeypatch) -> None:
    _patch_tmux(monkeypatch, "", returncode=1)
    assert _tmux_session_state("opencode") == "NONE"


def test_tmux_missing(monkeypatch) -> None:
    monkeypatch.setattr("command_center.app.shutil.which", lambda name: None)
    assert _tmux_session_state("opencode") == "N/A"


def test_resolve_upgrades_none_when_pane_seen() -> None:
    assert _resolve_tmux_state("NONE", pane_seen=True) == "DETACHED"


def test_resolve_leaves_other_states_alone() -> None:
    assert _resolve_tmux_state("NONE", pane_seen=False) == "NONE"
    assert _resolve_tmux_state("ATTACHED", pane_seen=True) == "ATTACHED"
    assert _resolve_tmux_state("DETACHED", pane_seen=True) == "DETACHED"
    assert _resolve_tmux_state("N/A", pane_seen=False) == "N/A"


def test_monitor_pane_seen_tracks_capture() -> None:
    monitor = ActivityMonitor(session="opencode")
    assert monitor.pane_seen is False
    monitor.update("some pane content\n", now=0.0)
    assert monitor.pane_seen is True
    monitor.update(None, now=1.0)
    assert monitor.pane_seen is False
