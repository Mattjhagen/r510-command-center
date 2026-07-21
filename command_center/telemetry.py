"""System telemetry collection and formatting.

All gathering happens through :class:`TelemetryCollector`, which keeps the
small amount of state needed to compute deltas (network throughput) and to
fall back to the last good reading if a single collection cycle fails.
Formatting helpers are pure functions so they are trivially unit-testable.
"""
from __future__ import annotations

import os
import socket
import time
from dataclasses import dataclass, field
from typing import Optional

try:
    import psutil
except ImportError:  # pragma: no cover - psutil is a mandatory dependency
    psutil = None  # type: ignore[assignment]


@dataclass
class Telemetry:
    """A single point-in-time snapshot of system health."""

    hostname: str = "unknown"
    ipv4: Optional[str] = None
    uptime_seconds: float = 0.0
    cpu_percent: float = 0.0
    per_cpu_percent: list[float] = field(default_factory=list)
    ram_used: int = 0
    ram_total: int = 0
    swap_used: int = 0
    swap_total: int = 0
    disk_used: int = 0
    disk_total: int = 0
    load_avg: tuple[float, float, float] = (0.0, 0.0, 0.0)
    process_count: int = 0
    logged_in_users: list[str] = field(default_factory=list)
    temperature_c: Optional[float] = None
    net_rx_bytes_per_sec: float = 0.0
    net_tx_bytes_per_sec: float = 0.0
    error: Optional[str] = None

    @property
    def ram_percent(self) -> float:
        return _safe_percent(self.ram_used, self.ram_total)

    @property
    def swap_percent(self) -> float:
        return _safe_percent(self.swap_used, self.swap_total)

    @property
    def disk_percent(self) -> float:
        return _safe_percent(self.disk_used, self.disk_total)


