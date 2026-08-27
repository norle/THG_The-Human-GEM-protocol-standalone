"""Final THG workflow adapter ownership."""

from ._phase4 import FinalTHGStage, final_thg_stages
from .registry import WorkflowDefinition

FINAL_THG_WORKFLOW = WorkflowDefinition(
    "final-thg",
    final_thg_stages(),
    frozenset({"final_thg"}),
    "Semantic β2 and Human Database merge",
)

__all__ = ["FINAL_THG_WORKFLOW", "FinalTHGStage", "final_thg_stages"]
