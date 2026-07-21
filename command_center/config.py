"""Configuration loading for R510 Command Center.

Configuration is entirely optional. Every function here is designed to
degrade to sensible defaults rather than raise -- a missing, empty, or
malformed config file must never prevent the dashboard from starting.
"""
from __future__ import annotations

import os
import shutil
import tomllib
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Optional

CONFIG_DIR = Path.home() / ".config" / "r510-command-center"
CONFIG_PATH = CONFIG_DIR / "config.toml"

DEFAULT_TITLE = "R510 ORBITAL AI COMMAND CENTER"
DEFAULT_OLLAMA_HOST = "127.0.0.1"
DEFAULT_OLLAMA_PORT = 11434
DEFAULT_TMUX_SESSION = "opencode"
DEFAULT_REFRESH_INTERVAL = 1.0
DEFAULT_ANIMATION_SPEED = 1.0
DEFAULT_SCREEN = "dashboard"


@dataclass(frozen=True)
class Config:
    """Immutable, fully-defaulted dashboard configuration."""

    title: str = DEFAULT_TITLE
    ollama_host: str = DEFAULT_OLLAMA_HOST
    ollama_port: int = DEFAULT_OLLAMA_PORT
    opencode_path: Optional[str] = None
    tmux_session: str = DEFAULT_TMUX_SESSION
    refresh_interval: float = DEFAULT_REFRESH_INTERVAL
    animation_speed: float = DEFAULT_ANIMATION_SPEED
    color_mode: bool = True
    reduced_motion: bool = False
    ascii_only: bool = False
    default_screen: str = DEFAULT_SCREEN
    autostart_tty1: bool = False

    @property
    def ollama_base_url(self) -> str:
        return f"http://{self.ollama_host}:{self.ollama_port}"


def _coerce(value: Any, default: Any) -> Any:
    """Best-effort coercion of a raw TOML value to the default's type.

    Falls back to the default itself if coercion fails, so a typo in the
    config file (e.g. a string where a number is expected) degrades
    gracefully instead of crashing the dashboard on startup.
    """
    if value is None:
        return default
    try:
        if isinstance(default, bool):
            return bool(value)
        if isinstance(default, int):
            return int(value)
        if isinstance(default, float):
            return float(value)
        if isinstance(default, str):
            return str(value)
    except (TypeError, ValueError):
        return default
    return value


def load_config(path: Optional[Path] = None) -> Config:
    """Load configuration from TOML, filling in defaults for anything
    missing, malformed, or absent. Never raises.
    """
    config_path = path or CONFIG_PATH
    defaults = Config()
    if not config_path.exists():
        return defaults

    try:
        raw = tomllib.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError):
        return defaults

    if not isinstance(raw, dict):
        return defaults

    values: dict[str, Any] = {}
    for field_name in defaults.__dataclass_fields__:
        if field_name == "opencode_path":
            continue
        if field_name in raw:
            values[field_name] = _coerce(raw[field_name], getattr(defaults, field_name))

    if "opencode_path" in raw:
        raw_path = raw["opencode_path"]
        values["opencode_path"] = str(raw_path) if raw_path else None

    try:
        return replace(defaults, **values)
    except TypeError:
        return defaults


def ensure_config_dir() -> Path:
    """Create the config directory (and parents) if it does not exist."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    return CONFIG_DIR


def default_config_toml() -> str:
    """Return the annotated TOML text written for a freshly created config."""
    return """# R510 Command Center configuration
# This entire file is optional -- anything left out uses a sensible default.

title = "R510 ORBITAL AI COMMAND CENTER"

ollama_host = "127.0.0.1"
ollama_port = 11434

# Leave blank to auto-detect: PATH, then ~/.opencode/bin, then ~/.local/bin
opencode_path = ""

tmux_session = "opencode"

refresh_interval = 1.0
animation_speed = 1.0

color_mode = true
reduced_motion = false
ascii_only = false

default_screen = "dashboard"

# Whether the installer's TTY1 autostart hook should launch the dashboard.
# Toggling this alone does not install the hook -- see install.sh / README.
autostart_tty1 = false
"""


def find_opencode_executable(config: Optional[Config] = None) -> Optional[str]:
    """Locate the OpenCode executable using the documented search order:

    1. An explicit ``opencode_path`` set in configuration.
    2. ``opencode`` on ``PATH``.
    3. ``~/.opencode/bin/opencode``.
    4. ``~/.local/bin/opencode``.

    Returns ``None`` if no candidate is found or executable.
    """
    if config and config.opencode_path:
        candidate = Path(config.opencode_path).expanduser()
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)

    found = shutil.which("opencode")
    if found:
        return found

    for candidate in (
        Path.home() / ".opencode" / "bin" / "opencode",
        Path.home() / ".local" / "bin" / "opencode",
    ):
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)

    return None


def build_tmux_opencode_command(session: str, executable: str) -> list[str]:
    """Build an argv list equivalent to::

        tmux new-session -A -s <session> <executable>

    Returned as a list so the command is never passed through a shell and
    no quoting is required, even if the session name or executable path
    contains spaces or shell metacharacters.
    """
    return ["tmux", "new-session", "-A", "-s", session, executable]
