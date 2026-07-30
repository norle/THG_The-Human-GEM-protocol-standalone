"""Exchange-reaction matching for cell-specific model tailoring."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


def _core_id(metabolite: Any) -> str:
    identifier = metabolite.id
    compartment = getattr(metabolite, "compartment", None)
    if compartment and identifier.endswith(f"_{compartment}"):
        return identifier[: -(len(compartment) + 1)]
    if compartment and identifier.endswith(f"[{compartment}]"):
        return identifier[: -(len(compartment) + 2)]
    return identifier


def match_exchange_reactions(
    model_new: Any,
    model_base: Any,
    *,
    add_reactions: bool = False,
) -> tuple[Any, list[tuple[str, str]], list[str], list[str]]:
    """Copy matching boundary bounds from ``model_base`` into a model copy.

    Matching uses compartment-aware metabolite core IDs and never performs
    annotation lookups, solver optimization, or network access. The returned
    model is independent of both inputs. ``add_reactions`` optionally copies
    unmatched base boundary reactions when all referenced metabolites exist.
    """
    result = model_new.copy()
    new_boundaries = [r for r in result.boundary if len(r.metabolites) == 1]
    base_boundaries = [r for r in model_base.boundary if len(r.metabolites) == 1]
    new_by_key = {}
    for reaction in new_boundaries:
        metabolite = next(iter(reaction.metabolites))
        new_by_key[(_core_id(metabolite), metabolite.compartment)] = reaction
    matched: list[tuple[str, str]] = []
    unmatched: list[str] = []
    inconsistent: list[str] = []
    for base_reaction in base_boundaries:
        base_metabolite = next(iter(base_reaction.metabolites))
        key = (_core_id(base_metabolite), base_metabolite.compartment)
        target = new_by_key.get(key)
        if target is None:
            unmatched.append(base_reaction.id)
            continue
        matched.append((target.id, base_reaction.id))
        try:
            target.bounds = deepcopy(base_reaction.bounds)
        except (TypeError, ValueError):
            inconsistent.append(target.id)

    if add_reactions:
        from cobra import Reaction

        for base_reaction in base_boundaries:
            if base_reaction.id in result.reactions:
                continue
            if not all(
                result.metabolites.has_id(met.id) for met in base_reaction.metabolites
            ):
                continue
            reaction = Reaction(
                base_reaction.id,
                name=base_reaction.name,
                lower_bound=base_reaction.lower_bound,
                upper_bound=base_reaction.upper_bound,
            )
            reaction.add_metabolites(
                {
                    result.metabolites.get_by_id(met.id): coefficient
                    for met, coefficient in base_reaction.metabolites.items()
                }
            )
            result.add_reactions([reaction])

    return result, matched, unmatched, inconsistent


__all__ = ["match_exchange_reactions"]
