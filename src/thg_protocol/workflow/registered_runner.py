"""Compatibility facade for the public workflow runner."""

from .runner import WorkflowError, get_status, resume, start

RegisteredWorkflowError = WorkflowError
start_registered = start
resume_registered = resume

__all__ = [
    "RegisteredWorkflowError",
    "start_registered",
    "resume_registered",
    "get_status",
]
