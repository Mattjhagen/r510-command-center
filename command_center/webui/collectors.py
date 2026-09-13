"""Read-only collectors feeding the normalized dashboard state.

Hard rules (binding per issue #22):
- Least privilege: node telemetry uses ``ssh -o BatchMode=yes`` with a short
  timeout and a forced-command telemetry script on the remote side; the
  collector never opens an interactive shell and never sends remote commands
  beyond the fixed telemetry probe.
- Fail closed: any timeout, non-zero exit, or unparseable output becomes an
  OFFLINE node with a short reason -- never a crash, never a hang.
- Untrusted input: GitHub payloads and agent reports are sanitized before
  they enter the model; control sequences are stripped at this boundary.
"""
from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Optional

from command_center.webui import sanitize
from command_center.webui.model import (
    NodeState,
    OFFLINE,
    ProcessRow,
    Telemetry,
)
from command_center.webui.todos import TodoPanel, TodoCache, parse_todos

AGENT_STATE_DIR = Path(".agent-state")
MAX_TELEMETRY_BYTES = 4096
MAX_GH_PAYLOAD_BYTES = 262_144
GITHUB_TIMEOUT_S = 6.0

# Fixed forced-command probe. The remote account's authorized_keys should use
# command= with exactly this script so the key can do nothing else.
TELEMETRY_PROBE = "r510-telemetry-probe"


