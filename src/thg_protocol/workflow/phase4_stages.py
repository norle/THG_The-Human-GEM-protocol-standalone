"""Compatibility facade for Phase 4 workflow adapters."""

from ._phase4 import (
    FinalTHGStage,
    HumanDatabaseStage,
    final_thg_stages,
    human_database_stages,
)

__all__ = [
    "FinalTHGStage", "HumanDatabaseStage", "final_thg_stages", "human_database_stages"
]
