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
from command_center.shaggoth import (
    LearningCounter,
    LearningFeed,
    ShaggothState,
    ShaggothStatus,
)
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
    assert layout.telemetry_start_row == 8
    assert layout.telemetry_header_row == 7
    assert layout.anim_top == 4
    assert layout.anim_bottom == 6
    assert layout.anim_height == 3
    assert layout.telemetry_end_row - layout.telemetry_start_row + 1 == TELEMETRY_LINES


def test_compute_layout_taller_terminal_grows_animation_only() -> None:
    small, tall = compute_layout(24), compute_layout(40)
    # Telemetry height is fixed; extra rows all go to the animation.
    assert (small.telemetry_end_row - small.telemetry_start_row) == (
        tall.telemetry_end_row - tall.telemetry_start_row
    )
    assert tall.anim_height == small.anim_height + 16


def _draw(
    screen: FakeScreen,
    flow: AIFlowPhase = AIFlowPhase.IDLE,
    shaggoth_status: ShaggothStatus | None = None,
    feed: LearningFeed | None = None,
    counter: LearningCounter | None = None,
) -> None:
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
        shaggoth_status or ShaggothStatus(),
        counter or LearningCounter(),
        feed or LearningFeed(),
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
    assert "SHAGGOTH" in rows[10] and "TOPICS" in rows[10] and "EPISODES" in rows[10]
    assert "LEARNING" in rows[11] and "WORDS" in rows[11]

    footer = screen.row_text(layout.footer_row)
    assert "[Q]uit" in footer and "[O]penCode" in footer and "[F]ly" in footer
    assert "[G]Shag" in footer


def test_live_learning_counters_render_totals_and_session_gain() -> None:
    screen = FakeScreen(height=24, width=110)
    status = ShaggothStatus(
        state=ShaggothState.ONLINE,
        knowledge_entries=307,
        total_words=238_431,
        total_episodes=1,
    )
    counter = LearningCounter(
        baseline_entries=305, baseline_words=235_178, baseline_episodes=0
    )
    counter.update(status, now=1000.0)

    _draw(screen, shaggoth_status=status, counter=counter)
    layout = compute_layout(24)

    topics_row = screen.row_text(layout.telemetry_start_row + 10)
    words_row = screen.row_text(layout.telemetry_start_row + 11)
    assert "307" in topics_row and "(+2)" in topics_row
    assert "EPISODES 1 (+1)" in topics_row
    assert "238,431" in words_row and "(+3,253)" in words_row


def test_ingestion_ticker_renders_and_scrolls() -> None:
    layout = compute_layout(24)
    feed = LearningFeed(
        events=[f"[{i}] OK   Topic {i}: 2,000 words" for i in range(1, 12)],
        seeded=True,
    )

    first = FakeScreen(height=24, width=110)
    _draw(first, feed=feed)
    ticker_first = first.row_text(layout.telemetry_start_row + 12)
    assert "Topic 1: 2,000 words" in ticker_first

    # A later tick shows a different window of the same feed -- i.e. it moved.
    later = FakeScreen(height=24, width=110)
    _draw_dashboard(
        later,
        Config(),
        RuntimeState(color_mode=False, ascii_only=False, reduced_motion=False),
        Telemetry(hostname="r510"),
        OllamaStatus(),
        AIActivityState.IDLE,
        AIFlowPhase.IDLE,
        None,
        "NONE",
        FlyStatus(),
        ShaggothStatus(),
        LearningCounter(),
        feed,
        tick=200,
        color_available=False,
    )
    assert later.row_text(layout.telemetry_start_row + 12) != ticker_first


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
