"""Tests for the resource-aware data-flow animation."""
from __future__ import annotations

from command_center.activity import (
    AIActivityState,
    AIFlowPhase,
    PaneObservation,
    flow_phase,
)
from command_center.animation import (
    FORWARD,
    REVERSE,
    PacketKind,
    _cpu_packet_count,
    _packet_speed,
    _ram_packet_count,
    _response_packet_count,
    build_flow_packets,
    render,
)
from command_center.config import Config, load_config


def test_packet_speed_monotonic_with_cpu() -> None:
    assert _packet_speed(0) < _packet_speed(25) < _packet_speed(50) < _packet_speed(90)


def test_packet_speed_clamped() -> None:
    assert _packet_speed(-50) == _packet_speed(0)
    assert _packet_speed(250) == _packet_speed(100)


def test_ram_packet_count_bounded_and_increasing() -> None:
    counts = [_ram_packet_count(p) for p in (0, 30, 50, 80, 100)]
    assert counts == sorted(counts)
    assert all(1 <= c <= 3 for c in counts)
    assert _ram_packet_count(-10) == 1
    assert _ram_packet_count(500) == 3


def test_cpu_and_response_counts_bounded() -> None:
    assert all(1 <= _cpu_packet_count(p) <= 3 for p in (-5, 0, 60, 100, 400))
    assert all(1 <= _response_packet_count(r) <= 3 for r in (-1, 0, 5_000, 10**9))


def test_processing_phase_moves_left_to_right() -> None:
    a = build_flow_packets(10, AIFlowPhase.PROCESSING, 50, 50)
    b = build_flow_packets(11, AIFlowPhase.PROCESSING, 50, 50)
    assert all(p.direction == FORWARD for p in a)
    assert b[0].progress > a[0].progress


def test_response_phase_moves_right_to_left() -> None:
    a = build_flow_packets(10, AIFlowPhase.RESPONSE, 50, 50)
    b = build_flow_packets(11, AIFlowPhase.RESPONSE, 50, 50)
    assert all(p.direction == REVERSE for p in a)
    assert b[0].progress < a[0].progress


def test_upload_phase_moves_forward() -> None:
    packets = build_flow_packets(5, AIFlowPhase.UPLOAD, 20, 20)
    assert packets
    assert all(p.direction == FORWARD for p in packets)


def test_idle_phase_has_no_resource_packets() -> None:
    for tick in range(0, 240):
        packets = build_flow_packets(tick, AIFlowPhase.IDLE, 90, 90)
        assert all(p.kind == PacketKind.IDLE for p in packets)
        assert len(packets) <= 1


def test_error_phase_is_red_and_single() -> None:
    packets = build_flow_packets(30, AIFlowPhase.ERROR, 90, 90)
    assert [p.kind for p in packets] == [PacketKind.ERROR]


def test_packet_count_never_exceeds_max() -> None:
    for phase in AIFlowPhase:
        for tick in range(0, 60, 7):
            packets = build_flow_packets(
                tick, phase, 100, 100, 10**9, max_packets=3, intensity="vivid"
            )
            assert len(packets) <= 3


def test_ascii_only_frames_use_safe_characters() -> None:
    frame = render(
        80, 12, tick=9, ascii_only=True,
        flow_phase=AIFlowPhase.PROCESSING, cpu_percent=90, ram_percent=90,
    )
    for line in frame.lines:
        assert all(ord(ch) < 128 for ch in line)


def test_packet_cells_reported_for_active_flow() -> None:
    frame = render(
        80, 12, tick=9,
        flow_phase=AIFlowPhase.PROCESSING, cpu_percent=90, ram_percent=90,
    )
    assert frame.packet_cells
    assert all(isinstance(kind, PacketKind) for kind in frame.packet_cells.values())


def test_every_packet_kind_has_a_color_mapping() -> None:
    # Guards the monochrome/no-color fallback path: the renderer looks
    # up each kind and falls back through attr(), so the mapping must be
    # total.
    from command_center.app import _PACKET_COLOR

    assert set(_PACKET_COLOR) == set(PacketKind)


def test_resource_flow_disabled_restores_legacy_packets() -> None:
    frame = render(
        80, 12, tick=9,
        flow_phase=AIFlowPhase.PROCESSING, cpu_percent=90, ram_percent=90,
        resource_flow=False,
    )
    assert not frame.packet_cells
    assert frame.highlights


def test_flow_phase_mapping() -> None:
    idle_obs = PaneObservation()
    assert flow_phase(AIActivityState.IDLE, idle_obs) == AIFlowPhase.IDLE
    assert flow_phase(AIActivityState.OFFLINE, idle_obs) == AIFlowPhase.IDLE
    assert flow_phase(AIActivityState.ERROR, idle_obs) == AIFlowPhase.ERROR

    fresh = PaneObservation(active=True, response_marker=False, active_seconds=0.5)
    assert flow_phase(AIActivityState.ACTIVE, fresh) == AIFlowPhase.UPLOAD

    sustained = PaneObservation(active=True, response_marker=False, active_seconds=10.0)
    assert flow_phase(AIActivityState.ACTIVE, sustained) == AIFlowPhase.PROCESSING

    replying = PaneObservation(active=True, response_marker=True, active_seconds=10.0)
    assert flow_phase(AIActivityState.ACTIVE, replying) == AIFlowPhase.RESPONSE


def test_flow_config_defaults_and_animation_table(tmp_path) -> None:
    defaults = Config()
    assert defaults.resource_flow is True
    assert defaults.max_flow_packets == 5
    assert defaults.flow_intensity == "subtle"

    # Old config files without the new fields keep working.
    old = tmp_path / "old.toml"
    old.write_text('title = "OLD"\n', encoding="utf-8")
    config = load_config(old)
    assert config.title == "OLD"
    assert config.resource_flow is True

    # New fields can live in an [animation] table.
    new = tmp_path / "new.toml"
    new.write_text(
        "[animation]\nresource_flow = false\nmax_flow_packets = 3\n"
        'flow_intensity = "vivid"\n',
        encoding="utf-8",
    )
    config = load_config(new)
    assert config.resource_flow is False
    assert config.max_flow_packets == 3
    assert config.flow_intensity == "vivid"
