"""Secondary full-screen views: help, logs, models, network, and prompts.

Each function here blocks until the user dismisses the screen (ESC or Q)
and then returns, handing control straight back to the main dashboard
loop. None of them touch external state beyond what is passed in.
"""
from __future__ import annotations

import curses
import subprocess

from . import rendering
from .config import Config
from .fly import FlyStatus
from .ollama import OllamaStatus
from .telemetry import Telemetry, format_rate

EXIT_KEYS = {27, ord("q"), ord("Q")}  # ESC, q, Q


def _wait_for_exit(win) -> None:
    win.nodelay(False)
    win.timeout(-1)
    while True:
        key = win.getch()
        if key in EXIT_KEYS or key == curses.KEY_RESIZE:
            return


def show_help(stdscr, config: Config) -> None:
    stdscr.erase()
    lines = [
        f"{config.title} -- Help",
        "",
        "  O        Open or attach the OpenCode tmux session",
        "  S        Open an interactive shell",
        "  L        View recent Ollama logs (journalctl -u ollama)",
        "  F        View recent Fly logs for the configured application",
        "  M        View installed Ollama models",
        "  R        Restart the Ollama service (confirmation required)",
        "  T        Open htop",
        "  N        View network information",
        "  P        Pause / resume the orbital animation",
        "  C        Toggle color mode",
        "  A        Toggle ASCII-only mode",
        "  H or ?   This help screen",
        "  Q        Quit the dashboard",
        "  ESC      Return from this screen",
        "",
        "Press ESC or Q to return to the dashboard.",
    ]
    max_y, _ = stdscr.getmaxyx()
    for i, line in enumerate(lines):
        if i + 1 >= max_y:
            break
        rendering.safe_addstr(stdscr, i + 1, 2, line)
    stdscr.refresh()
    _wait_for_exit(stdscr)


def show_models(stdscr, config: Config, status: OllamaStatus) -> None:
    stdscr.erase()
    max_y, max_x = stdscr.getmaxyx()
    rendering.safe_addstr(stdscr, 1, 2, "Installed Ollama Models", curses.A_BOLD)
    rendering.draw_hline(stdscr, 2, 2, max(0, max_x - 4), config.ascii_only)

    if status.state.value == "OFFLINE":
        rendering.safe_addstr(stdscr, 4, 2, "Ollama is offline -- no model data available.")
    elif not status.installed_models:
        rendering.safe_addstr(stdscr, 4, 2, "No models installed.")
    else:
        rendering.safe_addstr(stdscr, 4, 2, "(* = currently loaded)")
        for i, name in enumerate(status.installed_models):
            row = 6 + i
            if row + 1 >= max_y:
                rendering.safe_addstr(stdscr, row, 2, "...")
                break
            marker = "*" if name in status.running_models else " "
            rendering.safe_addstr(stdscr, row, 2, f"{marker} {name}")

    rendering.safe_addstr(stdscr, max_y - 1, 2, "Press ESC or Q to return.")
    stdscr.refresh()
    _wait_for_exit(stdscr)


def show_network(stdscr, config: Config, telemetry: Telemetry) -> None:
    stdscr.erase()
    max_y, max_x = stdscr.getmaxyx()
    rendering.safe_addstr(stdscr, 1, 2, "Network", curses.A_BOLD)
    rendering.draw_hline(stdscr, 2, 2, max(0, max_x - 4), config.ascii_only)

    rows = [
        f"Hostname     {telemetry.hostname}",
        f"IPv4         {telemetry.ipv4 or 'unavailable'}",
        f"Receive      {format_rate(telemetry.net_rx_bytes_per_sec)}",
        f"Transmit     {format_rate(telemetry.net_tx_bytes_per_sec)}",
    ]
    for i, line in enumerate(rows):
        rendering.safe_addstr(stdscr, 4 + i, 2, line)

    rendering.safe_addstr(stdscr, max_y - 1, 2, "Press ESC or Q to return.")
    stdscr.refresh()
    _wait_for_exit(stdscr)


