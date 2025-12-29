"""
Compatibility wrapper for legacy imports.
"""

from .workflows.registry import WorkflowSpec, get_workflow_specs, get_workflow_spec

__all__ = ["WorkflowSpec", "get_workflow_specs", "get_workflow_spec"]
