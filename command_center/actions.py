"""Hotkey actions that shell out to external tools (tmux, bash, sudo, htop).

Anything that needs a real interactive TTY -- a shell, tmux, sudo's
password prompt, htop -- temporarily tears down curses, runs the
subprocess as an argv list (never ``shell=True``), and restores curses
afterwards. This is the same pattern ``curses.wrapper`` itself uses
internally for cleanup.
"""
from __future__ import annotations

import curses
import shutil
import subprocess
from dataclasses import dataclass

from . import screens
from .config import Config, build_tmux_opencode_command, find_opencode_executable


@dataclass
class ActionResult:
    ok: bool
    message: str = ""


def _suspend_curses_and_run(cmd: list[str]) -> ActionResult:
    """Leave curses mode, run ``cmd`` attached to the real terminal, then
    restore curses. ``cmd`` is always a list -- never passed through a
    shell -- so no quoting is required and no injection is possible.
    """
    curses.def_prog_mode()
    curses.endwin()
    ok = True
    message = ""
    try:
        subprocess.call(cmd)
    except FileNotFoundError:
        ok = False
        message = f"Command not found: {cmd[0]}"
    except OSError as exc:
        ok = False
        message = f"Failed to run {cmd[0]}: {exc}"
    finally:
        curses.reset_prog_mode()
        try:
            curses.curs_set(0)
        except curses.error:
            pass
    return ActionResult(ok=ok, message=message)


def open_opencode(stdscr, config: Config) -> None:
    """Create or attach the OpenCode tmux session, equivalent to:

    ``tmux new-session -A -s <session> <opencode executable>``
    """
    executable = find_opencode_executable(config)
    if executable is None:
        screens.show_message(
            stdscr,
            "OpenCode Not Found",
            [
                "OpenCode was not found via PATH, ~/.opencode/bin, or ~/.local/bin.",
                "Install OpenCode, or set opencode_path in config.toml.",
            ],
        )
        return
    if shutil.which("tmux") is None:
        screens.show_message(stdscr, "tmux Not Found", ["Install tmux to use the OpenCode session: sudo apt install tmux"])
        return

    cmd = build_tmux_opencode_command(config.tmux_session, executable)
    result = _suspend_curses_and_run(cmd)
    if not result.ok:
        screens.show_message(stdscr, "OpenCode Session Error", [result.message])


def open_shell(stdscr) -> None:
    """Drop to an interactive shell; returns to the dashboard on exit."""
    shell = shutil.which("bash") or "/bin/sh"
    result = _suspend_curses_and_run([shell])
    if not result.ok:
        screens.show_message(stdscr, "Shell Error", [result.message])


def open_htop(stdscr) -> None:
    if shutil.which("htop") is None:
        screens.show_message(stdscr, "htop Not Found", ["Install htop: sudo apt install htop"])
        return
    result = _suspend_curses_and_run(["htop"])
    if not result.ok:
        screens.show_message(stdscr, "htop Error", [result.message])


def restart_ollama(stdscr) -> None:
    """Restart the Ollama systemd service after an explicit confirmation.

    Uses the caller's normal sudo authentication -- no sudoers changes
    are made and no credentials are cached or stored by this tool.
    """
    if not screens.confirm(stdscr, "Restart the Ollama service?"):
        return
    if shutil.which("sudo") is None:
        screens.show_message(stdscr, "Restart Failed", ["sudo is not available on this system."])
        return
    result = _suspend_curses_and_run(["sudo", "systemctl", "restart", "ollama"])
    if result.ok:
        screens.show_message(stdscr, "Ollama Restart", ["Restart command completed."])
    else:
        screens.show_message(stdscr, "Restart Failed", [result.message])
