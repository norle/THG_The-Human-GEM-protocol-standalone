"""Canonical β1 → β2 → gate → reference-gapfill composition."""

from .beta1._stages import detailed_beta1_stages
from .beta2._stages import detailed_beta2_stages
from .gapfill import Beta2GateStage, gapfill_stages
from .registry import WorkflowDefinition

REFERENCE_STAGES = (
    *detailed_beta1_stages(),
    *detailed_beta2_stages(),
    Beta2GateStage(),
    *gapfill_stages(reference=True),
)
REFERENCE_WORKFLOW = WorkflowDefinition(
    "reference",
    REFERENCE_STAGES,
    frozenset({"beta1", "beta2", "gapfill"}),
    "Canonical β1 → β2 → gapfilled reference pipeline",
)

__all__ = ["REFERENCE_STAGES", "REFERENCE_WORKFLOW"]
