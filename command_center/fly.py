"""Optional Fly.io application log monitoring.

The command center delegates authentication to ``flyctl``. A normal Fly login
or ``FLY_ACCESS_TOKEN`` environment variable is enough; this module never
reads, writes, or displays an access token.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from enum import Enum


class FlyState(str, Enum):
    ONLINE = "ONLINE"
    WARN = "WARN"
    ERROR = "ERROR"
    UNAVAILABLE = "UNAVAILABLE"
    DISABLED = "DISABLED"


@dataclass
class FlyStatus:
    """A bounded, redacted snapshot of recent Fly application logs."""

    app_name: str = ""
    state: FlyState = FlyState.DISABLED
    lines: list[str] = field(default_factory=list)
    error_count: int = 0
    warning_count: int = 0
    detail: str = ""

    @property
    def summary(self) -> str:
        if self.state == FlyState.DISABLED:
            return "monitoring disabled"
        if self.state == FlyState.UNAVAILABLE:
            return self.detail or "flyctl unavailable"
        if self.error_count:
            return f"{self.error_count} recent error{'s' if self.error_count != 1 else ''}"
        if self.warning_count:
            return f"{self.warning_count} recent warning{'s' if self.warning_count != 1 else ''}"
        return "recent logs clear"


_SECRET_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{8,}\b"),
    re.compile(r"\b(?:Bearer|Token)\s+[A-Za-z0-9._-]{8,}\b", re.IGNORECASE),
    re.compile(r"\beyJ[A-Za-z0-9._-]{12,}\b"),
)
_ERROR_PATTERN = re.compile(r"\b(error|panic|fatal|exception)\b|\s5\d\d\s", re.IGNORECASE)
_WARNING_PATTERN = re.compile(r"\b(warn|warning)\b", re.IGNORECASE)


def redact_log_line(value: str) -> str:
    """Remove common token shapes before a line reaches the terminal UI."""
    result = value
    for pattern in _SECRET_PATTERNS:
        result = pattern.sub("[REDACTED]", result)
    return result


def _record_text(record: object) -> str:
    if not isinstance(record, dict):
        return ""
    timestamp = str(record.get("timestamp") or "")
    level = str(record.get("level") or "INFO").upper()
    message = str(record.get("message") or "")
    return redact_log_line(f"{timestamp} {level} {message}".strip())


def get_status(app_name: str, max_lines: int = 120, timeout: float = 8.0) -> FlyStatus:
    """Fetch a recent, finite Fly log snapshot without ever streaming.

    Failure is represented in the returned status rather than raised so a
    network issue, missing CLI, or expired login cannot freeze the dashboard.
    """
    app_name = app_name.strip()
    if not app_name:
        return FlyStatus(state=FlyState.DISABLED)
    if shutil.which("flyctl") is None:
        return FlyStatus(app_name=app_name, state=FlyState.UNAVAILABLE, detail="flyctl not installed")

    try:
        result = subprocess.run(
            ["flyctl", "logs", "--app", app_name, "--no-tail", "--json"],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError:
        return FlyStatus(app_name=app_name, state=FlyState.UNAVAILABLE, detail="flyctl not installed")
    except subprocess.TimeoutExpired:
        return FlyStatus(app_name=app_name, state=FlyState.UNAVAILABLE, detail="log request timed out")
    except OSError as exc:
        return FlyStatus(app_name=app_name, state=FlyState.UNAVAILABLE, detail=f"log request failed: {exc}")

    if result.returncode != 0:
        detail = redact_log_line((result.stderr or result.stdout or "Fly log request failed").strip())
        return FlyStatus(app_name=app_name, state=FlyState.UNAVAILABLE, detail=detail[:160])

    lines: list[str] = []
    for raw_line in result.stdout.splitlines():
        try:
            record = json.loads(raw_line)
        except json.JSONDecodeError:
            continue
        text = _record_text(record)
        if text:
            lines.append(text)
    lines = lines[-max(1, max_lines):]
    errors = sum(1 for line in lines if _ERROR_PATTERN.search(line))
    warnings = sum(1 for line in lines if _WARNING_PATTERN.search(line))
    state = FlyState.ERROR if errors else FlyState.WARN if warnings else FlyState.ONLINE
    return FlyStatus(
        app_name=app_name,
        state=state,
        lines=lines,
        error_count=errors,
        warning_count=warnings,
    )
