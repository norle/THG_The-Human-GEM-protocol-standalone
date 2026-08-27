"""β2 DAG definition and stage ordering."""

from ..foundation import fixture_stages
from ..registry import WorkflowDefinition
from ._stages import DETAILED_BETA2_STAGE_IDS, detailed_beta2_stages

BETA2_WORKFLOW = WorkflowDefinition(
    "beta2",
    fixture_stages("beta2"),
    frozenset({"beta2"}),
    "THGβ2 foundation fixture",
    scientific_stages=detailed_beta2_stages(),
)

__all__ = ["BETA2_WORKFLOW", "DETAILED_BETA2_STAGE_IDS"]
