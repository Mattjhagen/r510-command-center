"""Web dashboard configuration with permission enforcement.

The dashboard config may contain node aliases and a path to a least-privilege
SSH key. Real addresses/keys stay host-local: the shipped default config
contains placeholders only, and the loader refuses (or loudly warns on)
insecure file permissions so secrets never sit world-readable.
"""
from __future__ import annotations

import os
import stat
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

WEBUI_CONFIG_DIR = Path.home() / ".config" / "r510-command-center"
WEBUI_CONFIG_PATH = WEBUI_CONFIG_DIR / "webui.toml"

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8422
DEFAULT_POLL_SECONDS = 5.0
DEFAULT_SSH_TIMEOUT_S = 4.0
DEFAULT_STALE_AFTER_S = 90.0

REQUIRED_MODE = 0o600


@dataclass(frozen=True)
class NodeConfig:
    node_id: str
    role: str
    host_alias: str  # display alias; never a raw address in shipped defaults
    ssh_destination: str  # e.g. alias defined in ~/.ssh/config


@dataclass(frozen=True)
class WebUIConfig:
    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    demo_mode: bool = False
    poll_seconds: float = DEFAULT_POLL_SECONDS
    stale_after_s: float = DEFAULT_STALE_AFTER_S
    ssh_timeout_s: float = DEFAULT_SSH_TIMEOUT_S
    github_enabled: bool = True
    nodes: tuple[NodeConfig, ...] = field(default_factory=tuple)


class ConfigPermissionError(PermissionError):
    """Raised when a config file is readable by group/others."""


def _coerce_float(raw: object, default: float) -> float:
    try:
        return max(0.5, min(float(raw), 3600.0))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def check_config_permissions(path: Path) -> Optional[str]:
    """Return a warning string if permissions are looser than mode 600.

    Raises :class:`ConfigPermissionError` when the file is group/world
    readable -- that is treated as a hard failure because the file may hold
    infrastructure hints.
    """
    st = os.stat(path)
    mode = stat.S_IMODE(st.st_mode)
    if mode & 0o077:
        message = (
            f"config {path} has mode {oct(mode)}; refusing to read "
            f"(expected 600). Fix with: chmod 600 {path}"
        )
        if mode & 0o047:
            raise ConfigPermissionError(message)
        return message
    return None


def load_webui_config(
    path: Optional[Path] = None,
    *,
    enforce_permissions: bool = True,
) -> tuple[WebUIConfig, list[str]]:
    """Load webui.toml. Never crashes the service: malformed files fall back
    to defaults plus a warning. Returns ``(config, warnings)``.

    ``enforce_permissions=False`` exists for tests and demo runs only.
    """
    warnings: list[str] = []
    config_path = path or WEBUI_CONFIG_PATH
    if not config_path.exists():
        return WebUIConfig(), warnings

    try:
        if enforce_permissions:
            check_config_permissions(config_path)
    except ConfigPermissionError:
        raise

    try:
        raw = tomllib.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        return WebUIConfig(), [f"config unreadable, using defaults: {exc}"]

    server = raw.get("server") if isinstance(raw.get("server"), dict) else {}
    nodes_raw = raw.get("nodes") if isinstance(raw.get("nodes"), list) else []

    nodes: list[NodeConfig] = []
    for entry in nodes_raw[:8]:
        if not isinstance(entry, dict):
            continue
        nodes.append(
            NodeConfig(
                node_id=str(entry.get("node_id", ""))[:60],
                role=str(entry.get("role", ""))[:60],
                host_alias=str(entry.get("host_alias", ""))[:60],
                ssh_destination=str(entry.get("ssh_destination", ""))[:120],
            )
        )

    config = WebUIConfig(
        host=str(server.get("host", DEFAULT_HOST))[:64],
        port=int(server.get("port", DEFAULT_PORT)),
        demo_mode=bool(server.get("demo_mode", False)),
        poll_seconds=_coerce_float(
            server.get("poll_seconds", DEFAULT_POLL_SECONDS), DEFAULT_POLL_SECONDS
        ),
        stale_after_s=_coerce_float(
            server.get("stale_after_s", DEFAULT_STALE_AFTER_S), DEFAULT_STALE_AFTER_S
        ),
        ssh_timeout_s=_coerce_float(
            server.get("ssh_timeout_s", DEFAULT_SSH_TIMEOUT_S), DEFAULT_SSH_TIMEOUT_S
        ),
        github_enabled=bool(server.get("github_enabled", True)),
        nodes=tuple(nodes),
    )

    if config.host != DEFAULT_HOST:
        warnings.append(
            f"non-loopback bind requested ({config.host}); loopback is enforced"
        )
        config = WebUIConfig(**{**config.__dict__, "host": DEFAULT_HOST})
    return config, warnings


DEFAULT_WEBUI_TOML = """# r510-command-center web UI configuration (host-local).
# Placeholders only -- replace aliases via your ~/.ssh/config names.
# This file must be chmod 600 when it holds real values.

[server]
host = "127.0.0.1"   # loopback enforced regardless of this value
port = 8422
demo_mode = false
poll_seconds = 5.0
stale_after_s = 90.0
ssh_timeout_s = 4.0
github_enabled = true

[[nodes]]
node_id = "t310-pm"
role = "PM"
host_alias = "t310"
ssh_destination = "t310-telemetry"

[[nodes]]
node_id = "r510-dev"
role = "Developer"
host_alias = "r510"
ssh_destination = "r510-telemetry"

[[nodes]]
node_id = "r410-sec"
role = "Security/QA"
host_alias = "r410"
ssh_destination = "r410-telemetry"
"""
