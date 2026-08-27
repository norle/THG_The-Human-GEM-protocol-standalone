"""Human Database workflow adapter ownership."""

from ._phase4 import HumanDatabaseStage, human_database_stages
from .registry import WorkflowDefinition

HUMAN_DATABASE_WORKFLOW = WorkflowDefinition(
    "human-database",
    human_database_stages(),
    frozenset({"human_database"}),
    "Offline-first Human Database reconstruction",
)

__all__ = ["HUMAN_DATABASE_WORKFLOW", "HumanDatabaseStage", "human_database_stages"]
