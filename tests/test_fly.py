"""Tests for bounded, secret-safe Fly log monitoring."""
from __future__ import annotations

import subprocess

from command_center.fly import FlyState, get_status, redact_log_line


def test_redact_log_line_masks_common_token_shapes() -> None:
    line = "Authorization: Bearer secret-token-value sk-abcdefghi eyJheader.payload.signature"
    redacted = redact_log_line(line)
    assert "secret-token-value" not in redacted
    assert "sk-abcdefghi" not in redacted
    assert "eyJheader.payload.signature" not in redacted
    assert redacted.count("[REDACTED]") == 3


def test_get_status_parses_recent_json_logs(monkeypatch) -> None:
    output = "\n".join(
        [
            '{"timestamp":"2026-07-24T00:00:00Z","level":"info","message":"healthy request 200"}',
            '{"timestamp":"2026-07-24T00:00:01Z","level":"warn","message":"slow response"}',
            '{"timestamp":"2026-07-24T00:00:02Z","level":"error","message":"upstream returned 502"}',
        ]
    )
    monkeypatch.setattr("command_center.fly.shutil.which", lambda name: "/usr/bin/flyctl")
    monkeypatch.setattr(
        "command_center.fly.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, output, ""),
    )
    status = get_status("archon-ide-pacmac", max_lines=2)
    assert status.state == FlyState.ERROR
    assert status.warning_count == 1
    assert status.error_count == 1
    assert len(status.lines) == 2
    assert "502" in status.lines[-1]


def test_get_status_is_unavailable_without_flyctl(monkeypatch) -> None:
    monkeypatch.setattr("command_center.fly.shutil.which", lambda name: None)
    status = get_status("archon-ide-pacmac")
    assert status.state == FlyState.UNAVAILABLE
    assert "not installed" in status.detail


def test_get_status_allows_monitoring_to_be_disabled() -> None:
    assert get_status("").state == FlyState.DISABLED
