"""Sanitization primitives for untrusted display data.

Everything that reaches the dashboard from GitHub, agent reports, process
tables, or SSH telemetry is treated as hostile. This module is the single
choke point through which all external text must pass before it enters the
normalized state model or the frontend.

Guarantees provided here (and asserted by tests):
- ANSI/CSI/OSC escape sequences and terminal control characters are removed.
- Output length is hard-capped.
- HTML rendering in the frontend never uses raw strings; the API emits JSON
  and the UI inserts text via ``textContent`` only. ``escape_html`` exists
  as defense in depth for any server-rendered fragment.
- Process names are reduced to basename; arguments, environment, prompts,
  file contents and secrets are never collected in the first place, but a
  basename re-check runs here so nothing slips through a collector bug.
"""
from __future__ import annotations

import html
import re
import os

# Length caps. Generous enough for real titles/reports, small enough that no
# single field can bloat the state payload or the DOM.
MAX_TITLE_LEN = 200
MAX_SUMMARY_LEN = 400
MAX_REPORT_LINE_LEN = 240
MAX_REPORT_LINES = 24
MAX_PROCESS_NAME_LEN = 64
MAX_ID_LEN = 80

# CSI sequences: ESC [ ... final byte. OSC sequences: ESC ] ... BEL or ST.
_ANSI_CSI_RE = re.compile(r"\x1b\[[0-9:;<=>?]*[ -/]*[@-~]")
_ANSI_OSC_RE = re.compile(r"\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)?")
_ANSI_MISC_RE = re.compile(r"\x1b[@-Z\\-_]")

# Any C0/C1 control character except newline, which downstream code handles
# explicitly (reports are split into lines before sanitization).
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")


def strip_escape_sequences(text: str) -> str:
    """Remove ANSI escape sequences (CSI, OSC, and two-byte escapes)."""
    if not isinstance(text, str):
        return ""
    text = _ANSI_OSC_RE.sub("", text)
    text = _ANSI_CSI_RE.sub("", text)
    text = _ANSI_MISC_RE.sub("", text)
    return text


def strip_control_characters(text: str) -> str:
    """Remove C0/C1 control characters (newline handled by callers)."""
    if not isinstance(text, str):
        return ""
    return _CONTROL_RE.sub("", text)


def sanitize_text(
    value: object,
    max_length: int = MAX_TITLE_LEN,
    collapse_newlines: bool = True,
) -> str:
    """Sanitize an arbitrary value into safe display text.

    - Non-strings become empty strings (never repr'd -- repr can leak data).
    - Escape sequences and control characters are stripped.
    - Newlines collapse to spaces for single-line fields unless
      ``collapse_newlines=False``.
    - Result is capped at ``max_length`` with an ellipsis marker inside the cap.
    """
    if not isinstance(value, str):
        return ""
    text = strip_escape_sequences(value)
    text = strip_control_characters(text)
    if collapse_newlines:
        text = text.replace("\r", " ").replace("\n", " ")
    else:
        text = text.replace("\r\n", "\n").replace("\r", "\n")
    if len(text) > max_length:
        keep = max(max_length - 1, 0)
        text = text[:keep] + "\u2026"
    return text


def sanitize_report_text(value: object) -> list[str]:
    """Sanitize multi-line report text into bounded lines.

    Control characters are stripped per line; each line is capped at
    ``MAX_REPORT_LINE_LEN`` and the number of lines at ``MAX_REPORT_LINES``.
    """
    if not isinstance(value, str):
        return []
    lines_out: list[str] = []
    for raw_line in value.split("\n"):
        line = sanitize_text(raw_line, MAX_REPORT_LINE_LEN)
        if line.strip():
            lines_out.append(line.strip())
        if len(lines_out) >= MAX_REPORT_LINES:
            break
    return lines_out


def basename_only(command: object) -> str:
    """Reduce a command string/path to its basename, sanitized.

    Defense in depth: collectors must already send basenames, but this
    function guarantees no path components, arguments, or shell metacharacter
    payloads survive even if a future collector misbehaves.
    """
    if not isinstance(command, str):
        return ""
    text = strip_escape_sequences(command)
    text = strip_control_characters(text)
    # Split on whitespace first (drops any argument tail), then on path
    # separators, so "/bin/sh -c 'rm -rf /'" collapses to "sh".
    first_token = text.split()
    token = first_token[0] if first_token else ""
    base = os.path.basename(token.replace("\\", "/"))
    return sanitize_text(base, MAX_PROCESS_NAME_LEN)


def escape_html(value: object) -> str:
    """HTML-escape sanitized text (defense in depth; UI prefers textContent)."""
    return html.escape(sanitize_text(value), quote=True)


def sanitize_id(value: object) -> str:
    """Sanitize an identifier (issue keys, node ids): caps and control-strip."""
    return sanitize_text(value, MAX_ID_LEN)
