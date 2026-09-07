"""Canonical β1 → β2 → gate → reference-gapfill composition."""

from .beta1._stages import detailed_beta1_stages
from .beta2._stages import detailed_beta2_stages
from .gapfill import Beta2GateStage, gapfill_stages
from .human_database import human_database_stages
from .human_database_integration import HumanDatabaseIntegrationStage
from .reference_reporting import ReferenceReportStage
from .registry import WorkflowDefinition

REFERENCE_STAGES = (
    *detailed_beta1_stages(),
    *detailed_beta2_stages(),
    Beta2GateStage(),
    *human_database_stages(),
    HumanDatabaseIntegrationStage("plan-human-database-integration", ("export-beta2", "human-database-reconstruct")),
    HumanDatabaseIntegrationStage("integrate-human-database", ("plan-human-database-integration", "export-beta2", "human-database-reconstruct")),
    *gapfill_stages(reference=True),
    ReferenceReportStage("summarize-reference", ("export-gapfilled-reference",)),
    ReferenceReportStage("export-reference", ("summarize-reference", "export-gapfilled-reference")),
)
REFERENCE_WORKFLOW = WorkflowDefinition(
    "reference",
    REFERENCE_STAGES,
    frozenset({"beta1", "beta2", "human_database", "reference", "gapfill"}),
    "Canonical β1 → β2 → gapfilled reference pipeline",
    version=2,
)

__all__ = ["REFERENCE_STAGES", "REFERENCE_WORKFLOW"]