def _run_bounded(argv: list[str], timeout_s: float, max_bytes: int) -> tuple[bool, str, str]:
    """Run argv without a shell under a hard timeout. Returns (ok, stdout, reason)."""
    try:
        proc = subprocess.run(  # noqa: S603 -- fixed argv, no shell
            argv,
            capture_output=True,
            timeout=timeout_s,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return False, "", f"timeout after {timeout_s:.0f}s"
    except OSError as exc:
        return False, "", f"exec failed: {type(exc).__name__}"
    if proc.returncode != 0:
        stderr_tail = sanitize.sanitize_text(proc.stderr.decode("utf-8", "replace"), 120)
        return False, "", stderr_tail or f"exit {proc.returncode}"
    out = proc.stdout[:max_bytes].decode("utf-8", "replace")
    return True, out, ""


def parse_telemetry_output(raw: object) -> Optional[Telemetry]:
    """Parse strict ``key=value`` lines from the forced-command probe.

    Returns None on garbage. Unknown keys are ignored; values must be finite
    numbers within sane ranges or the whole snapshot is rejected.
    """
    if not isinstance(raw, str):
        return None
    fields: dict[str, float] = {}
    for line in raw.splitlines():
        line = sanitize.strip_escape_sequences(line).strip()
        if not line or "=" not in line:
            continue
        key, _, value = line.partition("=")
        try:
            fields[key.strip()] = float(value.strip())
        except ValueError:
            continue
    required = ("cpu_percent", "ram_used_mb", "ram_total_mb")
    if any(k not in fields for k in required):
        return None
    cpu = fields["cpu_percent"]
    if not (0.0 <= cpu <= 100.0):
        return None
    temp = fields.get("temperature_c")
    if temp is not None and not (-20.0 <= temp <= 150.0):
        temp = None
    return Telemetry(
        cpu_percent=cpu,
        ram_used_mb=max(0.0, fields["ram_used_mb"]),
        ram_total_mb=max(0.0, fields["ram_total_mb"]),
        load_1=max(0.0, fields.get("load_1", 0.0)),
        temperature_c=temp,
        uptime_s=max(0.0, fields.get("uptime_s", 0.0)),
        process_count=int(max(0.0, fields.get("process_count", 0.0))),
    )


def collect_node_telemetry(
    ssh_destination: str, *, timeout_s: float = 4.0
) -> tuple[Optional[Telemetry], list[ProcessRow], str]:
    """Collect one node snapshot via BatchMode SSH + forced command.

    Returns ``(telemetry_or_None, processes, offline_reason)``.
    """
    argv = [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=3",
        "-o",
        "StrictHostKeyChecking=accept-new",
        "-o",
        f"ConnectTimeout={min(int(timeout_s), 5)}",
        ssh_destination,
        TELEMETRY_PROBE,
    ]
    ok, out, reason = _run_bounded(argv, timeout_s, MAX_TELEMETRY_BYTES)
    if not ok:
        return None, [], reason or "unreachable"
    telemetry = parse_telemetry_output(out)
    if telemetry is None:
        return None, [], "malformed telemetry payload"
    processes: list[ProcessRow] = []
    in_processes = False
    for line in out.splitlines():
        stripped = line.strip()
        if stripped == "[processes]":
            in_processes = True
            continue
        if in_processes:
            parts = stripped.split("|")
            if len(parts) >= 2:
                processes.append(ProcessRow.from_raw(parts[0], parts[1]))
            if len(processes) >= 12:
                break
    return telemetry, processes, ""


def read_agent_report(agent_id: str, base_dir: Path = AGENT_STATE_DIR) -> list[str]:
    """Read sanitized report lines from ``.agent-state/<id>/latest.md``.

    Missing files are normal (empty result), never errors.
    """
    safe_id = sanitize.sanitize_id(agent_id).replace("/", "_").replace(".", "_")
    path = base_dir / safe_id / "latest.md"
    try:
        text = path.read_text(encoding="utf-8", errors="replace")[:8192]
    except OSError:
        return []
    return sanitize.sanitize_report_text(text)


def read_agent_todos(
    agent_id: str,
    *,
    stale_after_s: float,
    cache: TodoCache,
    now_s: Optional[float] = None,
    base_dir: Path = AGENT_STATE_DIR,
) -> TodoPanel:
    """Load a node's live checklist, falling back to the durable cache.

    Live parse wins and refreshes the cache. If the file is missing/empty
    (idle agent), the cached checklist survives -- restarts and idle periods
    cannot erase in-progress context.
    """
    safe_id = sanitize.sanitize_id(agent_id).replace("/", "_").replace(".", "_")
    path = base_dir / safe_id / "todos.json"
    raw: object = ""
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")[:16384]
    except OSError:
        raw = ""
    panel = parse_todos(raw, stale_after_s=stale_after_s, now_s=now_s)
    if panel.items:
        cache.store(safe_id, panel)
        # Re-mark staleness against caller's clock semantics already applied.
        return panel
    cached = cache.load(safe_id)
    if cached is not None:
        now = now_s if now_s is not None else time.time()
        stale = bool(cached.updated_at_epoch_s > 0 and (now - cached.updated_at_epoch_s) > stale_after_s)
        return TodoPanel(
            agent_id=cached.agent_id or safe_id,
            updated_at_epoch_s=cached.updated_at_epoch_s,
            stale=stale,
            items=cached.items,
            source="cached",
        )
    from command_center.webui.todos import empty_panel

    return empty_panel(safe_id)


def build_node_state(
    *,
    node_id: str,
    role: str,
    host_alias: str,
    ssh_destination: str,
    agent_id: str,
    timeout_s: float,
    stale_after_s: float,
    todos_cache: TodoCache,
    opencode_state: str = "unknown",
    current_issue: str = "",
    current_pr: str = "",
    status_summary: str = "",
    now_s: Optional[float] = None,
) -> NodeState:
    """Collect everything known about one node; failures degrade to OFFLINE."""
    started = time.time() if now_s is None else now_s
    telemetry, processes, reason = collect_node_telemetry(
        ssh_destination, timeout_s=timeout_s
    )
    report_lines = read_agent_report(agent_id)
    todos = read_agent_todos(
        agent_id, stale_after_s=stale_after_s, cache=todos_cache, now_s=started
    )
    if telemetry is None:
        status = OFFLINE
        last_update = 0.0
    else:
        status = "reachable"
        last_update = started
    return NodeState(
        node_id=node_id,
        role=role,
        host_alias=host_alias,
        status=status,
        offline_reason=sanitize.sanitize_text(reason, 120),
        agent_identity=sanitize.sanitize_text(agent_id, 60),
        opencode_state=sanitize.sanitize_text(opencode_state, 40),
        current_issue=current_issue,
        current_pr=current_pr,
        status_summary=status_summary,
        last_update_epoch_s=last_update,
        telemetry=telemetry or Telemetry(),
        processes=tuple(processes),
        agent_report_lines=tuple(report_lines),
        todos=todos,
    )


def github_queue_items(entries: list[dict]) -> tuple:
    """Normalize raw GitHub issue dicts into sanitized QueueItems.

    Stage/state derivation is intentionally conservative: only well-known
    label prefixes are honored; everything unknown lands at intake/queued.
    """
    from command_center.webui.model import QueueItem
    from command_center.webui.workflow import STAGES

    stage_by_label = {
        "status:in-progress": "development",
        "status:review": "security-review",
        "status:blocked": "intake",
        "status:awaiting-human": "human-approval",
        "status:merged": "merged",
        "status:released": "released",
        "type:security": "security-review",
        "agent:pm": "pm-scope",
    }
    items: list[QueueItem] = []
    for entry in entries[:30]:
        number = entry.get("number")
        title = entry.get("title", "")
        gh_state = entry.get("state", "OPEN")
        labels = [
            str(l.get("name", "")).lower()
            for l in entry.get("labels", [])
            if isinstance(l, dict)
        ]
        stage = "intake"
        for label in labels:
            if label in stage_by_label:
                stage = stage_by_label[label]
                break
        if gh_state == "CLOSED":
            state = "merged" if stage in ("merged", "released") else "deployed"
            stage = stage if stage in ("merged", "released") else "released"
        else:
            state = {
                "intake": "queued",
                "pm-scope": "working",
                "development": "working",
                "security-review": "awaiting-human",
                "human-approval": "awaiting-human",
                "merged": "merged",
                "released": "deployed",
            }.get(stage, "queued")
        badge = ""
        if any("simulation" in l for l in labels):
            badge = "SIMULATION"
        elif any("test" in l for l in labels):
            badge = "TEST"
        items.append(
            QueueItem(
                key=f"issue-{sanitize.sanitize_id(str(number))}",
                kind="issue",
                title=title,
                stage=stage if stage in STAGES else "intake",
                state=state,
                badge=badge,
            )
        )
    return tuple(items)


def collect_github_state(*, timeout_s: float = GITHUB_TIMEOUT_S) -> tuple[bool, bool, list[dict]]:
    """Read-only GitHub snapshot via the gh CLI.

    Returns ``(reachable, stale, queue_items_raw)``. Any failure marks the
    source unreachable and returns the previous-good flag handled by callers;
    here it simply fails closed to empty.
    """
    argv = [
        "gh",
        "issue",
        "list",
        "--repo",
        "Mattjhagen/Projects",
        "--limit",
        "30",
        "--json",
        "number,title,state,labels",
    ]
    ok, out, _reason = _run_bounded(argv, timeout_s, MAX_GH_PAYLOAD_BYTES)
    if not ok:
        return False, True, []
    try:
        doc = json.loads(out)
    except json.JSONDecodeError:
        return False, True, []
    if not isinstance(doc, list):
        return False, True, []
    cleaned: list[dict] = []
    for entry in doc[:30]:
        if isinstance(entry, dict):
            cleaned.append(entry)
    return True, False, cleaned
