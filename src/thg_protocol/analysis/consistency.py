"""Dependency-light consistency checks for model-like objects."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from thg_protocol.model_build.mass_balance import formula_atoms


def reaction_balance(reaction: Any) -> dict[str, float]:
    """Return elemental totals for a COBRA reaction (products minus reactants)."""
    totals: dict[str, float] = defaultdict(float)
    for metabolite, coefficient in reaction.metabolites.items():
        formula = getattr(metabolite, "formula", "") or ""
        for element, count in formula_atoms(formula).items():
            totals[element] += float(coefficient) * count
    return {element: value for element, value in totals.items() if abs(value) > 1e-9}


def unbalanced_reactions(model: Any) -> list[str]:
    """Return IDs of reactions whose available formulas do not balance."""
    return [
        reaction.id
        for reaction in model.reactions
        if reaction_balance(reaction)
    ]


def orphan_metabolites(model: Any) -> list[str]:
    """Return metabolite IDs that participate in no reactions."""
    return [
        metabolite.id
        for metabolite in model.metabolites
        if not metabolite.reactions
    ]


def dead_end_metabolites(model: Any) -> list[str]:
    """Return metabolites used only as reactants or only as products."""
    consumed, produced = set(), set()
    for reaction in model.reactions:
        for metabolite, coefficient in reaction.metabolites.items():
            (consumed if coefficient < 0 else produced).add(metabolite.id)
    return sorted((consumed ^ produced) - set(orphan_metabolites(model)))


__all__ = [
    "dead_end_metabolites",
    "orphan_metabolites",
    "reaction_balance",
    "unbalanced_reactions",
]
