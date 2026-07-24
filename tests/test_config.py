"""Tests for configuration defaults, loading, and OpenCode detection."""
from __future__ import annotations

import os
import stat
from pathlib import Path

from command_center.config import (
    Config,
    build_tmux_opencode_command,
    find_opencode_executable,
    load_config,
)


def _make_executable(path: Path) -> None:
    path.write_text("#!/bin/sh\necho hi\n")
    path.chmod(path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


def test_defaults_when_no_file(tmp_path: Path) -> None:
    config = load_config(tmp_path / "does-not-exist.toml")
    assert config == Config()
    assert config.ollama_host == "127.0.0.1"
    assert config.ollama_port == 11434
    assert config.tmux_session == "opencode"
    assert config.color_mode is True
    assert config.ascii_only is False
    assert config.opencode_path is None


def test_load_config_overrides_known_fields(tmp_path: Path) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
        title = "CUSTOM TITLE"
        ollama_port = 12345
        refresh_interval = 2.5
        color_mode = false
        ascii_only = true
        fly_app_name = "other-fly-app"
        fly_refresh_seconds = 45
        fly_log_lines = 50
        """
    )
    config = load_config(config_file)
    assert config.title == "CUSTOM TITLE"
    assert config.ollama_port == 12345
    assert config.refresh_interval == 2.5
    assert config.color_mode is False
    assert config.ascii_only is True
    assert config.fly_app_name == "other-fly-app"
    assert config.fly_refresh_seconds == 45.0
    assert config.fly_log_lines == 50
    # Untouched fields keep their defaults.
    assert config.ollama_host == "127.0.0.1"
    assert config.tmux_session == "opencode"


def test_load_config_ignores_unknown_keys(tmp_path: Path) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text('title = "X"\nsome_unknown_future_key = "whatever"\n')
    config = load_config(config_file)
    assert config.title == "X"


def test_load_config_malformed_file_falls_back_to_defaults(tmp_path: Path) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text("this is not valid toml [[[")
    config = load_config(config_file)
    assert config == Config()


def test_load_config_wrong_types_fall_back_to_default_value(tmp_path: Path) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text('ollama_port = "not-a-number"\n')
    config = load_config(config_file)
    assert config.ollama_port == Config().ollama_port


def test_opencode_path_blank_means_autodetect(tmp_path: Path) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text('opencode_path = ""\n')
    config = load_config(config_file)
    assert config.opencode_path is None


def test_find_opencode_executable_prefers_configured_path(tmp_path: Path) -> None:
    exe = tmp_path / "opencode"
    _make_executable(exe)
    config = Config(opencode_path=str(exe))
    assert find_opencode_executable(config) == str(exe)


def test_find_opencode_executable_ignores_non_executable_configured_path(tmp_path: Path) -> None:
    exe = tmp_path / "opencode"
    exe.write_text("not executable")
    config = Config(opencode_path=str(exe))
    # Falls through to PATH/well-known dirs, which won't have it either
    # in a clean tmp environment -- as long as it doesn't return the
    # non-executable file, the safety property holds.
    assert find_opencode_executable(config) != str(exe)


def test_find_opencode_executable_via_path(monkeypatch, tmp_path: Path) -> None:
    exe = tmp_path / "opencode"
    _make_executable(exe)

    def fake_which(name: str):
        return str(exe) if name == "opencode" else None

    monkeypatch.setattr("command_center.config.shutil.which", fake_which)
    assert find_opencode_executable(Config()) == str(exe)


def test_find_opencode_executable_via_local_bin(monkeypatch, tmp_path: Path) -> None:
    fake_home = tmp_path
    (fake_home / ".local" / "bin").mkdir(parents=True)
    exe = fake_home / ".local" / "bin" / "opencode"
    _make_executable(exe)

    monkeypatch.setattr("command_center.config.shutil.which", lambda name: None)
    monkeypatch.setattr("command_center.config.Path.home", lambda: fake_home)
    assert find_opencode_executable(Config()) == str(exe)


def test_find_opencode_executable_returns_none_when_missing(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("command_center.config.shutil.which", lambda name: None)
    monkeypatch.setattr("command_center.config.Path.home", lambda: tmp_path)
    assert find_opencode_executable(Config()) is None


def test_build_tmux_opencode_command_is_a_safe_argv_list() -> None:
    cmd = build_tmux_opencode_command("opencode", "/usr/local/bin/opencode")
    assert cmd == ["tmux", "new-session", "-A", "-s", "opencode", "/usr/local/bin/opencode"]
    assert isinstance(cmd, list)
    assert all(isinstance(part, str) for part in cmd)


def test_build_tmux_opencode_command_preserves_dangerous_characters_as_a_single_argument() -> None:
    # No shell is ever involved, so shell metacharacters in a path are
    # just literal characters in one argv element -- never interpreted.
    dangerous_path = "/tmp/evil; rm -rf ~; #.sh"
    cmd = build_tmux_opencode_command("my session", dangerous_path)
    assert cmd[-1] == dangerous_path
    assert cmd.count(dangerous_path) == 1
