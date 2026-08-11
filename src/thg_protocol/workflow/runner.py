"""Public entry points for registered workflows."""

from collections.abc import Mapping
from pathlib import Path

from .manifest import load_workflow_manifest
from .registered_runner import (
    RegisteredWorkflowError,
    resume_registered,
    start_registered,
)

WorkflowError = RegisteredWorkflowError
start = start_registered
resume = resume_registered


def get_status(run_dir: str | Path) -> Mapping[str, object]:
    return load_workflow_manifest(run_dir)


__all__ = ["WorkflowError", "start", "resume", "get_status"]
