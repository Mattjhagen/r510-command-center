"""Sanitized synthetic fixtures: all three roles, every workflow state.

No real hostnames, addresses, keys, tokens, or secrets appear here -- node
names are role aliases, telemetry values are plausible-but-fake, process
tables carry basenames only. The demo dataset also includes per-agent
Todos / Build Plan checklists in the machine-readable format produced by
``todos.parse_todos`` so visual verification exercises the same code path
as production.
"""
from __future__ import annotations

import json
import time

from command_center.webui.model import (
    DashboardState,
    NodeState,
    ProcessRow,
    QueueItem,
    Telemetry,
    WorkflowSnapshot,
)
from command_center.webui.todos import TodoPanel, TodoItem
from command_center.webui.workflow import Handoff

DEMO_NOW = 1771700000.0  # fixed epoch for reproducible screenshots/tests


def _node_t310() -> NodeState:
    return NodeState(
        node_id="t310-pm",
        role="PM",
        host_alias="t310",
        status="reachable",
        agent_identity="pm-t310",
        opencode_state="scoping",
        current_issue="#22 [Dev] Build T310 three-node command center",
        current_pr="",
        status_summary="Scope locked to graphical kiosk override; queue ordered after #18.",
        last_update_epoch_s=DEMO_NOW,
        telemetry=Telemetry(
            cpu_percent=12.5,
            ram_used_mb=6144.0,
            ram_total_mb=16384.0,
            load_1=0.42,
            temperature_c=52.0,
            uptime_s=86_400 * 3 + 4211,
            process_count=214,
        ),
        processes=(
            ProcessRow(pid=1042, name="opencode"),
            ProcessRow(pid=1188, name="chromium"),
            ProcessRow(pid=907, name="tmux"),
        ),
        agent_report_lines=(
            "Scoping complete for graphical override.",
            "Curses path preserved as optional compatibility mode.",
        ),
        todos=TodoPanel(
            agent_id="pm-t310",
            updated_at_epoch_s=DEMO_NOW - 60.0,
            stale=False,
            items=(
                TodoItem("completed", "Confirm binding Chromium-kiosk override", ""),
                TodoItem("completed", "Order #22 after #18 in queue", ""),
                TodoItem(
                    "active",
                    "Watch dev build plan for security handoff",
                    "Reading PR checklist updates",
                ),
                TodoItem("pending", "Route merged dashboard to human approval", ""),
            ),
            source="live",
        ),
    )


def _node_r510() -> NodeState:
    return NodeState(
        node_id="r510-dev",
        role="Developer",
        host_alias="r510",
        status="reachable",
        agent_identity="dev-r510",
        opencode_state="working",
        current_issue="#22 [Dev] Build T310 three-node command center",
        current_pr="#31 feat(web): graphical three-node mission control",
        status_summary="Implementing webui package; tests green; screenshots pending.",
        last_update_epoch_s=DEMO_NOW - 15.0,
        telemetry=Telemetry(
            cpu_percent=63.8,
            ram_used_mb=21_300.0,
            ram_total_mb=32_768.0,
            load_1=1.84,
            temperature_c=61.5,
            uptime_s=86_400 * 11 + 7200,
            process_count=389,
        ),
        processes=(
            ProcessRow(pid=2211, name="python3"),
            ProcessRow(pid=2212, name="ollama"),
            ProcessRow(pid=2301, name="opencode"),
            ProcessRow(pid=2450, name="sshd"),
        ),
        agent_report_lines=(
            "webui backend modules committed.",
            "Sanitizer blocks ANSI/C0 injection; caps verified by tests.",
            "Next: headless Chromium screenshots at 1920x1080 and 1280x800.",
        ),
        todos=TodoPanel(
            agent_id="dev-r510",
            updated_at_epoch_s=DEMO_NOW - 20.0,
            stale=False,
            items=(
                TodoItem("completed", "Create feature branch from clean main", ""),
                TodoItem(
                    "active",
                    "Backend: sanitize, model, workflow, config, collectors, service",
                    "Writing command_center/webui/service.py",
                ),
                TodoItem("pending", "Frontend: index.html, styles.css, app.js, demo-data.js", ""),
                TodoItem("pending", "Tests: sanitization, workflow, config perms, collectors", ""),
                TodoItem("pending", "Visual verification screenshots (kiosk + desktop)", ""),
                TodoItem("pending", "Kiosk install/rollback/recovery documentation", ""),
                TodoItem("blocked", "Human install step", "Awaiting R410 approval; agents never deploy"),
            ),
            source="live",
        ),
    )


