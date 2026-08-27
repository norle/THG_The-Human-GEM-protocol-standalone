"""Pathway workflow adapter ownership."""

from ._scientific import PathwayStage, pathway_stages
from .registry import WorkflowDefinition

PATHWAY_WORKFLOW = WorkflowDefinition(
    "pathway",
    pathway_stages(),
    frozenset({"pathway"}),
    "First-class pathway model implementation",
)

__all__ = ["PATHWAY_WORKFLOW", "PathwayStage", "pathway_stages"]
