"""Compatibility facade for workflow-specific scientific adapters."""

from ._scientific import (
    CellSpecificStage,
    CompareStage,
    PathwayStage,
    cell_specific_stages,
    compare_stages,
    pathway_stages,
)

__all__ = [
    "CellSpecificStage", "CompareStage", "PathwayStage", "cell_specific_stages",
    "compare_stages", "pathway_stages",
]
