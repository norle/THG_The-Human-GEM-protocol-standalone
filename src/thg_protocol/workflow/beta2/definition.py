"""β2 DAG definition and stage ordering."""

from ..registry import WorkflowDefinition
from ._stages import BETA2_STAGE_IDS, beta2_stages

BETA2_WORKFLOW = WorkflowDefinition(
    "beta2",
    beta2_stages(),
    frozenset({"beta2"}),
    "THGβ2 offline expansion workflow",
)

__all__ = ["BETA2_WORKFLOW", "BETA2_STAGE_IDS"]
