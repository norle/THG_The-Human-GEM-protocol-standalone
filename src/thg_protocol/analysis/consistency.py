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


def charge_balance(reaction: Any) -> dict[str, float]:
    """Return net charge for a reaction using defined metabolite charges."""
    total = 0.0
    missing: list[str] = []
    for metabolite, coefficient in reaction.metabolites.items():
        charge = getattr(metabolite, "charge", None)
        if charge is None:
            missing.append(metabolite.id)
        else:
            total += float(coefficient) * float(charge)
    result = {"charge": total}
    if missing:
        result["missing"] = missing  # type: ignore[assignment]
    return result


def unbalanced_reactions_by_charge(model: Any) -> list[str]:
    """Return internal reactions with a non-zero or undefined net charge."""
    return [
        reaction.id
        for reaction in model.reactions
        if not reaction.boundary
        and (
            abs(charge_balance(reaction)["charge"]) > 1e-9
            or "missing" in charge_balance(reaction)
        )
    ]


def blocked_reactions(model: Any) -> list[str]:
    """Find blocked reactions through COBRA's optional solver interface."""
    try:
        from cobra.flux_analysis import find_blocked_reactions
    except ImportError as error:  # pragma: no cover - optional dependency path
        raise RuntimeError("blocked-reaction checks require COBRA") from error
    return list(find_blocked_reactions(model))


def stoichiometrically_balanced_cycles(model: Any) -> list[str]:
    """Return reactions carrying flux after all boundary reactions are closed."""
    try:
        from cobra.flux_analysis import flux_variability_analysis
    except ImportError as error:  # pragma: no cover - optional dependency path
        raise RuntimeError("cycle checks require COBRA") from error
    closed = model.copy()
    for reaction in closed.boundary:
        reaction.bounds = (0.0, 0.0)
    fva = flux_variability_analysis(closed)
    return [
        reaction_id
        for reaction_id, row in fva.iterrows()
        if abs(float(row["minimum"])) > 1e-9
        or abs(float(row["maximum"])) > 1e-9
    ]


def metabolites_not_produced(model: Any) -> list[str]:
    """Return metabolites consumed by a reaction but never produced."""
    consumed, produced = set(), set()
    for reaction in model.reactions:
        for metabolite, coefficient in reaction.metabolites.items():
            (consumed if coefficient < 0 else produced).add(metabolite.id)
    return sorted(consumed - produced)


def metabolites_not_consumed(model: Any) -> list[str]:
    """Return metabolites produced by a reaction but never consumed."""
    consumed, produced = set(), set()
    for reaction in model.reactions:
        for metabolite, coefficient in reaction.metabolites.items():
            (consumed if coefficient < 0 else produced).add(metabolite.id)
    return sorted(produced - consumed)


def unbounded_reactions(model: Any) -> tuple[list[str], float, Any]:
    """Return reactions at an FVA infinity bound and their fraction."""
    try:
        from cobra.flux_analysis import flux_variability_analysis
    except ImportError as error:  # pragma: no cover - optional dependency path
        raise RuntimeError("FVA checks require COBRA") from error
    result = flux_variability_analysis(model)
    ids = [
        reaction_id
        for reaction_id, row in result.iterrows()
        if abs(float(row["minimum"])) >= 999.0
        or abs(float(row["maximum"])) >= 999.0
    ]
    denominator = max(len(result), 1)
    return ids, len(ids) / denominator, result


__all__ = [
    "dead_end_metabolites",
    "orphan_metabolites",
    "reaction_balance",
    "charge_balance",
    "unbalanced_reactions_by_charge",
    "blocked_reactions",
    "stoichiometrically_balanced_cycles",
    "metabolites_not_produced",
    "metabolites_not_consumed",
    "unbounded_reactions",
    "unbalanced_reactions",
]
