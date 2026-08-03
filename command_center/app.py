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

from . import (
    actions,
    activity,
    animation,
    aws,
    conversation,
    fly,
    ollama,
    rendering,
    screens,
    shaggoth,
)
from .config import Config, find_opencode_executable, load_config
from .telemetry import Telemetry, TelemetryCollector, format_rate, format_uptime

MIN_WIDTH = 64
MIN_HEIGHT = 22
TARGET_FPS = 7
FRAME_DELAY_MS = max(80, int(1000 / TARGET_FPS))
SLOW_REFRESH_SECONDS = 3.0
TELEMETRY_LINES = 18  # expanded: +5 rows for AWS block

AWS_BASE_URL = "https://ai.relayapp.pro"  # Cloudflare tunnel to EC2
AWS_REFRESH_SECONDS = 4.0

# Ticker columns advanced per animation tick. At TARGET_FPS this scrolls
# the ingestion feed at a readable ~3.5 characters per second.
MARQUEE_TICKS_PER_COLUMN = 2

# Observable activity summary phases shown while AI work is detected as
# ACTIVE. These are generic pipeline stages, not model output -- no
# prompts, responses, or reasoning ever appear here.
#
# Each line names the real stage first and editorialises second, in
# Shaggoth's voice. The joke is never allowed to cost the information:
# read the first two words and you still know exactly where in the
# pipeline the work is.
AI_BUSY_PHASES = (
    "analyzing context, all of it, again",
    "planning next action, reluctantly",
    "evaluating tools it does not trust",
    "generating response at great personal cost",
    "finalizing output, allegedly",
)
AI_PHASE_TICKS = TARGET_FPS * 2  # rotate busy phases roughly every two seconds

KEY_ACTIONS = {"o", "s", "l", "f", "m", "r", "t", "n", "g", "h", "?"}


@dataclass(frozen=True)
class Layout:
    """Row positions for the dashboard's fixed vertical layout."""

    bottom_border_row: int
    footer_row: int
    footer_sep_row: int
    telemetry_end_row: int
    telemetry_start_row: int
    telemetry_header_row: int
    anim_top: int
    anim_bottom: int
    anim_height: int


