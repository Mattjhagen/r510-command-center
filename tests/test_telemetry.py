"""Tests for telemetry formatting and progress bar calculations."""
from __future__ import annotations

from command_center.telemetry import (
    Telemetry,
    TelemetryCollector,
    calc_progress_bar,
    format_bytes,
    format_rate,
    format_uptime,
)


def test_format_bytes_scales_units() -> None:
    assert format_bytes(0) == "0B"
    assert format_bytes(512) == "512B"
    assert format_bytes(2048) == "2.0K"
    assert format_bytes(1024 * 1024) == "1.0M"
    assert format_bytes(1024 * 1024 * 1024 * 3) == "3.0G"


def test_format_rate_appends_per_second() -> None:
    assert format_rate(1024) == "1.0K/s"


def test_format_uptime_variants() -> None:
    assert format_uptime(5) == "5s"
    assert format_uptime(65) == "1m 05s"
    assert format_uptime(3665) == "1h 1m"
    assert format_uptime(90000) == "1d 1h 0m"


def test_format_uptime_clamps_negative_to_zero() -> None:
    assert format_uptime(-100) == "0s"


def test_calc_progress_bar_bounds_and_width() -> None:
    bar = calc_progress_bar(50, 10)
    assert len(bar) == 10
    assert bar == "█████░░░░░"


def test_calc_progress_bar_clamps_out_of_range_percent() -> None:
    assert calc_progress_bar(-20, 10) == "░" * 10
    assert calc_progress_bar(150, 10) == "█" * 10


def test_calc_progress_bar_ascii_only_mode() -> None:
    bar = calc_progress_bar(50, 10, ascii_only=True)
    assert set(bar) <= {"#", "-"}
    assert bar.count("#") == 5


def test_calc_progress_bar_zero_width_is_empty() -> None:
    assert calc_progress_bar(50, 0) == ""
    assert calc_progress_bar(50, -5) == ""


def test_telemetry_percent_properties_avoid_division_by_zero() -> None:
    snapshot = Telemetry(ram_used=0, ram_total=0, swap_used=0, swap_total=0, disk_used=0, disk_total=0)
    assert snapshot.ram_percent == 0.0
    assert snapshot.swap_percent == 0.0
    assert snapshot.disk_percent == 0.0


def test_telemetry_percent_properties_compute_correctly() -> None:
    snapshot = Telemetry(ram_used=50, ram_total=200)
    assert snapshot.ram_percent == 25.0


def test_telemetry_collector_collect_never_raises() -> None:
    collector = TelemetryCollector()
    snapshot = collector.collect()
    assert isinstance(snapshot, Telemetry)
    assert snapshot.hostname
    # A second collection exercises the network-rate delta path.
    snapshot2 = collector.collect()
    assert isinstance(snapshot2, Telemetry)


def test_telemetry_collector_survives_psutil_being_unavailable(monkeypatch) -> None:
    monkeypatch.setattr("command_center.telemetry.psutil", None)
    collector = TelemetryCollector()
    snapshot = collector.collect()
    assert snapshot.error == "psutil is not installed"
