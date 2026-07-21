"""Orbital animation scene generator.

Rendering here is a pure function of ``(width, height, tick)`` -- no
curses, no I/O, no module-level mutable state. That makes the whole
scene trivially unit-testable and keeps the animation's only piece of
state (the tick counter) owned by the caller's render loop.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

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


@dataclass
class AnimationFrame:
    """One rendered frame: a grid of characters plus drawing hints.

    ``highlights`` are grid coordinates (row, col) that should be drawn
    with an accent color/attribute -- traveling packets and the passing
    satellite -- so the renderer doesn't need to know anything about the
    scene's geometry.
    """

    lines: list[str] = field(default_factory=list)
    highlights: set[tuple[int, int]] = field(default_factory=set)
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


def render(
    width: int,
    height: int,
    tick: int,
    *,
    reduced_motion: bool = False,
    ascii_only: bool = False,
    status_hint: str | None = None,
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

        # Traveling data packets along the arc.
        if arc_points:
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

    lines = ["".join(row) for row in grid]

    return AnimationFrame(
        lines=lines,
        highlights=highlights,
        scanline_row=None,
        status_text=status_hint or "UPLINK ESTABLISHED",
    )
