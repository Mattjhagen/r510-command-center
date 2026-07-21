"""Non-interactive smoke test.

Initializes every major component the same way the real dashboard does,
but never calls ``curses.wrapper`` -- this is what CI and the installer
run to catch obvious breakage without needing a real TTY.
"""
from __future__ import annotations

import time

from command_center import animation
from command_center.config import Config, find_opencode_executable, load_config
from command_center.ollama import get_status
from command_center.telemetry import TelemetryCollector


def test_config_loads_without_a_real_config_file_present() -> None:
    # Uses the real load_config() codepath (no explicit path override) to
    # prove startup never depends on ~/.config/r510-command-center existing.
    config = load_config()
    assert isinstance(config, Config)


def test_smoke_full_component_initialization(tmp_path) -> None:
    config = load_config(tmp_path / "missing.toml")
    assert config.title

    collector = TelemetryCollector()
    telemetry = collector.collect()
    assert telemetry.hostname

    started = time.monotonic()
    status = get_status(config.ollama_host, port=65535, timeout=0.3)
    elapsed = time.monotonic() - started
    assert elapsed < 3.0
    assert status.state is not None

    opencode_path = find_opencode_executable(config)
    assert opencode_path is None or isinstance(opencode_path, str)

    for width, height in ((80, 24), (40, 10), (10, 3), (0, 0)):
        for reduced in (False, True):
            for ascii_only in (False, True):
                frame = animation.render(
                    width, height, tick=5, reduced_motion=reduced, ascii_only=ascii_only
                )
                assert len(frame.lines) == height
                assert all(len(line) == width for line in frame.lines)
