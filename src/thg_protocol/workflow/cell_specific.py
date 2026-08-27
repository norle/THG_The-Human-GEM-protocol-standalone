"""Cell-specific workflow adapter ownership."""

from ._scientific import CellSpecificStage, cell_specific_stages
from .registry import WorkflowDefinition

CELL_SPECIFIC_WORKFLOW = WorkflowDefinition(
    "cell-specific",
    cell_specific_stages(),
    frozenset({"cell_specific"}),
    "Context-specific model reduction from normalized expression evidence",
)

__all__ = ["CELL_SPECIFIC_WORKFLOW", "CellSpecificStage", "cell_specific_stages"]
