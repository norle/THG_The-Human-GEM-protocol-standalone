"""Metabolite leaks and energy-generating cycles under closed boundaries.

Both checks close every boundary reaction and bound internal reactions to
``[-1, 1]`` or ``[0, 1]`` by reversibility (MEMOTE's
``close_boundaries_sensibly``), so fixed bounds cannot make the problem
infeasible. Unlike the stoichiometric-consistency check they respect reaction
directions: a metabolite is reported only if flux can actually make or
destroy it, and an energy metabolite only if flux can actually charge it.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from optlang.symbolics import Zero

#: Drain cap per metabolite; internal reactions are bounded to 1.
LEAK_FLUX = 1e-3
#: Extra metabolites in MEMOTE's dissipation reactions, by charged metabolite
#: (``memote.support.consistency.detect_energy_generating_cycles``).
_NUCLEOTIDE = {"MNXM2": -1, "MNXM1": 1, "MNXM9": 1}
_DISSIPATION: dict[str, dict[str, int]] = {
    **dict.fromkeys(["MNXM3", "MNXM63", "MNXM51", "MNXM121", "MNXM423"], _NUCLEOTIDE),
    **dict.fromkeys(["MNXM6", "MNXM10"], {"MNXM1": 1}),
    **dict.fromkeys(
        ["MNXM38", "MNXM208", "MNXM191", "MNXM223", "MNXM7517", "MNXM12233", "MNXM558"],
        {"MNXM1": 2},
    ),
    "MNXM21": {"MNXM2": -1, "MNXM1": 1, "MNXM26": 1},
    "MNXM89557": {"MNXM2": -1, "MNXM1": 2, "MNXM15": 1},
}


def _leaking(model: Any, coefficient: int) -> list[str]:
    """Metabolites a drain (``-1``) or source (``1``) can exchange.

    Each solve maximises the summed flux of the drains not yet found, so one
    LP proves the rest cannot leak or names at least one more that can.
    Capping each drain at ``LEAK_FLUX`` (as FASTCC does) makes the LP spread
    flux over as many leaks as it can; any leak scales below the cap, so the
    result is unchanged.
    """
    from memote.support.helpers import close_boundaries_sensibly

    tolerance = model.tolerance
    with model:
        close_boundaries_sensibly(model)
        exchanges = {
            metabolite.id: model.problem.Variable(f"__leak_{index}", lb=0, ub=LEAK_FLUX)
            for index, metabolite in enumerate(model.metabolites)
        }
        model.add_cons_vars(list(exchanges.values()))
        model.solver.update()
        for metabolite_id, variable in exchanges.items():
            model.constraints[metabolite_id].set_linear_coefficients(
                {variable: coefficient}
            )
        # Set the objective once: replacing it makes cobra build a symbolic
        # copy of the old one, which takes minutes at genome scale.
        model.objective = model.problem.Objective(Zero, direction="max")
        model.objective.set_linear_coefficients(dict.fromkeys(exchanges.values(), 1))
        remaining = dict(exchanges)
        leaking: set[str] = set()
        while remaining and model.slim_optimize(error_value=0.0) > tolerance:
            found = {k for k, v in remaining.items() if v.primal > tolerance}
            if not found:
                break
            leaking |= found
            model.objective.set_linear_coefficients(
                {remaining.pop(k): 0 for k in found}
            )
    return sorted(leaking)


def metabolite_leaks(model: Any) -> dict[str, list[str]]:
    """Metabolites the network can make (``produced``) or destroy
    (``consumed``) with every boundary reaction closed."""
    return {"produced": _leaking(model, -1), "consumed": _leaking(model, 1)}


def _values(items: Iterable[object]) -> set[str]:
    flat: set[str] = set()
    for item in items:
        if isinstance(item, str):
            flat.add(item)
        elif isinstance(item, Iterable):
            flat |= _values(item)
    return flat


def _find(model: Any, mnx_id: str, compartment: str) -> Any:
    """MEMOTE's metabolite lookup; ties go to the most shared cross-references.

    MetaNetX merges protonation states, so Human-GEM's hydroxide is annotated
    as water (MNXM2) too; water still shares more IDs with MEMOTE's shortlist.
    """
    from memote.support.helpers import METANETX_SHORTLIST, find_met_in_model

    try:
        return find_met_in_model(model, mnx_id, compartment)[0]
    except RuntimeError:
        references = _values(METANETX_SHORTLIST[mnx_id])
        scores: dict[Any, int] = {}
        for item in model.metabolites:
            if item.compartment == compartment:
                shared = _values((item.annotation or {}).values()) & references
                if shared:
                    scores[item] = len(shared)
        best = sorted(scores.values(), reverse=True)
        if not best or (len(best) > 1 and best[0] == best[1]):
            raise
        return max(scores, key=scores.__getitem__)


def _dissipation(model: Any, charged: str, compartment: str) -> dict[Any, float]:
    from memote.support.consistency import ENERGY_COUPLES

    stoichiometry: dict[Any, float] = {
        _find(model, charged, compartment): -1,
        _find(model, ENERGY_COUPLES[charged], compartment): 1,
    }
    for mnx_id, coefficient in _DISSIPATION[charged].items():
        metabolite = _find(model, mnx_id, compartment)
        stoichiometry[metabolite] = stoichiometry.get(metabolite, 0) + coefficient
    return stoichiometry


def energy_generating_cycles(
    model: Any, couples: Iterable[str] | None = None
) -> dict[str, object]:
    """Energy metabolites the network charges without any uptake.

    Follows MEMOTE (Fritzemeier et al. 2017): for each energy couple found in
    the cytosol, add an irreversible dissipation reaction (e.g. ATP + H2O ->
    ADP + Pi + H+), close the boundaries and maximise it. Any flux means an
    energy-generating cycle; ``cycles`` maps the charged metabolite to the
    reactions of a least-flux (pFBA) cycle, not every reaction carrying flux.
    ``not_found`` names couples whose metabolites the model lacks.
    """
    from cobra import Reaction
    from cobra.flux_analysis import pfba
    from memote.support.consistency import ENERGY_COUPLES
    from memote.support.helpers import (
        close_boundaries_sensibly,
        find_compartment_id_in_model,
    )

    compartment = find_compartment_id_in_model(model, "c")
    tolerance = model.tolerance
    cycles: dict[str, list[str]] = {}
    tested: list[str] = []
    not_found: dict[str, str] = {}
    for charged in ENERGY_COUPLES if couples is None else couples:
        try:
            stoichiometry = _dissipation(model, charged, compartment)
        except RuntimeError as error:
            not_found[charged] = str(error)
            continue
        energy = _find(model, charged, compartment).id
        tested.append(energy)
        with model:
            close_boundaries_sensibly(model)
            dissipation = Reaction("__energy_dissipation", lower_bound=0, upper_bound=1)
            dissipation.add_metabolites(stoichiometry)
            model.add_reactions([dissipation])
            model.objective = dissipation
            if model.slim_optimize(error_value=0.0) <= tolerance:
                continue
            fluxes = pfba(model).fluxes
            cycles[energy] = sorted(
                identifier
                for identifier, flux in fluxes.items()
                if identifier != dissipation.id and abs(flux) > tolerance
            )
    return {"cycles": cycles, "tested": tested, "not_found": not_found}


__all__ = ["energy_generating_cycles", "metabolite_leaks"]
