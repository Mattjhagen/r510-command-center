"""Ollama service and API status detection.

State is determined using two independent signals so the dashboard can
tell the difference between "the service is stopped" and "the service is
running but something is wrong":

1. ``systemctl is-active ollama`` -- is the unit itself running?
2. The Ollama HTTP API on ``/api/tags`` and ``/api/ps`` -- is the daemon
   actually answering requests, and is a model currently loaded?

All HTTP calls use a short timeout so an unreachable or hung daemon can
never freeze the render loop.
"""
from __future__ import annotations

import json
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

DEFAULT_TIMEOUT = 0.6


class OllamaState(str, Enum):
    ONLINE = "ONLINE"
    BUSY = "BUSY"  # deprecated: no longer produced by get_status()
    IDLE = "IDLE"
    OFFLINE = "OFFLINE"
    ERROR = "ERROR"


@dataclass
class OllamaStatus:
    state: OllamaState = OllamaState.OFFLINE
    installed_models: list[str] = field(default_factory=list)
    running_models: list[str] = field(default_factory=list)
    detail: str = ""

    @property
    def current_model(self) -> str:
        if self.running_models:
            return self.running_models[0]
        return "-"


def systemctl_is_active(service: str = "ollama", timeout: float = 2.0) -> Optional[bool]:
    """Return ``True``/``False`` for a known systemctl state, or ``None``
    if systemctl itself is unavailable (missing binary, non-systemd host,
    or the check times out).
    """
    try:
        result = subprocess.run(
            ["systemctl", "is-active", service],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None
    return result.stdout.strip() == "active"


def _http_get_json(url: str, timeout: float) -> Optional[dict]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:  # noqa: S310 - local API only
            if response.status != 200:
                return None
            payload = response.read().decode("utf-8")
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return None
    try:
        data = json.loads(payload)
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def parse_tags_response(data: Optional[dict]) -> list[str]:
    """Extract installed model names from a ``/api/tags`` response payload."""
    if not data:
        return []
    models = data.get("models") or []
    names: list[str] = []
    for model in models:
        if not isinstance(model, dict):
            continue
        name = model.get("name") or model.get("model")
        if name:
            names.append(name)
    return names


def parse_ps_response(data: Optional[dict]) -> list[str]:
    """Extract currently loaded model names from a ``/api/ps`` response payload."""
    if not data:
        return []
    models = data.get("models") or []
    names: list[str] = []
    for model in models:
        if not isinstance(model, dict):
            continue
        name = model.get("name") or model.get("model")
        if name:
            names.append(name)
    return names


def get_status(
    host: str = "127.0.0.1",
    port: int = 11434,
    timeout: float = DEFAULT_TIMEOUT,
) -> OllamaStatus:
    """Determine Ollama's current state.

    - ``OFFLINE``: the systemd unit is confirmed not active.
    - ``ERROR``: the unit is active but the HTTP API cannot be reached.
    - ``IDLE``: the API is reachable but no models are installed at all
      (nothing *to* load).
    - ``ONLINE``: the API is reachable and models are installed or
      loaded, ready to serve a request.

    A model appearing in ``/api/ps`` only means it is resident in
    memory, not that it is generating -- so it is never reported as
    ``BUSY`` here. Active generation is detected separately from
    observable signals (see :mod:`command_center.activity`).

    Always returns promptly regardless of the daemon's actual health.
    """
    base_url = f"http://{host}:{port}"
    active = systemctl_is_active("ollama")

    if active is False:
        return OllamaStatus(state=OllamaState.OFFLINE, detail="ollama.service is not active")

    tags = _http_get_json(f"{base_url}/api/tags", timeout)
    if tags is None:
        if active is None:
            return OllamaStatus(state=OllamaState.OFFLINE, detail="ollama API unreachable")
        return OllamaStatus(state=OllamaState.ERROR, detail="service active but API unreachable")

    installed = parse_tags_response(tags)
    ps_data = _http_get_json(f"{base_url}/api/ps", timeout)
    running = parse_ps_response(ps_data)

    if installed or running:
        state = OllamaState.ONLINE
    else:
        state = OllamaState.IDLE

    return OllamaStatus(state=state, installed_models=installed, running_models=running)
