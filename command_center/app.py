"""Main curses application loop for R510 Command Center.

Ties together configuration, telemetry, Ollama status, the orbital
animation, and the secondary screens/actions into a single responsive
render loop targeting roughly 5-10 frames per second.
"""
from __future__ import annotations

import curses
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Optional

from . import actions, activity, animation, ollama, rendering, screens
from .config import Config, find_opencode_executable, load_config
from .telemetry import Telemetry, TelemetryCollector, format_rate, format_uptime

MIN_WIDTH = 64
MIN_HEIGHT = 20
TARGET_FPS = 7
FRAME_DELAY_MS = max(80, int(1000 / TARGET_FPS))
SLOW_REFRESH_SECONDS = 3.0
TELEMETRY_LINES = 9

# Observable activity summary phases shown while AI work is detected as
# ACTIVE. These are generic pipeline stages, not model output -- no
# prompts, responses, or reasoning ever appear here.
AI_BUSY_PHASES = (
    "analyzing context",
    "planning next action",
    "evaluating tools",
    "generating response",
    "finalizing output",
)
AI_PHASE_TICKS = TARGET_FPS * 2  # rotate busy phases roughly every two seconds

KEY_ACTIONS = {"o", "s", "l", "m", "r", "t", "n", "h", "?"}


@dataclass
class RuntimeState:
    """Mutable, per-session runtime toggles.

    Kept as an instance owned by :func:`run` rather than module-level
    state, so nothing here is shared or reused across dashboard runs
    (relevant mainly for the test suite, which exercises the same
    process repeatedly).
    """

    color_mode: bool
    ascii_only: bool
    reduced_motion: bool
    paused: bool = False


def main() -> None:
    """Entry point installed as the ``command-center`` console script."""
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        print(
            "r510-command-center: refusing to run as root.\n"
            "Run this as the normal user who owns the session; actions that\n"
            "need elevated privileges (like restarting Ollama) will prompt\n"
            "for sudo individually.",
            file=sys.stderr,
        )
        sys.exit(1)

    os.environ.setdefault("ESCDELAY", "25")
    config = load_config()

    try:
        curses.wrapper(lambda stdscr: run(stdscr, config))
    except KeyboardInterrupt:
        pass
    except curses.error as exc:
        print(f"r510-command-center: terminal error: {exc}", file=sys.stderr)
        sys.exit(1)


def run(stdscr, config: Config) -> None:
    """The main render/input loop. Runs until the user presses Q."""
    curses.curs_set(0)
    stdscr.keypad(True)
    stdscr.timeout(FRAME_DELAY_MS)

    state = RuntimeState(
        color_mode=config.color_mode,
        ascii_only=config.ascii_only,
        reduced_motion=config.reduced_motion,
    )
    color_available = rendering.init_colors()

    telemetry_collector = TelemetryCollector()
    telemetry = telemetry_collector.collect()
    ollama_status = ollama.OllamaStatus()
    opencode_path = find_opencode_executable(config)
    tmux_state = "NONE"
    activity_monitor = activity.ActivityMonitor(config.tmux_session)
    ai_state = activity.AIActivityState.IDLE

    tick = 0
    next_slow_refresh = 0.0

    while True:
        telemetry = telemetry_collector.collect()

        now = time.monotonic()
        if now >= next_slow_refresh:
            ollama_status = ollama.get_status(config.ollama_host, config.ollama_port)
            opencode_path = find_opencode_executable(config)
            tmux_state = _tmux_session_state(config.tmux_session)
            next_slow_refresh = now + SLOW_REFRESH_SECONDS

        opencode_active = activity_monitor.poll(now)
        ai_state = activity.derive_state(ollama_status.state, opencode_active)
        flow_phase = activity.flow_phase(ai_state, activity_monitor.observation(now))

        max_y, max_x = stdscr.getmaxyx()
        stdscr.erase()

        if max_y < MIN_HEIGHT or max_x < MIN_WIDTH:
            _draw_too_small(stdscr, max_y, max_x)
        else:
            _draw_dashboard(
                stdscr,
                config,
                state,
                telemetry,
                ollama_status,
                ai_state,
                flow_phase,
                opencode_path,
                tmux_state,
                tick,
                color_available,
            )

        stdscr.refresh()

        key = stdscr.getch()
        if key != -1:
            outcome = _handle_key(stdscr, key, config, state, telemetry, ollama_status)
            stdscr.keypad(True)
            stdscr.timeout(FRAME_DELAY_MS)
            if outcome == "quit":
                return
            if outcome == "refresh":
                next_slow_refresh = 0.0

        if not state.paused:
            tick += 1


