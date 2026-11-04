"""Dependency-light consistency checks for model-like objects."""

from __future__ import annotations

import math
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


def _has_complete_formulas(reaction: Any) -> bool:
    return all(
        formula_atoms(getattr(metabolite, "formula", "") or "")
        for metabolite in reaction.metabolites
    )


def unassessable_reactions(model: Any) -> list[str]:
    """Return internal reactions with a metabolite lacking a parsable formula.

    Their elemental balance cannot be judged, so ``unbalanced_reactions``
    neither reports nor clears them.
    """
    return sorted(
        reaction.id
        for reaction in model.reactions
        if not reaction.boundary and not _has_complete_formulas(reaction)
    )


def unbalanced_reactions(model: Any) -> list[str]:
    """Return IDs of internal reactions whose formulas do not balance.

    Boundary reactions (exchange, demand, sink) add or remove mass by
    definition and are skipped, as are reactions with a metabolite whose
    formula is missing or unparsable (see ``unassessable_reactions``).
    """
    return sorted(
        reaction.id
        for reaction in model.reactions
        if not reaction.boundary
        and _has_complete_formulas(reaction)
        and reaction_balance(reaction)
    )


def orphan_metabolites(model: Any) -> list[str]:
    """Return metabolite IDs that participate in no reactions."""
    return [
        metabolite.id for metabolite in model.metabolites if not metabolite.reactions
    ]


def _directional_roles(model: Any) -> tuple[set[str], set[str]]:
    """Metabolites some reaction can make, and metabolites some can use.

    A reaction makes its products when it can run forward (upper bound > 0)
    and its reactants when it can run backward (lower bound < 0); using is
    the converse. Reactions with both bounds at zero do neither.
    """
    produced: set[str] = set()
    consumed: set[str] = set()
    for reaction in model.reactions:
        forward = reaction.upper_bound > 0
        backward = reaction.lower_bound < 0
        for metabolite, coefficient in reaction.metabolites.items():
            if (coefficient > 0 and forward) or (coefficient < 0 and backward):
                produced.add(metabolite.id)
            if (coefficient < 0 and forward) or (coefficient > 0 and backward):
                consumed.add(metabolite.id)
    return produced, consumed


def dead_end_metabolites(model: Any) -> list[str]:
    """Return metabolites that bounds allow to be only made or only used.

    Reversible reactions both make and use their metabolites, so a
    metabolite on a reversible path is not a dead end.
    """
    produced, consumed = _directional_roles(model)
    return sorted(produced ^ consumed)


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
    unbalanced: list[str] = []
    for reaction in model.reactions:
        if reaction.boundary:
            continue
        balance = charge_balance(reaction)
        if abs(balance["charge"]) > 1e-9 or "missing" in balance:
            unbalanced.append(reaction.id)
    return sorted(unbalanced)


def blocked_reactions(model: Any) -> list[str]:
    """Find blocked reactions through COBRA's optional solver interface."""
    try:
        from cobra.flux_analysis import find_blocked_reactions
    except ImportError as error:  # pragma: no cover - optional dependency path
        raise RuntimeError("blocked-reaction checks require COBRA") from error
    return list(find_blocked_reactions(model))


def _close_boundaries_keeping_direction(model: Any) -> None:
    """Close boundary reactions and cap internal fluxes at one unit.

    Internal bounds keep their direction (forward, backward or both) but lose
    any forced flux, so a fixed-flux reaction such as ATP maintenance cannot
    make the closed model infeasible.
    """
    for reaction in model.reactions:
        lower, upper = reaction.lower_bound, reaction.upper_bound
        reaction.bounds = (-1.0 if lower < 0 else 0.0, 1.0 if upper > 0 else 0.0)
    for reaction in model.boundary:
        reaction.bounds = (0.0, 0.0)


def stoichiometrically_balanced_cycles(model: Any) -> list[str]:
    """Return reactions that carry flux with every boundary closed.

    Run on a copy: boundaries are closed, internal reactions keep their
    direction but lose forced flux, and the objective is not enforced. Any
    remaining flux is a mass-conserving cycle.
    """
    try:
        from cobra.flux_analysis import flux_variability_analysis
    except ImportError as error:  # pragma: no cover - optional dependency path
        raise RuntimeError("cycle checks require COBRA") from error
    closed = model.copy()
    _close_boundaries_keeping_direction(closed)
    closed.objective = closed.problem.Objective(0, direction="max")
    fva = flux_variability_analysis(closed, fraction_of_optimum=0.0)
    tolerance = max(1e-9, float(closed.tolerance))
    return [
        reaction_id
        for reaction_id, row in fva.iterrows()
        if abs(float(row["minimum"])) > tolerance
        or abs(float(row["maximum"])) > tolerance
    ]


def metabolites_not_produced(model: Any) -> list[str]:
    """Return metabolites some reaction can use but none can make."""
    produced, consumed = _directional_roles(model)
    return sorted(consumed - produced)


def metabolites_not_consumed(model: Any) -> list[str]:
    """Return metabolites some reaction can make but none can use."""
    produced, consumed = _directional_roles(model)
    return sorted(produced - consumed)


def unbounded_reactions(model: Any) -> tuple[list[str], float, Any]:
    """Return reactions with solver-proven unbounded feasible flux and their FVA.

    Each direction is optimized over the model's feasible region, without
    constraining its original objective. Finite flux caps are never infinity.
    """
    try:
        import pandas as pd
        from cobra.util.solver import check_solver_status
    except ImportError as error:  # pragma: no cover - optional dependency path
        raise RuntimeError("FVA checks require COBRA") from error
    result = pd.DataFrame(
        index=[reaction.id for reaction in model.reactions],
        columns=["minimum", "maximum"],
        dtype=float,
    )
    with model:
        for reaction in model.reactions:
            model.objective = reaction
            for direction, column, infinity in (
                ("min", "minimum", -math.inf),
                ("max", "maximum", math.inf),
            ):
                model.objective_direction = direction
                value = model.slim_optimize()
                if model.solver.status == "unbounded":
                    value = infinity
                else:
                    check_solver_status(model.solver.status, raise_error=True)
                result.loc[reaction.id, column] = value
    ids = [
        reaction_id
        for reaction_id, row in result.iterrows()
        if math.isinf(float(row["minimum"])) or math.isinf(float(row["maximum"]))
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
    "unassessable_reactions",
]