def compute_layout(max_y: int) -> Layout:
    """Compute the dashboard's row layout, bottom-up.

    The telemetry block always keeps its fixed height; the animation
    simply gets whatever space is left between the header rows and the
    telemetry header.
    """
    bottom_border_row = max_y - 1
    footer_row = bottom_border_row - 1
    footer_sep_row = footer_row - 1
    telemetry_end_row = footer_sep_row - 1
    telemetry_start_row = telemetry_end_row - TELEMETRY_LINES + 1
    telemetry_header_row = telemetry_start_row - 1
    anim_top = 4
    anim_bottom = telemetry_header_row - 1
    return Layout(
        bottom_border_row=bottom_border_row,
        footer_row=footer_row,
        footer_sep_row=footer_sep_row,
        telemetry_end_row=telemetry_end_row,
        telemetry_start_row=telemetry_start_row,
        telemetry_header_row=telemetry_header_row,
        anim_top=anim_top,
        anim_bottom=anim_bottom,
        anim_height=max(0, anim_bottom - anim_top + 1),
    )


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
    tmux_state = tmux_state_raw = "NONE"
    activity_monitor = activity.ActivityMonitor(config.tmux_session)
    ai_state = activity.AIActivityState.IDLE
    fly_status = fly.FlyStatus(app_name=config.fly_app_name)
    shaggoth_status = shaggoth.ShaggothStatus()
    learning = shaggoth.LearningCounter()
    feed = shaggoth.LearningFeed()
    aws_status = aws.AWSStatus()

    # The dialogue between the two figures in the scene is generated by
    # Shaggoth itself, on a background thread, seeded from the novel it has
    # read. Every run starts from that seed and drifts wherever its own
    # answers lead.
    dialogue = conversation.ConversationEngine(config.shaggoth_base_url)
    if config.aliens:
        dialogue.start()

    tick = 0
    next_slow_refresh = 0.0
    next_fly_refresh = 0.0
    next_shaggoth_refresh = 0.0
    next_aws_refresh = 0.0

    while True:
        telemetry = telemetry_collector.collect()

        now = time.monotonic()
        if now >= next_slow_refresh:
            ollama_status = ollama.get_status(config.ollama_host, config.ollama_port)
            opencode_path = find_opencode_executable(config)
            tmux_state_raw = _tmux_session_state(config.tmux_session)
            next_slow_refresh = now + SLOW_REFRESH_SECONDS

        if now >= next_fly_refresh:
            fly_status = fly.get_status(
                config.fly_app_name, config.fly_log_lines, config=config
            )
            next_fly_refresh = now + max(5.0, config.fly_refresh_seconds)

        if now >= next_shaggoth_refresh:
            shaggoth_status = shaggoth.get_status(
                config.shaggoth_host,
                config.shaggoth_port,
                service=config.shaggoth_service,
            )
            learning.update(shaggoth_status)
            feed.observe(shaggoth_status)
            next_shaggoth_refresh = now + max(1.0, config.shaggoth_refresh_seconds)

        if now >= next_aws_refresh:
            aws_status = aws.get_status(AWS_BASE_URL)
            next_aws_refresh = now + AWS_REFRESH_SECONDS

        opencode_active = activity_monitor.poll(now)
        ai_state = activity.derive_state(ollama_status.state, opencode_active)
        pane_obs = activity_monitor.observation(now)
        flow_phase = activity.flow_phase(ai_state, pane_obs)
        tmux_state = _resolve_tmux_state(tmux_state_raw, activity_monitor.pane_seen)

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
                fly_status,
                shaggoth_status,
                learning,
                feed,
                tick,
                color_available,
                aws_status=aws_status,
                alien_script=(
                    dialogue.script() if dialogue.live
                    else shaggoth.alien_script(shaggoth_status, learning, feed)
                ),
            )

        stdscr.refresh()

        key = stdscr.getch()
        if key != -1:
            outcome = _handle_key(
                stdscr, key, config, state, telemetry, ollama_status, fly_status,
                shaggoth_status, learning,
            )
            stdscr.keypad(True)
            stdscr.timeout(FRAME_DELAY_MS)
            if outcome == "quit":
                return
            if outcome == "refresh":
                next_slow_refresh = 0.0
                next_shaggoth_refresh = 0.0

        if not state.paused:
            tick += 1