def _handle_key(
    stdscr,
    key: int,
    config: Config,
    state: RuntimeState,
    telemetry: Telemetry,
    ollama_status: ollama.OllamaStatus,
) -> Optional[str]:
    """Dispatch a keypress. Returns ``"quit"``, ``"refresh"``, or ``None``."""
    ch = chr(key) if 0 <= key < 256 else ""
    lower = ch.lower()

    if lower == "q":
        return "quit"
    if lower == "o":
        actions.open_opencode(stdscr, config)
        return "refresh"
    if lower == "s":
        actions.open_shell(stdscr)
        return "refresh"
    if lower == "l":
        screens.show_logs(stdscr, config)
        return None
    if lower == "m":
        screens.show_models(stdscr, config, ollama_status)
        return None
    if lower == "r":
        actions.restart_ollama(stdscr)
        return "refresh"
    if lower == "t":
        actions.open_htop(stdscr)
        return "refresh"
    if lower == "n":
        screens.show_network(stdscr, config, telemetry)
        return None
    if lower == "h" or ch == "?":
        screens.show_help(stdscr, config)
        return None
    if lower == "p":
        state.paused = not state.paused
        return None
    if lower == "c":
        state.color_mode = not state.color_mode
        return None
    if lower == "a":
        state.ascii_only = not state.ascii_only
        return None
    return None


