"""β1 DAG definition and stage ordering."""

from ..foundation import fixture_stages
from ..registry import WorkflowDefinition
from ._stages import DETAILED_BETA1_STAGE_IDS, detailed_beta1_stages

BETA1_WORKFLOW = WorkflowDefinition(
    "beta1",
    fixture_stages("beta1"),
    frozenset({"beta1"}),
    "THGβ1 foundation fixture",
    scientific_stages=detailed_beta1_stages(),
)

__all__ = ["BETA1_WORKFLOW", "DETAILED_BETA1_STAGE_IDS"]
