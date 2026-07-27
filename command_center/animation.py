"""Orbital animation scene generator.

Rendering here is a pure function of ``(width, height, tick)`` -- no
curses, no I/O, no module-level mutable state. That makes the whole
scene trivially unit-testable and keeps the animation's only piece of
state (the tick counter) owned by the caller's render loop.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Sequence

from .activity import AIFlowPhase

# Small planet, deliberately plain ASCII so it renders identically in
# Unicode and ASCII-only mode. Only the surrounding fill characters
# (stars, packets, the uplink arc) change between the two modes.
EARTH_ART = [
    "     .:oOo:.",
    "   .oOOOOOOOo.",
    "  oOOO@@@OOOOOo",
    "  oOO@@@@@OOOoo",
    "  oOOOO@@OOOOOo",
    "   `oOOOOOOo'",
    "     `:oOo:'",
]

CORE_ART = [
    "   .--------.",
    "  / AI  CORE \\",
    " +------------+",
    "  \\  * ** *  /",
    "   '--------'",
]


FORWARD = 1  # Earth -> AI Core (left to right)
REVERSE = -1  # AI Core -> Earth (right to left)


# --------------------------------------------------------------------------
# Aliens
# --------------------------------------------------------------------------
# Two observers watch the uplink and narrate what Shaggoth is learning:
# one standing on Earth (left), one on the satellite (right). Their script
# is supplied by the caller and built from real telemetry, so the joke is
# always about something that actually happened.
#
# Everything alien lives strictly inside the animation grid. The scene can
# get as silly as it likes without ever reaching the telemetry block, which
# is what keeps the dashboard a dashboard.

ALIEN_ART = ["(o.o)", " /|\\ "]
ALIEN_PEEK = "(o.o)"

ALIEN_LINE_TICKS = 28  # ~4 s per line of dialogue at 7 fps
PEEK_PERIOD = 150      # ticks between stray-alien cameos (~21 s)
PEEK_DURATION = 40     # how long a cameo lingers (~6 s)
DROPPING_PERIOD = 45   # ticks between deposits on the floor
MAX_DROPPINGS = 6      # deposits before the floor is mopped
MIN_ALIEN_WIDTH = 46
MIN_ALIEN_HEIGHT = 8


class OverlayStyle(str, Enum):
    """Color intent for an overlay span, resolved by the renderer."""

    AMBER = "amber"
    GREEN = "green"
    BLUE = "blue"
    PURPLE = "purple"
    YELLOW = "yellow"


@dataclass(frozen=True)
class OverlaySpan:
    """A run of characters drawn on top of the base frame in a given color."""

    row: int
    col: int
    text: str
    style: OverlayStyle


class PacketKind(str, Enum):
    """What a traveling packet represents, used to pick its color."""

    CPU = "cpu"
    RAM = "ram"
    RESPONSE = "response"
    ERROR = "error"
    IDLE = "idle"


@dataclass(frozen=True)
class FlowPacket:
    """One packet on the uplink path.

    ``progress`` is the resolved position along the arc (0.0 at Earth,
    1.0 at the AI core); ``direction`` records which way it is moving so
    tests can assert motion without simulating multiple frames.
    """

    progress: float
    kind: PacketKind
    direction: int  # FORWARD or REVERSE


@dataclass
class AnimationFrame:
    """One rendered frame: a grid of characters plus drawing hints.

    ``highlights`` are grid coordinates (row, col) that should be drawn
    with an accent color/attribute -- traveling packets and the passing
    satellite -- so the renderer doesn't need to know anything about the
    scene's geometry. ``packet_cells`` maps grid coordinates to the
    :class:`PacketKind` occupying them, so the renderer can color
    resource-flow packets individually.
    """

    lines: list[str] = field(default_factory=list)
    highlights: set[tuple[int, int]] = field(default_factory=set)
    packet_cells: dict[tuple[int, int], PacketKind] = field(default_factory=dict)
    trail_cells: dict[tuple[int, int], PacketKind] = field(default_factory=dict)
    overlays: list[OverlaySpan] = field(default_factory=list)
    scanline_row: int | None = None
    status_text: str = "UPLINK ESTABLISHED"


def _blit(grid: list[list[str]], art: list[str], top: int, left: int) -> None:
    height = len(grid)
    width = len(grid[0]) if grid else 0
    for dy, row_text in enumerate(art):
        y = top + dy
        if not (0 <= y < height):
            continue
        for dx, ch in enumerate(row_text):
            x = left + dx
            if 0 <= x < width and ch != " ":
                grid[y][x] = ch


def _star_positions(width: int, height: int, count: int) -> list[tuple[int, int, int]]:
    """Deterministic pseudo-random star field as (row, col, phase) triples.

    Uses a cheap multiplicative hash instead of the ``random`` module so
    the field is stable across frames without needing a stored seed --
    calling this twice with the same arguments always yields the same
    stars.
    """
    stars: list[tuple[int, int, int]] = []
    if width <= 0 or height <= 0:
        return stars
    for i in range(count):
        h = (i * 2654435761) & 0xFFFFFFFF
        row = h % height
        col = (h // max(1, height) + i * 17) % width
        phase = (i * 7) % 4
        stars.append((row, col, phase))
    return stars


def _clamp_percent(value: float) -> float:
    """Clamp any input (including NaN, negatives, >100) into 0..100."""
    if not isinstance(value, (int, float)) or value != value:  # NaN check
        return 0.0
    return min(100.0, max(0.0, float(value)))


def _packet_speed(cpu_percent: float) -> float:
    """CPU load -> packet speed in progress-units per tick.

    Monotonic and clamped: idle CPU moves visibly (~9 s to cross),
    saturated CPU stays readable (~2.7 s to cross) instead of becoming
    a blur.
    """
    cpu = _clamp_percent(cpu_percent)
    return 0.016 + (cpu / 100.0) * 0.037


def _cpu_packet_count(cpu_percent: float) -> int:
    """CPU load -> number of processing packets, bounded 1..3."""
    cpu = _clamp_percent(cpu_percent)
    return 1 + (cpu >= 50.0) + (cpu >= 85.0)


def _ram_packet_count(ram_percent: float) -> int:
    """RAM usage -> number of memory packets, bounded 1..3."""
    ram = _clamp_percent(ram_percent)
    return 1 + (ram >= 40.0) + (ram >= 75.0)


def _response_packet_count(net_bytes_per_sec: float) -> int:
    """Observable network throughput -> response packet density, 1..3."""
    rate = float(net_bytes_per_sec)
    if rate != rate or rate < 0.0:  # NaN or negative
        rate = 0.0
    return 1 + (rate >= 1_024) + (rate >= 102_400)


_INTENSITY_FACTOR = {"subtle": 0.75, "normal": 1.0, "vivid": 1.25}


def _scaled_count(count: int, intensity: str) -> int:
    factor = _INTENSITY_FACTOR.get(intensity, 0.75)
    return max(1, round(count * factor))


IDLE_PULSE_PERIOD = 120  # ticks between idle pulses (~17 s at 7 fps)
IDLE_PULSE_SPEED = 0.03


def build_flow_packets(
    tick: int,
    phase: AIFlowPhase,
    cpu_percent: float,
    ram_percent: float,
    net_bytes_per_sec: float = 0.0,
    *,
    max_packets: int = 5,
    intensity: str = "subtle",
) -> list[FlowPacket]:
    """Compute the packets on the uplink path for one frame.

    Deterministic in ``(tick, phase, cpu, ram, net)`` -- no stored
    per-packet state, so pausing or replaying the tick counter replays
    the flow exactly. The result is always bounded by ``max_packets``.
    """
    max_packets = max(0, int(max_packets))
    packets: list[FlowPacket] = []

    if phase == AIFlowPhase.IDLE:
        # Occasional restrained pulse; the link is otherwise just the
        # dotted arc.
        pulse_tick = tick % IDLE_PULSE_PERIOD
        progress = pulse_tick * IDLE_PULSE_SPEED
        if progress < 1.0:
            packets.append(FlowPacket(progress, PacketKind.IDLE, FORWARD))
        return packets[:max_packets]

    if phase == AIFlowPhase.ERROR:
        progress = (tick * 0.02) % 1.0
        packets.append(FlowPacket(progress, PacketKind.ERROR, FORWARD))
        return packets[:max_packets]

    if phase in (AIFlowPhase.UPLOAD, AIFlowPhase.PROCESSING):
        speed = _packet_speed(cpu_percent)
        cpu_count = 1 if phase == AIFlowPhase.UPLOAD else _scaled_count(_cpu_packet_count(cpu_percent), intensity)
        ram_count = _scaled_count(_ram_packet_count(ram_percent), intensity)
        for i in range(cpu_count):
            progress = (tick * speed + i / max(1, cpu_count)) % 1.0
            packets.append(FlowPacket(progress, PacketKind.CPU, FORWARD))
        for i in range(ram_count):
            # Memory packets drift at a steady pace, offset from the CPU
            # packets so the two streams stay distinguishable.
            progress = (tick * 0.036 + (i + 0.5) / max(1, ram_count)) % 1.0
            packets.append(FlowPacket(progress, PacketKind.RAM, FORWARD))
        return packets[:max_packets]

    # RESPONSE: data returning from the AI core to Earth.
    speed = _packet_speed(cpu_percent)
    count = _scaled_count(_response_packet_count(net_bytes_per_sec), intensity)
    for i in range(count):
        progress = 1.0 - ((tick * speed + i / max(1, count)) % 1.0)
        packets.append(FlowPacket(progress, PacketKind.RESPONSE, REVERSE))
    return packets[:max_packets]


PACKET_CHARS = {
    PacketKind.CPU: ("◆", "*"),
    PacketKind.RAM: ("●", "o"),
    PacketKind.RESPONSE: ("✦", "+"),
    PacketKind.ERROR: ("●", "x"),
    PacketKind.IDLE: ("◆", "o"),
}


def speech_bubble(text: str, max_width: int) -> str:
    """Wrap ``text`` in a chat bubble, truncated to ``max_width`` columns.

    Returns an empty string when there is not enough room for a bubble
    with at least a few characters of content -- a bubble reading ``( a )``
    is noise, so it is better to draw nothing.
    """
    if max_width < 8 or not text:
        return ""
    inner_width = max_width - 4  # "( " + " )"
    content = text if len(text) <= inner_width else text[: inner_width - 1].rstrip() + "…"
    return f"( {content} )"


def last_line_for(script: Sequence, index: int, speaker: int) -> str:
    """The most recent line spoken by ``speaker`` at or before ``index``.

    Walking backwards means each alien keeps its last utterance on screen
    while the other one replies, which is what makes two independently
    rendered bubbles read as a single conversation.
    """
    if not script:
        return ""
    index = index % len(script)
    for offset in range(len(script)):
        who, text = script[(index - offset) % len(script)]
        if who == speaker:
            return text
    return ""


def _dropping_positions(tick: int, base_col: int, span: int, count: int) -> list:
    """Deterministic deposit positions for one alien's patch of floor.

    Hashed off the tick bucket rather than ``random`` so the scene stays a
    pure function of the tick -- pausing and resuming replays it exactly.
    """
    positions = []
    bucket = tick // DROPPING_PERIOD
    for i in range(count):
        h = ((bucket - i) * 2654435761 + i * 40503) & 0xFFFFFFFF
        col = base_col + (h % max(1, span))
        kind = "~" if h % 3 == 0 else "o"  # a little of each
        positions.append((col, kind))
    return positions


def _draw_aliens(
    grid: list,
    tick: int,
    script: Sequence,
    ascii_only: bool,
    reduced_motion: bool,
) -> list:
    """Blit the two narrators, their bubbles, cameos, and the floor mess.

    Returns the overlay spans the renderer should color. Writes the same
    characters into ``grid`` so the base pass draws them even if a caller
    ignores the overlays.
    """
    height = len(grid)
    width = len(grid[0]) if grid else 0
    overlays: list = []
    if width < MIN_ALIEN_WIDTH or height < MIN_ALIEN_HEIGHT:
        return overlays

    floor_row = height - 1
    body_row = floor_row - 2
    bubble_row = body_row - 1

    def place(row: int, col: int, text: str, style: OverlayStyle) -> None:
        if not text or not (0 <= row < height):
            return
        col = max(0, min(col, width - 1))
        text = text[: width - col]
        if not text:
            return
        for offset, ch in enumerate(text):
            grid[row][col + offset] = ch
        overlays.append(OverlaySpan(row, col, text, style))

    left_col = 2
    alien_width = max(len(row) for row in ALIEN_ART)
    right_col = max(left_col + alien_width + 2, width - alien_width - 2)

    # The two narrators. Green on Earth, purple on the satellite.
    for dy, art_row in enumerate(ALIEN_ART):
        place(body_row + dy, left_col, art_row, OverlayStyle.GREEN)
        place(body_row + dy, right_col, art_row, OverlayStyle.PURPLE)

    # Speech bubbles, each kept on its own half so they can never collide.
    if script:
        index = tick // ALIEN_LINE_TICKS
        half = max(8, width // 2 - 4)

        left_bubble = speech_bubble(last_line_for(script, index, 0), half)
        place(bubble_row, left_col + 1, left_bubble, OverlayStyle.YELLOW)

        right_text = last_line_for(script, index, 1)
        right_bubble = speech_bubble(right_text, half)
        if right_bubble:
            place(
                bubble_row,
                max(width // 2, width - len(right_bubble) - 1),
                right_bubble,
                OverlayStyle.YELLOW,
            )

    # A third alien wanders in somewhere unhelpful, briefly.
    if not reduced_motion:
        phase = tick % PEEK_PERIOD
        if phase < PEEK_DURATION:
            h = (tick // PEEK_PERIOD) * 2654435761 & 0xFFFFFFFF
            peek_row = h % max(1, max(1, bubble_row - 1))
            peek_col = (h // 7) % max(1, width - len(ALIEN_PEEK))
            place(peek_row, peek_col, ALIEN_PEEK, OverlayStyle.BLUE)

    # ... and they are not house-trained. Deposits accumulate on the floor
    # row -- the last row of the animation, directly above the SYSTEM
    # TELEMETRY rule -- then the floor is mopped and it starts over.
    if not reduced_motion:
        count = (tick // DROPPING_PERIOD) % (MAX_DROPPINGS + 1)
        for base, span in ((left_col, alien_width + 4), (right_col - 4, alien_width + 4)):
            for col, kind in _dropping_positions(tick, base, span, count):
                if kind == "~" and ascii_only:
                    kind = ","
                place(floor_row, col, kind, OverlayStyle.AMBER)

    return overlays


def render(
    width: int,
    height: int,
    tick: int,
    *,
    reduced_motion: bool = False,
    ascii_only: bool = False,
    status_hint: str | None = None,
    flow_phase: AIFlowPhase = AIFlowPhase.IDLE,
    cpu_percent: float = 0.0,
    ram_percent: float = 0.0,
    net_bytes_per_sec: float = 0.0,
    resource_flow: bool = True,
    max_flow_packets: int = 5,
    flow_intensity: str = "subtle",
    aliens: bool = True,
    alien_script: Optional[Sequence] = None,
) -> AnimationFrame:
    """Render one animation frame as a grid of characters.

    Deterministic in ``tick``: the caller owns the tick counter and is
    free to pause it, replay it, or fast-forward it. Small terminals
    (``width < 20`` or ``height < 6``) still return a valid frame, just
    without the Earth/AI-core bodies, since there is no room to draw them
    legibly.
    """
    width = max(width, 0)
    height = max(height, 0)
    if width == 0 or height == 0:
        return AnimationFrame(status_text=status_hint or "UPLINK ESTABLISHED")

    grid = [[" "] * width for _ in range(height)]
    highlights: set[tuple[int, int]] = set()
    packet_cells: dict[tuple[int, int], PacketKind] = {}
    trail_cells: dict[tuple[int, int], PacketKind] = {}

    if width >= 24 and height >= 6:
        earth_top = max(0, (height - len(EARTH_ART)) // 2 - 1)
        earth_left = 2
        core_width = max(len(row) for row in CORE_ART)
        core_left = max(earth_left + 10, width - core_width - 3)
        core_top = max(0, (height - len(CORE_ART)) // 2 - 1)

        _blit(grid, EARTH_ART, earth_top, earth_left)
        _blit(grid, CORE_ART, core_top, core_left)

        # Orbital uplink: a gentle sine arc connecting Earth to the AI core.
        path_start_x = earth_left + max(len(row) for row in EARTH_ART) - 1
        path_end_x = core_left
        path_row_center = (earth_top + core_top) / 2 + 2
        span = max(1, path_end_x - path_start_x)
        arc_points: list[tuple[int, int]] = []
        if path_end_x > path_start_x:
            for x in range(path_start_x, path_end_x):
                t = (x - path_start_x) / span
                y = int(round(path_row_center - math.sin(t * math.pi) * 3))
                if 0 <= y < height and 0 <= x < width:
                    arc_points.append((y, x))
                    if grid[y][x] == " ":
                        grid[y][x] = "." if ascii_only else "·"  # ·

        # Traveling data packets along the arc: colored resource flow
        # when enabled, otherwise the original always-on accent packets.
        if arc_points:
            if resource_flow:
                packets = build_flow_packets(
                    tick,
                    flow_phase,
                    cpu_percent,
                    ram_percent,
                    net_bytes_per_sec,
                    max_packets=1 if reduced_motion else max_flow_packets,
                    intensity=flow_intensity,
                )
                for packet in packets:
                    idx = int(packet.progress * (len(arc_points) - 1))
                    idx = min(len(arc_points) - 1, max(0, idx))
                    y, x = arc_points[idx]
                    unicode_char, ascii_char = PACKET_CHARS[packet.kind]
                    grid[y][x] = ascii_char if ascii_only else unicode_char
                    packet_cells[(y, x)] = packet.kind
                    # One-frame trail: tint the arc dot the packet just
                    # left, so motion direction reads at a glance.
                    if not reduced_motion:
                        trail_idx = idx - packet.direction
                        if 0 <= trail_idx < len(arc_points):
                            ty, tx = arc_points[trail_idx]
                            if (ty, tx) not in packet_cells:
                                trail_cells[(ty, tx)] = packet.kind
                for coord in packet_cells:
                    trail_cells.pop(coord, None)
            else:
                speed = 1 if reduced_motion else 2
                packet_char = "o" if ascii_only else "◆"  # ◆
                num_packets = 1 if reduced_motion else 3
                spacing = max(1, len(arc_points) // max(1, num_packets))
                for p in range(num_packets):
                    idx = (tick * speed + p * spacing) % len(arc_points)
                    y, x = arc_points[idx]
                    grid[y][x] = packet_char
                    highlights.add((y, x))

    # Star field fills whatever empty space remains.
    star_count = min(40, max(0, (width * height) // 60))
    for row, col, phase in _star_positions(width, height, star_count):
        if grid[row][col] != " ":
            continue
        if reduced_motion:
            grid[row][col] = "." if ascii_only else "·"
            continue
        cycle = (tick // 3 + phase) % 4
        if cycle == 0:
            continue  # brief blink-out for a twinkling feel
        grid[row][col] = "*" if cycle == 1 else ("." if ascii_only else "·")

    # An occasional satellite drifting across the top of the scene.
    if not reduced_motion and height > 3 and width > 5:
        period = width + 10
        pos = tick % period
        if pos < width:
            sat_row = 1
            grid[sat_row][pos] = "+" if ascii_only else "✦"  # ✦
            highlights.add((sat_row, pos))

    # Aliens go on last so nothing else can draw over a face or a bubble.
    overlays: list = []
    if aliens:
        overlays = _draw_aliens(grid, tick, alien_script or (), ascii_only, reduced_motion)
        # A packet sharing a cell with an alien would be drawn twice, in two
        # different colors, on the same frame -- drop the packet.
        occupied = {
            (span.row, span.col + i)
            for span in overlays
            for i in range(len(span.text))
        }
        for coord in occupied:
            packet_cells.pop(coord, None)
            trail_cells.pop(coord, None)
            highlights.discard(coord)

    lines = ["".join(row) for row in grid]

    return AnimationFrame(
        lines=lines,
        highlights=highlights,
        packet_cells=packet_cells,
        trail_cells=trail_cells,
        overlays=overlays,
        scanline_row=None,
        status_text=status_hint or "UPLINK ESTABLISHED",
    )