def _ai_activity_text(state: activity.AIActivityState, tick: int, ascii_only: bool) -> str:
    """Short, observable AI activity summary for the telemetry footer row.

    Pure function of the derived activity state and the animation tick.
    While ACTIVE it slowly cycles through generic pipeline-stage phrases
    with a small animated dot suffix; other states map to a single
    static phrase.
    """
    if state == activity.AIActivityState.ACTIVE:
        phase = AI_BUSY_PHASES[(tick // AI_PHASE_TICKS) % len(AI_BUSY_PHASES)]
        dot = "." if ascii_only else "·"
        dots = dot * ((tick // 4) % 3 + 1)
        return f"{phase} {dots}"
    if state == activity.AIActivityState.IDLE:
        return "standing by for uplink"
    if state == activity.AIActivityState.OFFLINE:
        return "uplink offline"
    return "telemetry unavailable"


def _tmux_session_state(session: str) -> str:
    """One of ``ATTACHED``, ``DETACHED``, ``NONE``, or ``N/A``."""
    if shutil.which("tmux") is None:
        return "N/A"
    try:
        result = subprocess.run(
            ["tmux", "list-sessions", "-F", "#{session_name}:#{session_attached}"],
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "N/A"
    if result.returncode != 0:
        return "NONE"
    for line in result.stdout.splitlines():
        name, _, attached = line.partition(":")
        if name == session:
            return "ATTACHED" if attached.strip() == "1" else "DETACHED"
    return "NONE"


def _draw_too_small(stdscr, max_y: int, max_x: int) -> None:
    message = f"Terminal too small ({max_x}x{max_y}). Resize to at least {MIN_WIDTH}x{MIN_HEIGHT}."
    y = max(0, max_y // 2)
    x = max(0, (max_x - len(message)) // 2)
    rendering.safe_addstr(stdscr, y, x, message)


# Packet colors: amber for processing power, cyan for memory, green for
# a response returning, red for the error state. Falls back to bold
# monochrome via attr() when color is unavailable or toggled off.
_PACKET_COLOR = {
    animation.PacketKind.CPU: rendering.COLOR_PAIR_WARN,
    animation.PacketKind.RAM: rendering.COLOR_PAIR_NORMAL,
    animation.PacketKind.RESPONSE: rendering.COLOR_PAIR_GOOD,
    animation.PacketKind.ERROR: rendering.COLOR_PAIR_BAD,
    animation.PacketKind.IDLE: rendering.COLOR_PAIR_ACCENT,
}

_OLLAMA_COLOR = {
    ollama.OllamaState.ONLINE: rendering.COLOR_PAIR_GOOD,
    ollama.OllamaState.BUSY: rendering.COLOR_PAIR_WARN,
    ollama.OllamaState.IDLE: rendering.COLOR_PAIR_NORMAL,
    ollama.OllamaState.OFFLINE: rendering.COLOR_PAIR_DIM,
    ollama.OllamaState.ERROR: rendering.COLOR_PAIR_BAD,
}


def _draw_dashboard(
    stdscr,
    config: Config,
    state: RuntimeState,
    telemetry: Telemetry,
    ollama_status: ollama.OllamaStatus,
    ai_state: activity.AIActivityState,
    flow_phase: activity.AIFlowPhase,
    opencode_path: Optional[str],
    tmux_state: str,
    tick: int,
    color_available: bool,
) -> None:
    max_y, max_x = stdscr.getmaxyx()
    ascii_only = state.ascii_only
    use_color = state.color_mode and color_available

    def attr(pair: int, bold: bool = False) -> int:
        base = curses.color_pair(pair) if use_color else 0
        return base | curses.A_BOLD if bold else base

    normal = attr(rendering.COLOR_PAIR_NORMAL)
    dim = attr(rendering.COLOR_PAIR_DIM)

    rendering.draw_box(stdscr, 0, 0, max_y, max_x, ascii_only, normal)

    content_width = max_x - 2
    rendering.safe_addstr(
        stdscr, 1, 1,
        rendering.center_text(config.title, content_width),
        attr(rendering.COLOR_PAIR_ACCENT, bold=True),
    )

    status_hint = "PROCESSING" if ai_state == activity.AIActivityState.ACTIVE else "UPLINK ESTABLISHED"
    separator = "-" if ascii_only else "·"
    subtitle = f"NODE ONLINE {separator} {status_hint}"
    rendering.safe_addstr(stdscr, 2, 1, rendering.center_text(subtitle, content_width), dim)

    rendering.draw_hline(stdscr, 3, 1, content_width, ascii_only, normal)

    # Layout, computed bottom-up so the telemetry block always keeps its
    # fixed height and the animation simply gets whatever space is left.
    bottom_border_row = max_y - 1
    footer_row = bottom_border_row - 1
    footer_sep_row = footer_row - 1
    telemetry_end_row = footer_sep_row - 1
    telemetry_start_row = telemetry_end_row - TELEMETRY_LINES + 1
    telemetry_header_row = telemetry_start_row - 1
    anim_top = 4
    anim_bottom = telemetry_header_row - 1
    anim_height = max(0, anim_bottom - anim_top + 1)

    if anim_height >= 3 and content_width >= 20:
        frame = animation.render(
            content_width,
            anim_height,
            tick,
            reduced_motion=state.reduced_motion,
            ascii_only=ascii_only,
            status_hint=status_hint,
            flow_phase=flow_phase,
            cpu_percent=telemetry.cpu_percent,
            ram_percent=telemetry.ram_percent,
            net_bytes_per_sec=telemetry.net_rx_bytes_per_sec + telemetry.net_tx_bytes_per_sec,
            resource_flow=config.resource_flow,
            max_flow_packets=config.max_flow_packets,
            flow_intensity=config.flow_intensity,
        )
        for i, line in enumerate(frame.lines):
            row = anim_top + i
            line_attr = dim
            if frame.scanline_row == i:
                line_attr |= curses.A_REVERSE
            rendering.safe_addstr(stdscr, row, 1, line, line_attr)
        accent = attr(rendering.COLOR_PAIR_ACCENT, bold=True)
        for hy, hx in frame.highlights:
            if 0 <= hy < len(frame.lines) and 0 <= hx < len(frame.lines[hy]):
                rendering.safe_addstr(stdscr, anim_top + hy, 1 + hx, frame.lines[hy][hx], accent)
        for (py, px), kind in frame.packet_cells.items():
            if 0 <= py < len(frame.lines) and 0 <= px < len(frame.lines[py]):
                pair = _PACKET_COLOR.get(kind, rendering.COLOR_PAIR_ACCENT)
                rendering.safe_addstr(
                    stdscr, anim_top + py, 1 + px, frame.lines[py][px], attr(pair, bold=True)
                )
    else:
        rendering.safe_addstr(stdscr, anim_top, 1, "[ animation hidden -- widen terminal ]", dim)

    rendering.draw_labeled_hline(stdscr, telemetry_header_row, 1, content_width, "SYSTEM TELEMETRY", ascii_only, normal)

    col1_x = 1
    col2_x = 1 + content_width // 2
    col_width = max(10, col2_x - col1_x - 1)

    def draw_row(row: int, left: str, right: str = "", left_attr: int = 0, right_attr: int = 0) -> None:
        rendering.safe_addstr(stdscr, row, col1_x, left[:col_width], left_attr or normal)
        if right:
            rendering.safe_addstr(stdscr, row, col2_x, right, right_attr or normal)

    bar_width = 16
    row = telemetry_start_row

    rendering.safe_addstr(stdscr, row, col1_x, "CPU  ", normal)
    rendering.draw_progress_bar(stdscr, row, col1_x + 5, bar_width, telemetry.cpu_percent, ascii_only, normal)
    rendering.safe_addstr(stdscr, row, col2_x, "RAM  ", normal)
    rendering.draw_progress_bar(stdscr, row, col2_x + 5, bar_width, telemetry.ram_percent, ascii_only, normal)
    row += 1

    rendering.safe_addstr(stdscr, row, col1_x, "SWAP ", normal)
    rendering.draw_progress_bar(stdscr, row, col1_x + 5, bar_width, telemetry.swap_percent, ascii_only, normal)
    rendering.safe_addstr(stdscr, row, col2_x, "DISK ", normal)
    rendering.draw_progress_bar(stdscr, row, col2_x + 5, bar_width, telemetry.disk_percent, ascii_only, normal)
    row += 1

    temp_str = f"{telemetry.temperature_c:.0f}C" if telemetry.temperature_c is not None else "N/A"
    la = telemetry.load_avg
    draw_row(row, f"TEMP  {temp_str}", f"LOAD  {la[0]:.2f} {la[1]:.2f} {la[2]:.2f}")
    row += 1

    row += 1  # blank line

    state_str = ollama_status.state.value
    state_attr = attr(_OLLAMA_COLOR.get(ollama_status.state, rendering.COLOR_PAIR_NORMAL), bold=True)
    draw_row(row, "OLLAMA", "")
    rendering.safe_addstr(stdscr, row, col1_x + 9, state_str, state_attr)
    rendering.safe_addstr(stdscr, row, col2_x, f"MODEL     {ollama_status.current_model}", normal)
    row += 1

    ready_str = "READY" if opencode_path else "MISSING"
    ready_attr = attr(rendering.COLOR_PAIR_GOOD if opencode_path else rendering.COLOR_PAIR_WARN, bold=True)
    rendering.safe_addstr(stdscr, row, col1_x, "OPENCODE", normal)
    rendering.safe_addstr(stdscr, row, col1_x + 9, ready_str, ready_attr)
    rendering.safe_addstr(stdscr, row, col2_x, f"TMUX      {tmux_state}", normal)
    row += 1

    draw_row(row, f"HOST {telemetry.hostname}"[:col_width], f"IP {telemetry.ipv4 or 'N/A'}")
    row += 1

    users = ",".join(telemetry.logged_in_users) or "-"
    net_str = f"NET rx {format_rate(telemetry.net_rx_bytes_per_sec)} tx {format_rate(telemetry.net_tx_bytes_per_sec)}"
    draw_row(
        row,
        f"UPTIME {format_uptime(telemetry.uptime_seconds)}  PROCS {telemetry.process_count}  USERS {users}",
        net_str,
    )
    row += 1

    ai_active = ai_state == activity.AIActivityState.ACTIVE
    activity_text = _ai_activity_text(ai_state, tick, ascii_only)
    rendering.safe_addstr(stdscr, row, col1_x, "AI ACTIVITY", normal)
    rendering.safe_addstr(
        stdscr, row, col1_x + 13,
        activity_text[: max(0, content_width - 13)],
        attr(rendering.COLOR_PAIR_ACCENT) if ai_active else dim,
    )

    rendering.draw_hline(stdscr, footer_sep_row, 1, content_width, ascii_only, normal)
    keybar = (
        "[O]OpenCode [S]Shell [L]Logs [M]Models [R]Restart [T]Top "
        "[N]Net [P]Pause [C]Color [A]ASCII [H]Help [Q]Exit"
    )
    rendering.safe_addstr(stdscr, footer_row, 1, keybar[:content_width], dim)


if __name__ == "__main__":
    main()