def _node_r410() -> NodeState:
    return NodeState(
        node_id="r410-sec",
        role="Security/QA",
        host_alias="r410",
        status="stale",
        offline_reason="last snapshot 6m old",
        agent_identity="sec-r410",
        opencode_state="reviewing",
        current_issue="(security child pending PR)",
        current_pr="",
        status_summary="Pre-review: awaiting developer PR link before XSS/SSE/SSH pass.",
        last_update_epoch_s=DEMO_NOW - 360.0,
        telemetry=Telemetry(
            cpu_percent=8.1,
            ram_used_mb=2048.0,
            ram_total_mb=8192.0,
            load_1=0.11,
            temperature_c=None,
            uptime_s=86_400 * 30 + 900,
            process_count=142,
        ),
        processes=(
            ProcessRow(pid=771, name="opencode"),
            ProcessRow(pid=802, name="gh"),
        ),
        agent_report_lines=("Review checklist staged: XSS, SSE, loopback bind, SSH probe.",),
        todos=TodoPanel(
            agent_id="sec-r410",
            updated_at_epoch_s=DEMO_NOW - 420.0,
            stale=True,
            items=(
                TodoItem("completed", "Define R410 review checklist", ""),
                TodoItem("pending", "Review sanitization and CSP enforcement", ""),
                TodoItem("pending", "Verify localhost-only bind and no public listener", ""),
                TodoItem("pending", "Physical-console recovery walkthrough sign-off", ""),
            ),
            source="live",
        ),
    )


def _offline_node() -> NodeState:
    return NodeState(
        node_id="aux-lab",
        role="Spare",
        host_alias="lab-aux",
        status="offline",
        offline_reason="timeout after 4s",
        agent_identity="",
        status_summary="No response; UI stays responsive.",
        last_update_epoch_s=0.0,
    )


def demo_dashboard() -> DashboardState:
    """Full demo state: three primary nodes plus an offline spare."""
    handoffs = (
        Handoff("intake", "pm-scope", "2026-08-21T18:02Z", "issue #22 claim comment"),
        Handoff("pm-scope", "development", "2026-08-21T19:40Z", "scope section in #22"),
        Handoff(
            "development",
            "security-review",
            "2026-08-21T21:15Z",
            "PR open; security child created",
        ),
    )
    workflow = WorkflowSnapshot(
        current_stage="development",
        item_label="Website order: three-node command center (#22)",
        state="working",
        handoffs=handoffs,
    )
    queue = (
        QueueItem(
            key="issue-18",
            kind="issue",
            title="Phase A active work",
            stage="development",
            state="working",
            badge="TEST",
        ),
        QueueItem(
            key="issue-22",
            kind="issue",
            title="[Dev] Build T310 three-node command center",
            stage="development",
            state="working",
        ),
        QueueItem(
            key="pr-31",
            kind="pr",
            title="feat(web): graphical three-node mission control",
            stage="security-review",
            state="awaiting-human",
            checks_summary="tests 41/41 · lint clean",
            security_verdict="pending review @ commit abc1234",
            badge="SIMULATION",
        ),
        QueueItem(
            key="issue-21",
            kind="issue",
            title="Synthetic delivery run",
            stage="intake",
            state="queued",
            badge="SIMULATION",
        ),
        QueueItem(
            key="issue-12",
            kind="issue",
            title="Earlier blocked intake item",
            stage="intake",
            state="blocked",
        ),
        QueueItem(
            key="pr-9",
            kind="pr",
            title="Prior merged hardening work",
            stage="merged",
            state="deployed",
            checks_summary="all checks passed",
            security_verdict="approved @ commit def5678",
        ),
    )
    nodes = (_node_t310(), _node_r510(), _node_r410(), _offline_node())
    return DashboardState(
        generated_at_epoch_s=time.time(),
        demo_mode=True,
        github_reachable=True,
        github_stale=False,
        nodes=nodes,
        workflow=workflow,
        queue=queue,
    )


def demo_state_json() -> str:
    """Serialize the demo state exactly as /api/state would."""
    return json.dumps(demo_dashboard().to_dict())
