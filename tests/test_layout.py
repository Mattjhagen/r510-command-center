"""Layout regression tests.

Pins the bottom telemetry block's row coordinates and contents so
animation work can never remove, move, or shrink it, and confirms flow
packets stay inside the animation area.
"""
from __future__ import annotations

from command_center import animation
from command_center.activity import AIActivityState, AIFlowPhase
from command_center.app import TELEMETRY_LINES, RuntimeState, _draw_dashboard, compute_layout
from command_center.config import Config
from command_center.fly import FlyStatus
from command_center.ollama import OllamaStatus
from command_center.telemetry import Telemetry


class FakeScreen:
    """Records every addstr so tests can assert what landed on each row."""

    def __init__(self, height: int = 24, width: int = 80) -> None:
        self._height = height
        self._width = width
        self.calls: list[tuple[int, int, str, int]] = []

    def getmaxyx(self) -> tuple[int, int]:
        return self._height, self._width

    def addstr(self, y: int, x: int, text: str, attr: int = 0) -> None:
        self.calls.append((y, x, text, attr))

    def row_text(self, row: int) -> str:
        return " ".join(text for (y, _x, text, _a) in self.calls if y == row)


def test_compute_layout_80x24() -> None:
    layout = compute_layout(24)
    assert layout.bottom_border_row == 23
    assert layout.footer_row == 22
    assert layout.footer_sep_row == 21
    assert layout.telemetry_end_row == 20
    assert layout.telemetry_start_row == 11
    assert layout.telemetry_header_row == 10
    assert layout.anim_top == 4
    assert layout.anim_bottom == 9
    assert layout.anim_height == 6
    assert layout.telemetry_end_row - layout.telemetry_start_row + 1 == TELEMETRY_LINES


def test_compute_layout_taller_terminal_grows_animation_only() -> None:
    small, tall = compute_layout(24), compute_layout(40)
    # Telemetry height is fixed; extra rows all go to the animation.
    assert (small.telemetry_end_row - small.telemetry_start_row) == (
        tall.telemetry_end_row - tall.telemetry_start_row
    )
    assert tall.anim_height == small.anim_height + 16


def _draw(screen: FakeScreen, flow: AIFlowPhase = AIFlowPhase.IDLE) -> None:
    """Draw the full dashboard onto a fake screen, colors disabled."""
    telemetry = Telemetry(hostname="r510", ipv4="192.168.0.169", cpu_percent=42.0)
    _draw_dashboard(
        screen,
        Config(),
        RuntimeState(color_mode=False, ascii_only=False, reduced_motion=False),
        telemetry,
        OllamaStatus(),
        AIActivityState.IDLE,
        flow,
        None,
        "NONE",
        FlyStatus(),
        tick=9,
        color_available=False,
    )


def test_bottom_telemetry_rows_and_contents_unchanged() -> None:
    # 110 columns so the full command bar fits (it clips on 80 -- that
    # clipping is long-standing behavior, not under test here).
    screen = FakeScreen(height=24, width=110)
    _draw(screen)
    layout = compute_layout(24)

    header = screen.row_text(layout.telemetry_header_row)
    assert "SYSTEM TELEMETRY" in header

    rows = [screen.row_text(layout.telemetry_start_row + i) for i in range(TELEMETRY_LINES)]
    assert "CPU" in rows[0] and "RAM" in rows[0]
    assert "SWAP" in rows[1] and "DISK" in rows[1]
    assert "TEMP" in rows[2] and "LOAD" in rows[2]
    assert "OLLAMA" in rows[4] and "MODEL" in rows[4]
    assert "OPENCODE" in rows[5] and "TMUX" in rows[5]
    assert "HOST r510" in rows[6] and "IP 192.168.0.169" in rows[6]
    assert "UPTIME" in rows[7] and "NET rx" in rows[7]
    assert "FLY ARCHON" in rows[8]
    assert "AI ACTIVITY" in rows[9]

    footer = screen.row_text(layout.footer_row)
    assert "[Q]Exit" in footer and "[O]OpenCode" in footer and "[F]Fly" in footer


def test_debug_overlay_is_gone() -> None:
    # The temporary FLOW diagnostic row was removed; nothing may draw it.
    screen = FakeScreen()
    _draw(screen, flow=AIFlowPhase.PROCESSING)
    assert not any(text.startswith("FLOW:") for (_y, _x, text, _a) in screen.calls)


def test_packet_cells_stay_inside_animation_bounds() -> None:
    for phase in AIFlowPhase:
        for tick in range(0, 300, 11):
            frame = animation.render(
                78, 7, tick,
                flow_phase=phase, cpu_percent=95, ram_percent=95,
                net_bytes_per_sec=10**6,
            )
            for (y, x) in list(frame.packet_cells) + list(frame.trail_cells):
                assert 0 <= y < 7
                assert 0 <= x < 78
