"""Optional network-reaction compaction helpers."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


def are_reactions_proportional(
    reaction1: Any, reaction2: Any, *, tolerance: float = 1e-9
) -> tuple[bool, float, bool]:
    """Compare two reactions by stoichiometry, including reversal."""
    first = {
        getattr(metabolite, "id", metabolite): value
        for metabolite, value in reaction1.metabolites.items()
    }
    second = {
        getattr(metabolite, "id", metabolite): value
        for metabolite, value in reaction2.metabolites.items()
    }
    if set(first) != set(second) or not first:
        return False, 0.0, False
    ratios = []
    for metabolite in first:
        left, right = first[metabolite], second[metabolite]
        if abs(left) <= tolerance:
            if abs(right) > tolerance:
                return False, 0.0, False
            continue
        ratios.append(right / left)
    if not ratios or any(abs(value - ratios[0]) > tolerance for value in ratios[1:]):
        return False, 0.0, False
    return True, ratios[0], ratios[0] < 0


def combine_identical_reactions(
    model: Any, non_comp_id: set[str] | None = None
) -> tuple[Any, list[Any]]:
    """Return a copy with proportional non-boundary reactions combined."""
    result = model.copy()
    excluded = set(non_comp_id or ())
    removed: list[Any] = []
    reactions = list(result.reactions)
    for index, base in enumerate(reactions):
        if base.id in excluded or base.boundary or not result.reactions.has_id(base.id):
            continue
        for candidate in reactions[index + 1 :]:
            if (
                candidate.id in excluded
                or candidate.boundary
                or not result.reactions.has_id(candidate.id)
            ):
                continue
            proportional, factor, _ = are_reactions_proportional(base, candidate)
            if not proportional:
                continue
            if base.gene_reaction_rule and candidate.gene_reaction_rule:
                base.gene_reaction_rule = (
                    f"{base.gene_reaction_rule} or ({candidate.gene_reaction_rule})"
                )
            elif candidate.gene_reaction_rule:
                base.gene_reaction_rule = candidate.gene_reaction_rule
            base.lower_bound = min(base.lower_bound, candidate.lower_bound * factor)
            base.upper_bound = max(base.upper_bound, candidate.upper_bound * factor)
            removed.append(deepcopy(candidate))
            result.remove_reactions([candidate])
    return result, removed


def full_compaction(
    model: Any,
    *,
    non_comp_id: set[str] | None = None,
    no_blocked_reactions: bool = True,
) -> tuple[Any, list[Any]]:
    """Compact proportional reactions, optionally filtering blocked reactions.

    Blocked-reaction filtering is solver-dependent and imported only when
    explicitly requested. The default operation is deterministic and offline.
    """
    result = model.copy()
    if not no_blocked_reactions:
        try:
            from cobra.flux_analysis import find_blocked_reactions

            result.remove_reactions(find_blocked_reactions(result))
        except ImportError as error:  # pragma: no cover - optional COBRA path
            raise RuntimeError("blocked-reaction filtering requires COBRA") from error
    removed: list[Any] = []
    while True:
        result, round_removed = combine_identical_reactions(result, non_comp_id)
        if not round_removed:
            break
        removed.extend(round_removed)
    return result, removed


__all__ = [
    "are_reactions_proportional",
    "combine_identical_reactions",
    "full_compaction",
]
