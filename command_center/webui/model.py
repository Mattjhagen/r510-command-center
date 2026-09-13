"""Strict normalized state model for the web dashboard.

The service never forwards raw collector output. Every field passes through
``sanitize`` and lands in one of the dataclasses below; ``DashboardState.to_
dict`` is the only JSON shape the frontend may consume. Unknown upstream
fields are dropped, not propagated.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from command_center.webui import sanitize
from command_center.webui.todos import TodoPanel
from command_center.webui.workflow import Handoff, STAGES, validate_state

REACHABLE = "reachable"
OFFLINE = "offline"
STALE = "stale"

NODE_STATUSES = (REACHABLE, OFFLINE, STALE)


@dataclass(frozen=True)
class Telemetry:
    """Least-privilege node telemetry snapshot."""

    cpu_percent: float = 0.0
    ram_used_mb: float = 0.0
    ram_total_mb: float = 0.0
    load_1: float = 0.0
    temperature_c: Optional[float] = None
    uptime_s: float = 0.0
    process_count: int = 0

    def to_dict(self) -> dict:
        return {
            "cpu_percent": round(self.cpu_percent, 1),
            "ram_used_mb": round(self.ram_used_mb, 1),
            "ram_total_mb": round(self.ram_total_mb, 1),
            "load_1": round(self.load_1, 2),
            "temperature_c": (
                None if self.temperature_c is None else round(self.temperature_c, 1)
            ),
            "uptime_s": round(self.uptime_s, 0),
            "process_count": self.process_count,
        }


@dataclass(frozen=True)
class ProcessRow:
    pid: int = 0
    name: str = ""  # basename only, sanitized

    def to_dict(self) -> dict:
        return {"pid": max(0, int(self.pid)), "name": sanitize.basename_only(self.name)}

    @classmethod
    def from_raw(cls, pid: object, command: object) -> "ProcessRow":
        try:
            pid_val = abs(int(pid))  # negative PIDs are garbage; clamp
        except (TypeError, ValueError):
            pid_val = 0
        return cls(pid=pid_val, name=sanitize.basename_only(command))


@dataclass(frozen=True)
class NodeState:
    node_id: str
    role: str
    host_alias: str  # display alias only -- never a raw address
    status: str = OFFLINE
    offline_reason: str = ""
    agent_identity: str = ""
    opencode_state: str = "unknown"
    current_issue: str = ""
    current_pr: str = ""
    status_summary: str = ""
    last_update_epoch_s: float = 0.0
    telemetry: Telemetry = field(default_factory=Telemetry)
    processes: tuple[ProcessRow, ...] = ()
    agent_report_lines: tuple[str, ...] = ()
    todos: TodoPanel = field(default_factory=lambda: TodoPanel(agent_id="", source="none"))

    def to_dict(self) -> dict:
        return {
            "node_id": sanitize.sanitize_id(self.node_id),
            "role": sanitize.sanitize_text(self.role, 60),
            "host_alias": sanitize.sanitize_text(self.host_alias, 60),
            "status": self.status if self.status in NODE_STATUSES else STALE,
            "offline_reason": sanitize.sanitize_text(self.offline_reason, 120),
            "agent_identity": sanitize.sanitize_text(self.agent_identity, 60),
            "opencode_state": sanitize.sanitize_text(self.opencode_state, 40),
            "current_issue": sanitize.sanitize_text(self.current_issue, sanitize.MAX_TITLE_LEN),
            "current_pr": sanitize.sanitize_text(self.current_pr, sanitize.MAX_TITLE_LEN),
            "status_summary": sanitize.sanitize_text(
                self.status_summary, sanitize.MAX_SUMMARY_LEN
            ),
            "last_update_epoch_s": float(self.last_update_epoch_s),
            "telemetry": self.telemetry.to_dict(),
            "processes": [p.to_dict() for p in self.processes],
            "agent_report_lines": list(self.agent_report_lines),
            "todos": self.todos.to_dict(),
        }


@dataclass(frozen=True)
class QueueItem:
    key: str  # e.g. "issue-22" / "pr-14"
    kind: str  # "issue" | "pr"
    title: str
    stage: str  # canonical workflow stage
    state: str  # queued/working/blocked/awaiting-human/merged/deployed
    checks_summary: str = ""
    security_verdict: str = ""  # bound to reviewed commit when present
    badge: str = ""  # e.g. "TEST", "SIMULATION"
    evidence_url: str = ""

    def __post_init__(self) -> None:
        validate_state(self.state)

    def to_dict(self) -> dict:
        return {
            "key": sanitize.sanitize_id(self.key),
            "kind": self.kind if self.kind in ("issue", "pr") else "issue",
            "title": sanitize.sanitize_text(self.title, sanitize.MAX_TITLE_LEN),
            # Unknown stage labels coerce to intake rather than crashing.
            "stage": self.stage if self.stage in STAGES else "intake",
            "state": validate_state(self.state),
            "checks_summary": sanitize.sanitize_text(self.checks_summary, 120),
            "security_verdict": sanitize.sanitize_text(self.security_verdict, 120),
            "badge": sanitize.sanitize_text(self.badge, 20),
            "evidence_url": sanitize.sanitize_text(
                self.evidence_url, 300
            ),
        }


@dataclass(frozen=True)
class WorkflowSnapshot:
    current_stage: str = "intake"
    item_label: str = ""
    state: str = "queued"
    handoffs: tuple[Handoff, ...] = ()

    def to_dict(self) -> dict:
        return {
            "current_stage": (
                self.current_stage if self.current_stage in STAGES else "intake"
            ),
            "item_label": sanitize.sanitize_text(self.item_label, sanitize.MAX_TITLE_LEN),
            "state": validate_state(self.state),
            "handoffs": [h.to_dict() for h in self.handoffs],
        }


@dataclass(frozen=True)
class DashboardState:
    generated_at_epoch_s: float
    demo_mode: bool
    github_reachable: bool
    github_stale: bool
    nodes: tuple[NodeState, ...]
    workflow: WorkflowSnapshot
    queue: tuple[QueueItem, ...]

    def to_dict(self) -> dict:
        return {
            "schema": "r510-dashboard-state/v1",
            "generated_at_epoch_s": float(self.generated_at_epoch_s),
            "demo_mode": bool(self.demo_mode),
            "github_reachable": bool(self.github_reachable),
            "github_stale": bool(self.github_stale),
            "nodes": [n.to_dict() for n in self.nodes],
            "workflow": self.workflow.to_dict(),
            "queue": [q.to_dict() for q in self.queue],
        }
