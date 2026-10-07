"""β1 DAG definition and stage ordering."""

from ..registry import WorkflowDefinition
from ._stages import BETA1_STAGE_IDS, beta1_stages

BETA1_WORKFLOW = WorkflowDefinition(
    "beta1",
    beta1_stages(),
    frozenset({"beta1"}),
    "THGβ1 offline curation workflow",
)

__all__ = ["BETA1_WORKFLOW", "BETA1_STAGE_IDS"]
