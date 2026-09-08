"""β2 DAG definition and stage ordering."""

from ..registry import WorkflowDefinition
from ._stages import DETAILED_BETA2_STAGE_IDS, detailed_beta2_stages

BETA2_WORKFLOW = WorkflowDefinition(
    "beta2",
    detailed_beta2_stages(),
    frozenset({"beta2"}),
    "THGβ2 offline expansion workflow",
)

__all__ = ["BETA2_WORKFLOW", "DETAILED_BETA2_STAGE_IDS"]