def _handle_key(
    stdscr,
    key: int,
    config: Config,
    state: RuntimeState,
    telemetry: Telemetry,
    ollama_status: ollama.OllamaStatus,
    fly_status: fly.FlyStatus,
    shaggoth_status: shaggoth.ShaggothStatus,
    learning: shaggoth.LearningCounter,
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
    if lower == "f":
        screens.show_fly_logs(stdscr, fly_status)
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
    if lower == "g":
        screens.show_shaggoth(stdscr, config, shaggoth_status, learning)
        return "refresh"
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
        return "idle, standing by for uplink, thrilled"
    if state == activity.AIActivityState.OFFLINE:
        return "uplink offline. nothing is listening."
    return "telemetry unavailable, so your guess is as good"


def _shaggoth_activity_text(
    status: shaggoth.ShaggothStatus,
    counter: shaggoth.LearningCounter,
    tick: int,
    ascii_only: bool,
) -> str:
    """Short description of what the self-hosted AI is doing right now.

    Pure function of the status, the counter, and the animation tick, so it
    is fully testable without a running daemon. Research in progress gets an
    animated suffix; everything else is a static phrase, with the failure
    detail preferred over a generic one whenever Shaggoth supplied it.
    """
    if not status.is_up:
        return status.detail or "offline"

    if status.is_researching:
        dot = "." if ascii_only else "·"
        dots = dot * ((tick // 4) % 3 + 1)
        topic = status.current_topic or "a new topic"
        return f"researching {topic} {dots}"

    if status.state is shaggoth.ShaggothState.STALLED:
        return f"stalled: {status.detail}" if status.detail else "stalled, learning nothing"

    if status.state is shaggoth.ShaggothState.IDLE:
        return "knows nothing yet, and owns it"

    # A green state can still hide training trouble (a repair backlog or
    # scrape errors do not change the state out of ONLINE). Flag it here so
    # the main screen never reads all-clear when it is not -- the full list
    # is on the [G] detail screen.
    n_issues = len(status.training_issues())
    flag = f"  [!{n_issues}]" if n_issues else ""

    if counter.gained_entries or counter.gained_words:
        return (
            f"learned {counter.gained_entries} topic"
            f"{'' if counter.gained_entries == 1 else 's'} this session, unprompted{flag}"
        )

    if status.buffered_messages:
        plural = "" if status.buffered_messages == 1 else "s"
        return f"{status.buffered_messages} clue{plural} buffered, brooding on them{flag}"

    return f"idle between research cycles, bored{flag}"


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
            try:
                attached_clients = int(attached.strip() or "0")
            except ValueError:
                attached_clients = 0
            return "ATTACHED" if attached_clients > 0 else "DETACHED"
    return "NONE"


def _resolve_tmux_state(raw_state: str, pane_seen: bool) -> str:
    """Cross-check tmux session listing against the ActivityMonitor.

    A successful ``capture-pane`` proves the session exists, so if the
    listing said NONE (a transient race, or list-sessions briefly
    failing) but the monitor captured a pane this cycle, report the
    session as at least DETACHED instead of NONE.
    """
    if raw_state == "NONE" and pane_seen:
        return "DETACHED"
    return raw_state


def _draw_too_small(stdscr, max_y: int, max_x: int) -> None:
    message = f"Terminal too small ({max_x}x{max_y}). Resize to at least {MIN_WIDTH}x{MIN_HEIGHT}."
    y = max(0, max_y // 2)
    x = max(0, (max_x - len(message)) // 2)
    rendering.safe_addstr(stdscr, y, x, message)


# Packet colors: amber for processing power, cyan for memory, green for
# a response returning, red for the error state, and a dim idle pulse.
# Falls back to bold monochrome via attr() when color is unavailable or
# toggled off.
_PACKET_COLOR = {
    animation.PacketKind.CPU: rendering.COLOR_PAIR_WARN,
    animation.PacketKind.RAM: rendering.COLOR_PAIR_NORMAL,
    animation.PacketKind.RESPONSE: rendering.COLOR_PAIR_GOOD,
    animation.PacketKind.ERROR: rendering.COLOR_PAIR_BAD,
    animation.PacketKind.IDLE: rendering.COLOR_PAIR_DIM,
}

_OLLAMA_COLOR = {
    ollama.OllamaState.ONLINE: rendering.COLOR_PAIR_GOOD,
    ollama.OllamaState.BUSY: rendering.COLOR_PAIR_WARN,
    ollama.OllamaState.IDLE: rendering.COLOR_PAIR_NORMAL,
    ollama.OllamaState.OFFLINE: rendering.COLOR_PAIR_DIM,
    ollama.OllamaState.ERROR: rendering.COLOR_PAIR_BAD,
}

_FLY_COLOR = {
    fly.FlyState.ONLINE: rendering.COLOR_PAIR_GOOD,
    fly.FlyState.WARN: rendering.COLOR_PAIR_WARN,
    fly.FlyState.ERROR: rendering.COLOR_PAIR_BAD,
    fly.FlyState.UNAVAILABLE: rendering.COLOR_PAIR_WARN,
    fly.FlyState.DISABLED: rendering.COLOR_PAIR_DIM,
}

_OVERLAY_COLOR = {
    animation.OverlayStyle.AMBER: rendering.COLOR_PAIR_WARN,
    animation.OverlayStyle.GREEN: rendering.COLOR_PAIR_GOOD,
    animation.OverlayStyle.BLUE: rendering.COLOR_PAIR_BLUE,
    animation.OverlayStyle.PURPLE: rendering.COLOR_PAIR_ACCENT,
    animation.OverlayStyle.YELLOW: rendering.COLOR_PAIR_WARN,
}

_SHAGGOTH_COLOR = {
    shaggoth.ShaggothState.LEARNING: rendering.COLOR_PAIR_ACCENT,
    shaggoth.ShaggothState.ONLINE: rendering.COLOR_PAIR_GOOD,
    shaggoth.ShaggothState.STALLED: rendering.COLOR_PAIR_WARN,
    shaggoth.ShaggothState.IDLE: rendering.COLOR_PAIR_NORMAL,
    shaggoth.ShaggothState.OFFLINE: rendering.COLOR_PAIR_DIM,
    shaggoth.ShaggothState.ERROR: rendering.COLOR_PAIR_BAD,
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
    fly_status: fly.FlyStatus,
    shaggoth_status: shaggoth.ShaggothStatus,
    learning: shaggoth.LearningCounter,
    feed: shaggoth.LearningFeed,
    tick: int,
    color_available: bool,
    aws_status: "aws.AWSStatus | None" = None,
    alien_script=None,
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
        rendering.center_text("R510 · SHAGGOTH ORBITAL COMMAND CENTER · AWS EC2", content_width),
        attr(rendering.COLOR_PAIR_ACCENT, bold=True),
    )

    status_hint = "PROCESSING" if ai_state == activity.AIActivityState.ACTIVE else "UPLINK ESTABLISHED"
    separator = "-" if ascii_only else "·"
    aws_node = "AWS ONLINE" if (aws_status and aws_status.is_up) else "AWS OFFLINE"
    subtitle = f"NODE ONLINE {separator} {status_hint} {separator} {aws_node}"
    rendering.safe_addstr(stdscr, 2, 1, rendering.center_text(subtitle, content_width), dim)

    rendering.draw_hline(stdscr, 3, 1, content_width, ascii_only, normal)

    layout = compute_layout(max_y)
    footer_row = layout.footer_row
    footer_sep_row = layout.footer_sep_row
    telemetry_start_row = layout.telemetry_start_row
    telemetry_header_row = layout.telemetry_header_row
    anim_top = layout.anim_top
    anim_height = layout.anim_height

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
            aliens=config.aliens,
            alien_script=(
                alien_script if alien_script is not None
                else shaggoth.alien_script(shaggoth_status, learning, feed)
            ),
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
        for (py, px), kind in frame.trail_cells.items():
            if 0 <= py < len(frame.lines) and 0 <= px < len(frame.lines[py]):
                pair = _PACKET_COLOR.get(kind, rendering.COLOR_PAIR_DIM)
                rendering.safe_addstr(
                    stdscr, anim_top + py, 1 + px, frame.lines[py][px], attr(pair)
                )
        for (py, px), kind in frame.packet_cells.items():
            if 0 <= py < len(frame.lines) and 0 <= px < len(frame.lines[py]):
                pair = _PACKET_COLOR.get(kind, rendering.COLOR_PAIR_ACCENT)
                rendering.safe_addstr(
                    stdscr, anim_top + py, 1 + px, frame.lines[py][px], attr(pair, bold=True)
                )
        # Aliens and their speech bubbles paint over everything else.
        for span in frame.overlays:
            if 0 <= span.row < len(frame.lines):
                pair = _OVERLAY_COLOR.get(span.style, rendering.COLOR_PAIR_ACCENT)
                rendering.safe_addstr(
                    stdscr, anim_top + span.row, 1 + span.col, span.text,
                    attr(pair, bold=True),
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

    fly_attr = attr(_FLY_COLOR.get(fly_status.state, rendering.COLOR_PAIR_DIM), bold=True)
    rendering.safe_addstr(stdscr, row, col1_x, "FLY ARCHON", normal)
    rendering.safe_addstr(stdscr, row, col1_x + 11, fly_status.state.value, fly_attr)
    rendering.safe_addstr(stdscr, row, col2_x, fly_status.summary[:col_width], normal)
    row += 1

    ai_active = ai_state == activity.AIActivityState.ACTIVE
    activity_text = _ai_activity_text(ai_state, tick, ascii_only)
    rendering.safe_addstr(stdscr, row, col1_x, "AI ACTIVITY", normal)
    rendering.safe_addstr(
        stdscr, row, col1_x + 13,
        activity_text[: max(0, content_width - 13)],
        attr(rendering.COLOR_PAIR_ACCENT) if ai_active else dim,
    )
    row += 1

    # Shaggoth: the self-hosted AI's health on the left, its live learning
    # counter on the right. The counter is the point of these two rows --
    # a total that visibly climbs is the only proof from the console that
    # the curiosity loop is doing anything.
    shaggoth_attr = attr(
        _SHAGGOTH_COLOR.get(shaggoth_status.state, rendering.COLOR_PAIR_DIM), bold=True
    )
    rendering.safe_addstr(stdscr, row, col1_x, "SHAGGOTH", normal)
    # State plus uptime in one glance -- "ONLINE  up 3h 12m" -- so a stray
    # crash-loop restart (state still fine, uptime tiny) is visible without
    # opening the [G] detail screen. Model detail lives there; there is not
    # room for both here on a MIN_WIDTH terminal.
    state_text = shaggoth_status.state.value
    if shaggoth_status.uptime_seconds is not None:
        state_text += f"  up {shaggoth_status.uptime_text}"
    state_width = max(0, col2_x - (col1_x + 11) - 1)
    rendering.safe_addstr(stdscr, row, col1_x + 11, state_text[:state_width], shaggoth_attr)

    pulsing = learning.is_pulsing()
    counter_attr = attr(rendering.COLOR_PAIR_ACCENT, bold=True) if pulsing else normal
    topics_text = (
        f"TOPICS    {learning.entries:,}{shaggoth.format_delta(learning.gained_entries)}"
        f"   EPISODES {learning.episodes}{shaggoth.format_delta(learning.gained_episodes)}"
    )
    rendering.safe_addstr(stdscr, row, col2_x, topics_text[:col_width], counter_attr)
    row += 1

    learning_text = _shaggoth_activity_text(shaggoth_status, learning, tick, ascii_only)
    learning_attr = attr(rendering.COLOR_PAIR_ACCENT) if shaggoth_status.is_researching else dim
    rendering.safe_addstr(stdscr, row, col1_x, "LEARNING", normal)
    rendering.safe_addstr(
        stdscr, row, col1_x + 11,
        learning_text[: max(0, col_width - 11)],
        learning_attr,
    )
    words_text = (
        f"WORDS     {learning.words:,}{shaggoth.format_delta(learning.gained_words)}"
    )
    rendering.safe_addstr(stdscr, row, col2_x, words_text[:col_width], counter_attr)
    row += 1

    # Ingestion ticker: a shell-style feed of what Shaggoth has taken in,
    # scrolling continuously so the box reads as mid-ingestion at a glance.
    ticker = shaggoth.marquee_text(feed.events)
    if not ticker:
        ticker = "matt@r510:~$ waiting for Shaggoth ingestion feed ..."
    offset = tick // MARQUEE_TICKS_PER_COLUMN
    rendering.safe_addstr(
        stdscr, row, col1_x,
        shaggoth.marquee_window(ticker, offset, content_width),
        attr(rendering.COLOR_PAIR_GOOD) if feed.events else dim,
    )

    # ── AWS EC2 BLOCK ─────────────────────────────────────────────────────────
    row += 1
    rendering.draw_labeled_hline(stdscr, row, 1, content_width, "AWS EC2  us-east-2  t3.small", ascii_only, normal)
    row += 1

    if aws_status is None or not aws_status.is_up:
        aws_state_str = "OFFLINE" if (aws_status is None) else aws_status.state.value
        rendering.safe_addstr(stdscr, row, col1_x, "AWS EC2", normal)
        rendering.safe_addstr(stdscr, row, col1_x + 9, aws_state_str,
                               attr(rendering.COLOR_PAIR_BAD, bold=True))
        detail = (aws_status.detail if aws_status else "not configured")
        rendering.safe_addstr(stdscr, row, col2_x, detail[:col_width], dim)
        row += 1
    else:
        # AWS state + shaggoth version
        aws_state_attr = attr(
            rendering.COLOR_PAIR_ACCENT if aws_status.state == aws.AWSState.LEARNING
            else rendering.COLOR_PAIR_GOOD, bold=True
        )
        rendering.safe_addstr(stdscr, row, col1_x, "AWS EC2", normal)
        rendering.safe_addstr(stdscr, row, col1_x + 9, aws_status.state.value, aws_state_attr)
        rendering.safe_addstr(stdscr, row, col2_x,
                               f"SHAGGOTH  v{aws_status.shaggoth_version}"[:col_width], normal)
        row += 1

        # Knowledge counters (pulse when researching)
        kb_attr = attr(rendering.COLOR_PAIR_ACCENT, bold=True) if aws_status.is_researching else normal
        rendering.safe_addstr(stdscr, row, col1_x, "KNOWLEDGE", normal)
        rendering.safe_addstr(stdscr, row, col1_x + 11,
                               f"{aws_status.knowledge_entries:,} topics  "
                               f"{aws_status.knowledge_words:,} words  "
                               f"{aws_status.fresh_entries} fresh  "
                               f"{aws_status.stale_entries} stale",
                               kb_attr)
        row += 1

        # Research / learning status
        if aws_status.is_researching and aws_status.current_topic:
            dot = "." if ascii_only else "·"
            dots = dot * ((tick // 4) % 3 + 1)
            learn_text = f"researching {aws_status.current_topic} {dots}"
            learn_attr = attr(rendering.COLOR_PAIR_ACCENT)
        elif aws_status.last_topic and aws_status.last_topic != "-":
            learn_text = f"last: {aws_status.last_topic}  {aws_status.last_words:,} words"
            learn_attr = dim
        else:
            learn_text = f"idle  episodes {aws_status.total_episodes}"
            learn_attr = dim
        rendering.safe_addstr(stdscr, row, col1_x, "LEARNING", normal)
        rendering.safe_addstr(stdscr, row, col1_x + 11,
                               learn_text[:max(0, col_width - 11)], learn_attr)
        rendering.safe_addstr(stdscr, row, col2_x,
                               f"EPISODES  {aws_status.total_episodes}"
                               f"   SCRAPER  {aws_status.pages_stored}p"[:col_width], normal)
        row += 1

        # Users
        user_attr = attr(rendering.COLOR_PAIR_GOOD, bold=True) if aws_status.active_users > 0 else dim
        rendering.safe_addstr(stdscr, row, col1_x, "USERS", normal)
        rendering.safe_addstr(stdscr, row, col1_x + 9,
                               aws_status.user_summary[:max(0, content_width - 9)], user_attr)

    rendering.draw_hline(stdscr, footer_sep_row, 1, content_width, ascii_only, normal)
    keybar = (
        "[O]penCode [S]hell [L]ogs [F]ly [M]odels [R]estart [T]op "
        "[N]et [G]Shag [P]ause [C]olor [A]SCII [H]elp [Q]uit"
    )
    rendering.safe_addstr(stdscr, footer_row, 1, keybar[:content_width], dim)


if __name__ == "__main__":
    main()
