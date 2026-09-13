"""Live Todos / Build Plan panel state (supervisor requirement on #22).

Agent checklists arrive as durable, machine-readable JSON written by each
agent to ``.agent-state/<agent-id>/todos.json``::

    {
      "schema": "r510-agent-todos/v1",
      "updated_at_epoch_s": 1771700000.0,
      "agent_id": "dev-r510",
      "items": [
        {"label": "Create feature branch", "status": "completed",
         "activity": "branch agent/developer/22-... created"}
      ]
    }

Design rules enforced here:
- Nothing is hard-coded into production UI: an empty/missing file renders an
  explicit "no checklist reported" placeholder.
- The service persists the most recent checklist per node to a host-local
  cache so a process exit/restart cannot erase in-progress context and an
  idle agent cannot blank the panel.
- Every label/activity string passes through :mod:`sanitize`.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from command_center.webui import sanitize
from command_center.webui.sanitize import MAX_REPORT_LINE_LEN

TODO_SCHEMA = "r510-agent-todos/v1"

STATUS_COMPLETED = "completed"
STATUS_ACTIVE = "active"
STATUS_PENDING = "pending"
STATUS_BLOCKED = "blocked"
STATUS_FAILED = "failed"

ITEM_STATUSES: tuple[str, ...] = (
    STATUS_COMPLETED,
    STATUS_ACTIVE,
    STATUS_PENDING,
    STATUS_BLOCKED,
    STATUS_FAILED,
)

GLYPHS: dict[str, str] = {
    STATUS_COMPLETED: "\u2713",  # [✓]
    STATUS_ACTIVE: "\u2022",     # [•]
    STATUS_PENDING: " ",         # [ ]
    STATUS_BLOCKED: "!",         # [!]
    STATUS_FAILED: "\u2717",     # [✗]
}

MAX_TODO_ITEMS = 24


@dataclass(frozen=True)
class TodoItem:
    status: str = STATUS_PENDING
    label: str = ""
    activity: str = ""  # latest short activity; shown under the active step

    def __post_init__(self) -> None:
        if self.status not in ITEM_STATUSES:
            raise ValueError(f"unknown todo status: {self.status!r}")

    @property
    def glyph(self) -> str:
        return GLYPHS[self.status]

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "glyph": self.glyph,
            "label": sanitize.sanitize_text(self.label, MAX_REPORT_LINE_LEN),
            "activity": sanitize.sanitize_text(self.activity, MAX_REPORT_LINE_LEN),
        }


@dataclass(frozen=True)
class TodoPanel:
    """A parsed checklist plus freshness metadata."""

    agent_id: str
    updated_at_epoch_s: float = 0.0
    stale: bool = True
    items: tuple[TodoItem, ...] = ()
    source: str = "live"  # live | cached | none

    def to_dict(self) -> dict:
        return {
            "agent_id": sanitize.sanitize_id(self.agent_id),
            "updated_at_epoch_s": float(self.updated_at_epoch_s),
            "stale": bool(self.stale),
            "source": self.source if self.source in ("live", "cached", "none") else "none",
            "items": [i.to_dict() for i in self.items],
        }


def parse_todos(raw_text: object, *, stale_after_s: float, now_s: Optional[float] = None) -> TodoPanel:
    """Parse machine-readable todo JSON into a sanitized :class:`TodoPanel`.

    Malformed input never raises: it yields an empty non-stale-source panel
    marked appropriately. Unknown statuses coerce to ``pending``.
    """
    if not isinstance(raw_text, str) or not raw_text.strip():
        return TodoPanel(agent_id="", source="none")
    try:
        doc = json.loads(raw_text)
    except json.JSONDecodeError:
        return TodoPanel(agent_id="", source="none")
    if not isinstance(doc, dict):
        return TodoPanel(agent_id="", source="none")

    agent_id = sanitize.sanitize_id(doc.get("agent_id", ""))
    try:
        updated = float(doc.get("updated_at_epoch_s", 0.0))
    except (TypeError, ValueError):
        updated = 0.0
    now = now_s if now_s is not None else time.time()
    stale = bool(updated > 0 and (now - updated) > stale_after_s)

    items_raw = doc.get("items")
    items: list[TodoItem] = []
    if isinstance(items_raw, list):
        for entry in items_raw[:MAX_TODO_ITEMS]:
            if not isinstance(entry, dict):
                continue
            status = entry.get("status", STATUS_PENDING)
            if status not in ITEM_STATUSES:
                status = STATUS_PENDING
            items.append(
                TodoItem(
                    status=status,
                    label=sanitize.sanitize_text(entry.get("label", ""), MAX_REPORT_LINE_LEN),
                    activity=sanitize.sanitize_text(
                        entry.get("activity", ""), MAX_REPORT_LINE_LEN
                    ),
                )
            )
    return TodoPanel(
        agent_id=agent_id,
        updated_at_epoch_s=max(0.0, updated),
        stale=stale,
        items=tuple(items),
        source="live" if items else "none",
    )


def empty_panel(agent_id: str) -> TodoPanel:
    """Explicit empty state -- used instead of fabricating fake progress."""
    return TodoPanel(agent_id=sanitize.sanitize_id(agent_id), source="none")


class TodoCache:
    """Durable host-local cache of the latest checklist per node.

    Written whenever a live parse succeeds; read at startup so a restarted
    dashboard still shows the last known build plan (marked ``cached`` and
    stale per timestamps). Idle agents cannot erase in-progress context.
    """

    def __init__(self, cache_dir: Path) -> None:
        self.cache_dir = cache_dir
        self._memory: dict[str, TodoPanel] = {}

    def _path_for(self, node_id: str) -> Path:
        safe = sanitize.sanitize_id(node_id).replace("/", "_") or "node"
        return self.cache_dir / f"todos-{safe}.json"

    def load(self, node_id: str) -> Optional[TodoPanel]:
        if node_id in self._memory:
            return self._memory[node_id]
        path = self._path_for(node_id)
        if not path.exists():
            return None
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError:
            return None
        panel = parse_todos(raw, stale_after_s=1e18)  # staleness judged later
        panel_source = "cached" if panel.items else "none"
        cached = TodoPanel(
            agent_id=panel.agent_id,
            updated_at_epoch_s=panel.updated_at_epoch_s,
            stale=panel.stale,
            items=panel.items,
            source=panel_source,
        )
        self._memory[node_id] = cached
        return cached if cached.items else None

    def store(self, node_id: str, panel: TodoPanel) -> None:
        if not panel.items:
            # Never overwrite a real checklist with emptiness.
            return
        self._memory[node_id] = TodoPanel(
            agent_id=panel.agent_id,
            updated_at_epoch_s=panel.updated_at_epoch_s,
            stale=panel.stale,
            items=panel.items,
            source="cached",
        )
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            payload = {
                "schema": TODO_SCHEMA,
                "agent_id": panel.agent_id,
                "updated_at_epoch_s": panel.updated_at_epoch_s,
                "items": [
                    {"status": i.status, "label": i.label, "activity": i.activity}
                    for i in panel.items
                ],
            }
            tmp = self._path_for(node_id).with_suffix(".tmp")
            tmp.write_text(json.dumps(payload), encoding="utf-8")
            tmp.replace(self._path_for(node_id))
        except OSError:
            # Cache write failure is nonfatal; memory copy still serves.
            pass
