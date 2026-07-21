"""Curses drawing primitives.

Every helper here is defensive on purpose: curses raises when writing to
the terminal's final cell, on windows smaller than the content being
drawn, and on unsupported attributes -- none of that should ever crash
the dashboard, so failures are swallowed and simply result in clipped or
skipped output.
"""
from __future__ import annotations

import curses
from typing import Optional

from .telemetry import calc_progress_bar

COLOR_PAIR_NORMAL = 1
COLOR_PAIR_ACCENT = 2
COLOR_PAIR_GOOD = 3
COLOR_PAIR_WARN = 4
COLOR_PAIR_BAD = 5
COLOR_PAIR_DIM = 6


def init_colors() -> bool:
    """Initialise color pairs. Returns whether color is actually usable."""
    if not curses.has_colors():
        return False
    try:
        curses.start_color()
        try:
            curses.use_default_colors()
            background = -1
        except curses.error:
            background = curses.COLOR_BLACK
        curses.init_pair(COLOR_PAIR_NORMAL, curses.COLOR_CYAN, background)
        curses.init_pair(COLOR_PAIR_ACCENT, curses.COLOR_MAGENTA, background)
        curses.init_pair(COLOR_PAIR_GOOD, curses.COLOR_GREEN, background)
        curses.init_pair(COLOR_PAIR_WARN, curses.COLOR_YELLOW, background)
        curses.init_pair(COLOR_PAIR_BAD, curses.COLOR_RED, background)
        curses.init_pair(COLOR_PAIR_DIM, curses.COLOR_WHITE, background)
        return True
    except curses.error:
        return False


def safe_addstr(win, y: int, x: int, text: str, attr: int = 0) -> None:
    """Write ``text`` clipped to the window bounds.

    Silently ignores the curses edge-of-screen error that comes from
    writing into the terminal's final cell, and does nothing for
    coordinates that are already off-window.
    """
    if not text:
        return
    try:
        max_y, max_x = win.getmaxyx()
    except curses.error:
        return
    if y < 0 or y >= max_y or x >= max_x or x < 0:
        return
    available = max_x - x
    if available <= 0:
        return
    try:
        win.addstr(y, x, text[:available], attr)
    except curses.error:
        pass


def draw_box(win, y: int, x: int, height: int, width: int, ascii_only: bool = False, attr: int = 0) -> None:
    """Draw a border, falling back to plain ASCII when requested or when
    Unicode box-drawing characters are not desired.
    """
    if height < 2 or width < 2:
        return
    if ascii_only:
        top_left, top_right, bottom_left, bottom_right = "+", "+", "+", "+"
        horizontal, vertical = "-", "|"
    else:
        top_left, top_right, bottom_left, bottom_right = "┌", "┐", "└", "┘"
        horizontal, vertical = "─", "│"

    safe_addstr(win, y, x, top_left + horizontal * (width - 2) + top_right, attr)
    for row in range(1, height - 1):
        safe_addstr(win, y + row, x, vertical, attr)
        safe_addstr(win, y + row, x + width - 1, vertical, attr)
    safe_addstr(win, y + height - 1, x, bottom_left + horizontal * (width - 2) + bottom_right, attr)


def draw_hline(win, y: int, x: int, width: int, ascii_only: bool = False, attr: int = 0) -> None:
    ch = "-" if ascii_only else "─"
    safe_addstr(win, y, x, ch * max(0, width), attr)


def draw_labeled_hline(
    win,
    y: int,
    x: int,
    width: int,
    label: str,
    ascii_only: bool = False,
    attr: int = 0,
) -> None:
    """Draw a horizontal rule with a centered ``" LABEL "`` embedded in it,
    e.g. ``──────── SYSTEM TELEMETRY ────────``.
    """
    ch = "-" if ascii_only else "─"
    width = max(0, width)
    text = f" {label} " if label else ""
    if len(text) >= width:
        safe_addstr(win, y, x, ch * width, attr)
        return
    left_fill = (width - len(text)) // 2
    right_fill = width - len(text) - left_fill
    safe_addstr(win, y, x, ch * left_fill + text + ch * right_fill, attr)


def draw_progress_bar(
    win,
    y: int,
    x: int,
    width: int,
    percent: float,
    ascii_only: bool = False,
    attr: int = 0,
    fill_attr: Optional[int] = None,
) -> None:
    """Draw a ``[####----]``-style bar, ``width`` characters wide
    including the surrounding brackets.
    """
    inner_width = max(0, width - 2)
    bar = calc_progress_bar(percent, inner_width, ascii_only=ascii_only)
    safe_addstr(win, y, x, "[", attr)
    safe_addstr(win, y, x + 1, bar, fill_attr if fill_attr is not None else attr)
    safe_addstr(win, y, x + 1 + inner_width, "]", attr)


def center_text(text: str, width: int) -> str:
    """Center ``text`` within ``width`` columns, truncating if too long."""
    if width <= 0:
        return ""
    if len(text) >= width:
        return text[:width]
    pad = width - len(text)
    left = pad // 2
    return " " * left + text + " " * (pad - left)