def show_logs(stdscr, config: Config, lines: int = 200) -> None:
    """Show recent ``journalctl -u ollama`` output with simple scrolling."""
    stdscr.erase()
    max_y, max_x = stdscr.getmaxyx()
    rendering.safe_addstr(stdscr, 0, 2, "Ollama Logs (journalctl -u ollama)", curses.A_BOLD)

    try:
        result = subprocess.run(
            ["journalctl", "-u", "ollama", "-n", str(lines), "--no-pager"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        content = result.stdout or result.stderr or "(no log output)"
    except FileNotFoundError:
        content = "journalctl is not available on this system."
    except subprocess.TimeoutExpired:
        content = "Timed out reading logs."
    except OSError as exc:
        content = f"Failed to read logs: {exc}"

    log_lines = content.splitlines() or ["(no log output)"]
    view_height = max(1, max_y - 3)
    offset = 0
    max_offset = max(0, len(log_lines) - view_height)

    stdscr.nodelay(False)
    stdscr.timeout(-1)
    while True:
        for row in range(view_height):
            rendering.safe_addstr(stdscr, 2 + row, 0, " " * max(0, max_x - 1))
        for row in range(view_height):
            idx = offset + row
            if idx >= len(log_lines):
                break
            rendering.safe_addstr(stdscr, 2 + row, 2, log_lines[idx][: max(0, max_x - 4)])
        rendering.safe_addstr(
            stdscr,
            max_y - 1,
            2,
            f"Line {offset + 1}-{min(offset + view_height, len(log_lines))} of {len(log_lines)}"
            " -- Up/Down/PgUp/PgDn to scroll, ESC or Q to return.",
        )
        stdscr.refresh()

        key = stdscr.getch()
        if key in EXIT_KEYS:
            return
        if key in (curses.KEY_DOWN, ord("j")):
            offset = min(max_offset, offset + 1)
        elif key in (curses.KEY_UP, ord("k")):
            offset = max(0, offset - 1)
        elif key == curses.KEY_NPAGE:
            offset = min(max_offset, offset + view_height)
        elif key == curses.KEY_PPAGE:
            offset = max(0, offset - view_height)
        elif key == curses.KEY_RESIZE:
            return


def show_fly_logs(stdscr, status: FlyStatus) -> None:
    """Show the latest cached Fly snapshot with the normal scrolling controls."""
    stdscr.erase()
    max_y, max_x = stdscr.getmaxyx()
    title = f"Fly Logs — {status.app_name or 'monitoring disabled'}"
    rendering.safe_addstr(stdscr, 0, 2, title, curses.A_BOLD)

    log_lines = status.lines or [status.summary]
    view_height = max(1, max_y - 3)
    offset = max(0, len(log_lines) - view_height)
    max_offset = max(0, len(log_lines) - view_height)

    stdscr.nodelay(False)
    stdscr.timeout(-1)
    while True:
        for row in range(view_height):
            rendering.safe_addstr(stdscr, 2 + row, 0, " " * max(0, max_x - 1))
        for row in range(view_height):
            idx = offset + row
            if idx >= len(log_lines):
                break
            rendering.safe_addstr(stdscr, 2 + row, 2, log_lines[idx][: max(0, max_x - 4)])
        rendering.safe_addstr(
            stdscr,
            max_y - 1,
            2,
            f"{status.summary} — Up/Down/PgUp/PgDn to scroll, ESC or Q to return.",
        )
        stdscr.refresh()

        key = stdscr.getch()
        if key in EXIT_KEYS:
            return
        if key in (curses.KEY_DOWN, ord("j")):
            offset = min(max_offset, offset + 1)
        elif key in (curses.KEY_UP, ord("k")):
            offset = max(0, offset - 1)
        elif key == curses.KEY_NPAGE:
            offset = min(max_offset, offset + view_height)
        elif key == curses.KEY_PPAGE:
            offset = max(0, offset - view_height)
        elif key == curses.KEY_RESIZE:
            return


def show_message(stdscr, title: str, message_lines: list[str]) -> None:
    """Generic blocking message screen used for errors and notices."""
    stdscr.erase()
    max_y, _ = stdscr.getmaxyx()
    rendering.safe_addstr(stdscr, 1, 2, title, curses.A_BOLD)
    for i, line in enumerate(message_lines):
        row = 3 + i
        if row >= max_y - 1:
            break
        rendering.safe_addstr(stdscr, row, 2, line)
    rendering.safe_addstr(stdscr, max_y - 1, 2, "Press any key to continue.")
    stdscr.refresh()
    stdscr.nodelay(False)
    stdscr.timeout(-1)
    stdscr.getch()


def confirm(stdscr, prompt: str) -> bool:
    """Blocking yes/no confirmation. Only ``y``/``Y`` returns ``True``."""
    stdscr.erase()
    max_y, max_x = stdscr.getmaxyx()
    text = f"{prompt} [y/N]"
    rendering.safe_addstr(stdscr, max_y // 2, max(0, (max_x - len(text)) // 2), text, curses.A_BOLD)
    stdscr.refresh()
    stdscr.nodelay(False)
    stdscr.timeout(-1)
    key = stdscr.getch()
    return key in (ord("y"), ord("Y"))
