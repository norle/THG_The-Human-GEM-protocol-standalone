"""β1 DAG definition and stage ordering."""

from ..registry import WorkflowDefinition
from ._stages import DETAILED_BETA1_STAGE_IDS, detailed_beta1_stages

BETA1_WORKFLOW = WorkflowDefinition(
    "beta1",
    detailed_beta1_stages(),
    frozenset({"beta1"}),
    "THGβ1 offline curation workflow",
)

__all__ = ["BETA1_WORKFLOW", "DETAILED_BETA1_STAGE_IDS"]
