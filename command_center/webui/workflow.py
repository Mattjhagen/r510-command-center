"""Workflow stage model for the three-agent pipeline.

Canonical handoff order (binding per issue #22):

    intake -> pm-scope -> development -> security-review
           -> human-approval -> merged -> released

Distinct item states (also binding): queued, working, blocked,
awaiting-human, merged, deployed. A stage describes *where* an item sits in
the pipeline; a state describes *how* it is progressing there.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

STAGES: tuple[str, ...] = (
    "intake",
    "pm-scope",
    "development",
    "security-review",
    "human-approval",
    "merged",
    "released",
)

ITEM_STATES: tuple[str, ...] = (
    "queued",
    "working",
    "blocked",
    "awaiting-human",
    "merged",
    "deployed",
)


class WorkflowError(ValueError):
    """Raised for invalid stages or transitions."""


def validate_stage(stage: str) -> str:
    if stage not in STAGES:
        raise WorkflowError(f"unknown workflow stage: {stage!r}")
    return stage


def validate_state(state: str) -> str:
    if state not in ITEM_STATES:
        raise WorkflowError(f"unknown item state: {state!r}")
    return state


def next_stage(stage: str) -> Optional[str]:
    """Return the next canonical stage, or None past ``released``."""
    validate_stage(stage)
    index = STAGES.index(stage)
    if index + 1 < len(STAGES):
        return STAGES[index + 1]
    return None


def is_forward(current: str, proposed: str) -> bool:
    """True if ``proposed`` is exactly one canonical step after ``current``
    or the same stage (state-only change). Backwards jumps are allowed only
    to ``intake`` (rejection/rework), which the UI renders distinctly."""
    validate_stage(current)
    validate_stage(proposed)
    if proposed == current:
        return True
    if proposed == "intake":
        return True  # rework / rejection restarts the flow
    return next_stage(current) == proposed


@dataclass(frozen=True)
class Handoff:
    """A recorded movement between two stages."""

    from_stage: str
    to_stage: str
    timestamp: str  # ISO-8601 UTC, already sanitized upstream
    evidence_url: str = ""  # sanitized URL or empty

    def to_dict(self) -> dict:
        return {
            "from_stage": self.from_stage,
            "to_stage": self.to_stage,
            "timestamp": self.timestamp,
            "evidence_url": self.evidence_url,
        }

    @classmethod
    def from_dict(cls, raw: dict) -> "Handoff":
        from command_center.webui.sanitize import sanitize_id, sanitize_text

        known_stages = set(STAGES)
        from_stage = sanitize_id(raw.get("from_stage", ""))
        to_stage = sanitize_id(raw.get("to_stage", ""))
        # Unrecognized stage labels are coerced to intake rather than trusted.
        if from_stage not in known_stages:
            from_stage = "intake"
        if to_stage not in known_stages:
            to_stage = "intake"
        return cls(
            from_stage=from_stage,
            to_stage=to_stage,
            timestamp=sanitize_text(raw.get("timestamp", ""), 40),
            evidence_url=sanitize_text(raw.get("evidence_url", ""), MAX_URL),
        )


MAX_URL = 300
