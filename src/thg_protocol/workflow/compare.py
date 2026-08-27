"""Model comparison workflow adapter ownership."""

from ._scientific import CompareStage, compare_stages
from .registry import WorkflowDefinition

COMPARE_WORKFLOW = WorkflowDefinition(
    "compare",
    compare_stages(),
    frozenset({"compare"}),
    "Semantic comparison of two explicit model inputs",
)

__all__ = ["COMPARE_WORKFLOW", "CompareStage", "compare_stages"]
