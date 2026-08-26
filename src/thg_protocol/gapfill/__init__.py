"""Gapfill workflow APIs.

The package API works with JSON-serializable model mappings and writes only to
paths explicitly supplied by callers.  The legacy COBRA workflow remains
available as a compatibility script while it is migrated incrementally.
"""

from .core import (
    DeterministicGapfillStrategy,
    GapfillCandidate,
    GapfillResult,
    GapfillStrategy,
    apply_gapfill_plan,
    gapfill_model,
    generate_candidates,
    generate_gapfill_plan,
    run_gapfill,
    run_phase1,
    run_phase2,
    run_phase3,
    run_pipeline,
    validate_gapfill_plan,
)

__all__ = [
    "generate_candidates",
    "gapfill_model",
    "run_phase1",
    "run_phase2",
    "run_phase3",
    "run_pipeline",
    "GapfillCandidate",
    "GapfillResult",
    "GapfillStrategy",
    "DeterministicGapfillStrategy",
    "run_gapfill",
    "generate_gapfill_plan",
    "validate_gapfill_plan",
    "apply_gapfill_plan",
]
