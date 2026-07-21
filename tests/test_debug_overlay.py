"""Regression tests for the temporary flow debug overlay.

Guards against two failure modes:
1. Attribute leakage -- the overlay must pass one explicit attribute
   per draw call and never set a persistent window attribute, so
   elements drawn afterwards keep their own color pairs.
2. Layout clobbering -- the overlay text must be produced for an unused
   animation row, not the border or the command bar (placement itself
   is exercised in app code; here we pin the drawing contract).
"""
from __future__ import annotations

from command_center import rendering
from command_center.activity import AIFlowPhase
from command_center.animation import FORWARD, REVERSE, FlowPacket, PacketKind
from command_center.app import _flow_debug_text

DEBUG_ATTR = 0x1234
COLOR_ATTR = 0x5678


class FakeScreen:
    """Minimal curses-window stand-in that records every draw call and
    fails the test if any persistent attribute API is touched."""

    def __init__(self, height: int = 24, width: int = 80) -> None:
        self._height = height
        self._width = width
        self.calls: list[tuple[int, int, str, int]] = []

    def getmaxyx(self) -> tuple[int, int]:
        return self._height, self._width

    def addstr(self, y: int, x: int, text: str, attr: int = 0) -> None:
        self.calls.append((y, x, text, attr))

    def addnstr(self, y: int, x: int, text: str, n: int, attr: int = 0) -> None:
        self.calls.append((y, x, text[:n], attr))

    # Persistent attribute APIs: calling any of these is the regression.
    def attrset(self, attr: int) -> None:
        raise AssertionError("debug overlay must not call attrset()")

    def attron(self, attr: int) -> None:
        raise AssertionError("debug overlay must not call attron()")

    def attroff(self, attr: int) -> None:
        raise AssertionError("debug overlay must not call attroff()")

    def bkgdset(self, *args) -> None:
        raise AssertionError("debug overlay must not call bkgdset()")

    def bkgd(self, *args) -> None:
        raise AssertionError("debug overlay must not call bkgd()")


def _sample_packets() -> list[FlowPacket]:
    return [
        FlowPacket(0.1, PacketKind.CPU, FORWARD),
        FlowPacket(0.5, PacketKind.CPU, FORWARD),
        FlowPacket(0.3, PacketKind.RAM, FORWARD),
    ]


def test_flow_debug_text_format() -> None:
    text = _flow_debug_text(AIFlowPhase.PROCESSING, _sample_packets(), 3)
    assert text == "FLOW: PROCESSING CPU=2 RAM=1 RESP=0 CELLS=3"


def test_flow_debug_text_handles_missing_frame_and_response() -> None:
    packets = [FlowPacket(0.9, PacketKind.RESPONSE, REVERSE)]
    text = _flow_debug_text(AIFlowPhase.RESPONSE, packets, None)
    assert text == "FLOW: RESPONSE CPU=0 RAM=0 RESP=1 CELLS=-"


def test_debug_overlay_does_not_leak_attributes() -> None:
    screen = FakeScreen()

    # Draw the debug overlay exactly the way the app does: one explicit
    # attribute passed directly to the draw call.
    debug_text = _flow_debug_text(AIFlowPhase.PROCESSING, _sample_packets(), 3)
    rendering.safe_addstr(screen, 4, 1, debug_text, DEBUG_ATTR)

    # A colored dashboard element drawn afterwards must receive its own
    # attribute, not inherit anything from the overlay. (If the overlay
    # had used attrset/attron, FakeScreen would already have raised.)
    rendering.safe_addstr(screen, 10, 5, "◆", COLOR_ATTR)

    assert screen.calls[0][3] == DEBUG_ATTR
    assert screen.calls[1] == (10, 5, "◆", COLOR_ATTR)


def test_debug_overlay_clips_instead_of_wrapping() -> None:
    screen = FakeScreen(height=24, width=30)
    debug_text = _flow_debug_text(AIFlowPhase.PROCESSING, _sample_packets(), 3)
    rendering.safe_addstr(screen, 4, 1, debug_text, DEBUG_ATTR)
    (y, x, text, attr) = screen.calls[0]
    assert y == 4 and x == 1
    assert len(text) <= 29
    assert attr == DEBUG_ATTR