def _safe_percent(used: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return max(0.0, min(100.0, (used / total) * 100.0))


def format_bytes(num_bytes: float) -> str:
    """Human-readable byte size, e.g. ``2048`` -> ``"2.0K"``."""
    value = float(abs(num_bytes))
    sign = "-" if num_bytes < 0 else ""
    for unit in ("B", "K", "M", "G", "T", "P"):
        if value < 1024.0:
            if unit == "B":
                return f"{sign}{value:.0f}{unit}"
            return f"{sign}{value:.1f}{unit}"
        value /= 1024.0
    return f"{sign}{value:.1f}E"


def format_rate(bytes_per_sec: float) -> str:
    """Human-readable throughput, e.g. ``"512.0K/s"``."""
    return f"{format_bytes(bytes_per_sec)}/s"


def format_uptime(seconds: float) -> str:
    """Format a duration in seconds as e.g. ``"3d 4h 12m"`` or ``"22m 04s"``."""
    total_seconds = max(0, int(seconds))
    days, remainder = divmod(total_seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, secs = divmod(remainder, 60)
    if days:
        return f"{days}d {hours}h {minutes}m"
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m {secs:02d}s"
    return f"{secs}s"


def calc_progress_bar(percent: float, width: int, ascii_only: bool = False) -> str:
    """Render a fixed-width progress bar fill for a 0-100 percent value.

    Always returns exactly ``width`` characters (or ``""`` if ``width`` is
    not positive). The input percent is clamped into ``[0, 100]`` first, so
    out-of-range readings never produce a malformed bar.
    """
    if width <= 0:
        return ""
    pct = max(0.0, min(100.0, percent))
    filled_char = "#" if ascii_only else "█"  # █
    empty_char = "-" if ascii_only else "░"  # ░
    filled = max(0, min(width, round((pct / 100.0) * width)))
    return filled_char * filled + empty_char * (width - filled)


def get_primary_ipv4() -> Optional[str]:
    """Best-effort local IPv4 address, skipping loopback and link-local."""
    if psutil is None:
        return None
    try:
        interfaces = psutil.net_if_addrs()
    except Exception:
        return None
    for _iface, addrs in interfaces.items():
        for addr in addrs:
            if addr.family == socket.AF_INET:
                ip = addr.address
                if ip and not ip.startswith("127.") and not ip.startswith("169.254."):
                    return ip
    return None


def get_temperature_c() -> Optional[float]:
    """Best-effort CPU/system temperature in Celsius.

    Returns ``None`` when unavailable: non-Linux platforms, missing
    sensors, permission errors, or virtualized hardware all fall through
    to this instead of raising.
    """
    if psutil is None or not hasattr(psutil, "sensors_temperatures"):
        return None
    try:
        temps = psutil.sensors_temperatures()
    except Exception:
        return None
    if not temps:
        return None
    for label in ("coretemp", "cpu_thermal", "k10temp", "acpitz", "zenpower"):
        entries = temps.get(label)
        if entries:
            return entries[0].current
    for entries in temps.values():
        if entries:
            return entries[0].current
    return None


def get_logged_in_users() -> list[str]:
    """Sorted list of distinct logged-in usernames, or ``[]`` if unknown."""
    if psutil is None:
        return []
    try:
        return sorted({u.name for u in psutil.users()})
    except Exception:
        return []


class TelemetryCollector:
    """Stateful collector that tracks network throughput deltas between
    successive samples and remembers the last good snapshot so that a
    single failed collection cycle never blanks the dashboard.
    """

    def __init__(self) -> None:
        self._last_net: Optional[tuple[float, int, int]] = None
        self._last_snapshot = Telemetry()
        if psutil is not None:
            try:
                psutil.cpu_percent(percpu=True)  # prime internal counters
            except Exception:
                pass

    def collect(self) -> Telemetry:
        """Gather a fresh snapshot. Never raises."""
        if psutil is None:
            return Telemetry(error="psutil is not installed")
        try:
            snapshot = self._collect_unsafe()
        except Exception as exc:  # pragma: no cover - defensive catch-all
            fallback = self._last_snapshot
            fallback.error = f"telemetry error: {exc}"
            return fallback
        self._last_snapshot = snapshot
        return snapshot

    def _collect_unsafe(self) -> Telemetry:
        now = time.time()

        vm = psutil.virtual_memory()
        swap = psutil.swap_memory()

        try:
            disk = psutil.disk_usage("/")
            disk_used, disk_total = disk.used, disk.total
        except Exception:
            disk_used, disk_total = 0, 0

        try:
            load_avg = tuple(os.getloadavg())
        except (OSError, AttributeError):
            load_avg = (0.0, 0.0, 0.0)

        try:
            per_cpu = list(psutil.cpu_percent(percpu=True))
        except Exception:
            per_cpu = []
        cpu_percent = sum(per_cpu) / len(per_cpu) if per_cpu else 0.0

        try:
            uptime = now - psutil.boot_time()
        except Exception:
            uptime = 0.0

        try:
            process_count = len(psutil.pids())
        except Exception:
            process_count = 0

        rx_rate = tx_rate = 0.0
        try:
            counters = psutil.net_io_counters()
            if self._last_net is not None:
                last_time, last_rx, last_tx = self._last_net
                elapsed = max(1e-6, now - last_time)
                rx_rate = max(0.0, (counters.bytes_recv - last_rx) / elapsed)
                tx_rate = max(0.0, (counters.bytes_sent - last_tx) / elapsed)
            self._last_net = (now, counters.bytes_recv, counters.bytes_sent)
        except Exception:
            pass

        return Telemetry(
            hostname=socket.gethostname(),
            ipv4=get_primary_ipv4(),
            uptime_seconds=uptime,
            cpu_percent=cpu_percent,
            per_cpu_percent=per_cpu,
            ram_used=vm.used,
            ram_total=vm.total,
            swap_used=swap.used,
            swap_total=swap.total,
            disk_used=disk_used,
            disk_total=disk_total,
            load_avg=load_avg,
            process_count=process_count,
            logged_in_users=get_logged_in_users(),
            temperature_c=get_temperature_c(),
            net_rx_bytes_per_sec=rx_rate,
            net_tx_bytes_per_sec=tx_rate,
        )
