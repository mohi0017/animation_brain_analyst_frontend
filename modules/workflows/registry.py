"""
Workflow registry for milestone-based configuration.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from ..config import DEFAULT_LINE_ART_MODEL, DEFAULT_M3_MODEL


@dataclass(frozen=True)
class WorkflowSpec:
    key: str
    label: str
    api_path: str
    prompt_mode: str  # "single" or "dual"
    requires_reference: bool
    default_model: str
    model_options: List[str]


def get_workflow_specs() -> List[WorkflowSpec]:
    """Return supported milestone workflows in display order."""
    return [
        WorkflowSpec(
            key="M3",
            label="Milestone 3 (M3)",
            api_path="workflows/Animation_Workflow_M3_Api.json",
            prompt_mode="dual",
            requires_reference=True,
            default_model=DEFAULT_M3_MODEL,
            model_options=[DEFAULT_M3_MODEL, DEFAULT_LINE_ART_MODEL],
        ),
    ]


def get_workflow_spec(key: str) -> WorkflowSpec:
    """Lookup a workflow by key."""
    for spec in get_workflow_specs():
        if spec.key == key:
            return spec
    raise KeyError(f"Unknown workflow key: {key}")
