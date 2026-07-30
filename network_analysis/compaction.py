"""Compatibility wrapper for network compaction helpers."""

from thg_protocol.analysis.compaction import (
    are_reactions_proportional,
    combine_identical_reactions,
    full_compaction,
)

__all__ = [
    "are_reactions_proportional",
    "combine_identical_reactions",
    "full_compaction",
]
