"""Putative-transport (PTR) gapfill: candidates, connectors, sink coverage, MILP.

The legacy three-phase pipeline, as pure functions over COBRApy models:

1. candidates: same-base metabolite pairs in allowed compartment pairs that
   either join two network components or link main-component dead ends;
2. connectors: a minimum spanning tree over components, one PTR per edge;
3. coverage and selection: per component, which blocked reactions each PTR
   unblocks with temporary dead-end sinks, then one MILP picks the PTRs.
"""

from __future__ import annotations

import math
import random
import re
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass, field, replace
from typing import Any

from thg_protocol.workflow.ids import metabolite_base_ids

from .core import (
    GapfillCandidate,
    GapfillResult,
    _add_candidate,
    _as_mapping,
    _metabolite_kind,
    _metrics,
    _pair_type,
    _produced_consumed,
    _resolved_parameters,
    _suffix,
    _TransportSearch,
    _UnionFind,
)

_RANK = {"A": 0, "B": 1, "C": 2}
# Flux a reaction must reach to count as unblocked (FASTCC's default). Legacy
# used 10x the solver tolerance, which equals Gurobi's feasibility tolerance,
# so forcing that flux "succeeded" on fully blocked networks.
EPSILON = 1e-4


@dataclass(frozen=True)
class Components:
    """Connected components of the undirected reaction–metabolite graph.

    ``of`` maps metabolite and reaction IDs to a component number; numbers are
    ordered by node count, descending, so 1 is the main component.
    """

    of: dict[str, int]
    sizes: dict[int, int]


def network_components(model: Any) -> Components:
    """Number components by size; metabolites in no reaction get no entry.

    Reactions and metabolites share one ID space here, so a reaction ID that
    is also a metabolite ID raises instead of silently merging two nodes.
    """
    shared = sorted(
        {reaction.id for reaction in model.reactions}
        & {metabolite.id for metabolite in model.metabolites}
    )
    if shared:
        raise ValueError(
            f"IDs used by both a reaction and a metabolite: {', '.join(shared)}"
        )
    sets = _UnionFind()
    for reaction in model.reactions:
        sets.add(reaction.id)
        for metabolite in reaction.metabolites:
            sets.add(metabolite.id)
            sets.union(reaction.id, metabolite.id)
    groups: dict[str, list[str]] = {}
    for node in sets:
        groups.setdefault(sets.find(node), []).append(node)
    ordered = sorted(groups.values(), key=lambda nodes: (-len(nodes), min(nodes)))
    of = {node: number for number, nodes in enumerate(ordered, 1) for node in nodes}
    return Components(
        of, {number: len(nodes) for number, nodes in enumerate(ordered, 1)}
    )


@dataclass(frozen=True)
class PtrCandidate:
    """A reversible same-base transport between two compartments.

    ``met1 < met2``; ``compartments`` and ``components`` follow that order.
    ``present`` marks a pair an existing transport already covers: such a
    candidate is reported but never added.
    """

    met1: str
    met2: str
    base: str
    compartments: tuple[str, str]
    components: tuple[int, int]
    type: str
    reaction_id: str
    present: bool = False

    @property
    def main_only(self) -> bool:
        return self.components == (1, 1)

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "compartments": list(self.compartments),
            "components": list(self.components),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> PtrCandidate:
        return cls(
            **{
                **payload,
                "compartments": tuple(payload["compartments"]),
                "components": tuple(payload["components"]),
            }
        )

    def as_gapfill_candidate(self, phase: int | None = None) -> GapfillCandidate:
        annotation: dict[str, Any] = {"type": self.type, "base": self.base}
        if phase is not None:
            annotation["phase"] = phase
        return GapfillCandidate(
            self.reaction_id,
            {self.met1: -1.0, self.met2: 1.0},
            -1000.0,
            1000.0,
            source="putative-transport",
            annotation=annotation,
        )


def generate_ptr_candidates(
    model: Any,
    allowed_connections: list[tuple[str, str]],
    candidate_types: list[str],
    components: Components,
) -> list[PtrCandidate]:
    """Pairs that join two components, or two main-component dead ends.

    A pair across components qualifies with any type. A pair inside the main
    component qualifies only as type A or B, i.e. when it links dead ends.
    Candidates sorted by ``reaction_id``.

    Dead ends here are sign-only, as in legacy typing (agreed spec); the
    temporary sinks of :func:`compute_coverage` are bounds-aware instead.
    """
    allowed = {tuple(sorted(pair)) for pair in allowed_connections}
    mapped = _as_mapping(model)
    produced, consumed = _produced_consumed(mapped)
    buckets: dict[str, list[tuple[str, str]]] = {}
    bases = metabolite_base_ids({met["id"]: met for met in mapped["metabolites"]})
    for metabolite in model.metabolites:
        if metabolite.id in components.of:
            compartment = metabolite.compartment or _suffix(metabolite.id)
            buckets.setdefault(bases[metabolite.id], []).append(
                (metabolite.id, compartment)
            )
    search = _TransportSearch(mapped)
    result = []
    for base, members in buckets.items():
        members.sort()
        for index, (met1, compartment1) in enumerate(members):
            for met2, compartment2 in members[index + 1 :]:
                if tuple(sorted((compartment1, compartment2))) not in allowed:
                    continue
                kind = _pair_type(
                    _metabolite_kind(met1, produced, consumed),
                    _metabolite_kind(met2, produced, consumed),
                )
                pair = (components.of[met1], components.of[met2])
                if kind not in candidate_types or (
                    pair[0] == pair[1] and (pair[0] != 1 or kind == "C")
                ):
                    continue
                candidate = PtrCandidate(
                    met1,
                    met2,
                    base,
                    (compartment1, compartment2),
                    pair,
                    kind,
                    re.sub(r"[^A-Za-z0-9_]", "_", f"GAPFILL_PTR_{met1}_{met2}"),
                )
                if search.covers(candidate.as_gapfill_candidate()):
                    candidate = replace(candidate, present=True)
                result.append(candidate)
    return sorted(result, key=lambda candidate: candidate.reaction_id)


def select_connectors(candidates: list[PtrCandidate]) -> list[PtrCandidate]:
    """Join every component with one PTR per spanning-tree edge (Kruskal).

    Each component pair is represented by its best candidate (type A before B
    before C, then base and metabolite IDs); edges are taken in that order.
    """
    representatives: dict[tuple[int, int], PtrCandidate] = {}
    for candidate in candidates:
        if candidate.present or candidate.components[0] == candidate.components[1]:
            continue
        pair = tuple(sorted(candidate.components))
        best = representatives.get(pair)
        if best is None or _connector_key(candidate) < _connector_key(best):
            representatives[pair] = candidate
    sets = _UnionFind(component for pair in representatives for component in pair)
    selected = []
    for candidate in sorted(representatives.values(), key=_connector_key):
        if sets.union(*candidate.components):
            selected.append(candidate)
    return selected


def _connector_key(candidate: PtrCandidate) -> tuple[int, str, str, str]:
    return (_RANK[candidate.type], candidate.base, candidate.met1, candidate.met2)


def _fluxes(model: Any, reactions: dict[str, Any]) -> dict[str, float]:
    primal = model.solver.primal_values
    return {
        rid: primal[reaction.forward_variable.name]
        - primal[reaction.reverse_variable.name]
        for rid, reaction in reactions.items()
    }


def _solve(model: Any) -> float | None:
    """Optimum, ``None`` if infeasible; any other non-optimal status raises.

    Unbounded or numerically troubled LPs would otherwise read as "blocked".
    """
    value = model.slim_optimize(error_value=math.nan)
    if not math.isnan(value):
        return value
    status = model.solver.status
    if status == "infeasible":
        return None
    raise RuntimeError(f"flux LP ended with status {status}")


def _lp7(
    model: Any, signs: dict[str, int], epsilon: float, watched: dict[str, Any]
) -> tuple[float, dict[str, float]] | None:
    """FASTCC LP7: maximize sum z, 0 <= z_r <= epsilon, z_r <= sign_r * v_r.

    Only for reactions whose sign the bounds already fix, so the coupling
    removes no flux. Returns the optimum and the fluxes of ``watched``, or
    ``None`` if infeasible.
    """
    from optlang.symbolics import Zero

    reactions = [model.reactions.get_by_id(rid) for rid in sorted(signs)]
    with model:
        z = [
            model.problem.Variable(f"_ptr_lp7_z_{index}", lb=0, ub=epsilon)
            for index in range(len(reactions))
        ]
        constraints = [
            model.problem.Constraint(Zero, ub=0, name=f"_ptr_lp7_c_{index}")
            for index in range(len(reactions))
        ]
        model.add_cons_vars([*z, *constraints])
        for variable, constraint, reaction in zip(
            z, constraints, reactions, strict=True
        ):
            sign = signs[reaction.id]
            constraint.set_linear_coefficients(
                {
                    variable: 1,
                    reaction.forward_variable: -sign,
                    reaction.reverse_variable: sign,
                }
            )
        model.objective = model.problem.Objective(Zero, direction="max")
        model.objective.set_linear_coefficients({variable: 1 for variable in z})
        value = _solve(model)
        if value is None:
            return None
        return value, _fluxes(model, watched)


def _optimize_direction(
    model: Any, weights: dict[str, float], direction: str, watched: dict[str, Any]
) -> tuple[float, dict[str, float]] | None:
    """Optimize ``sum weight_r * v_r``; ``watched`` fluxes, ``None`` if infeasible."""
    from optlang.symbolics import Zero

    coefficients = {}
    for rid, weight in weights.items():
        reaction = model.reactions.get_by_id(rid)
        coefficients[reaction.forward_variable] = weight
        coefficients[reaction.reverse_variable] = -weight
    with model:
        model.objective = model.problem.Objective(Zero, direction=direction)
        model.objective.set_linear_coefficients(coefficients)
        value = _solve(model)
        if value is None:
            return None
        return value, _fluxes(model, watched)


def unblockable(model: Any, reaction_ids: set[str], epsilon: float) -> set[str]:
    """Reactions of ``reaction_ids`` that can carry at least ``epsilon`` flux.

    Every LP solution is a witness: a reaction it shows at ``epsilon`` or more
    is unblockable. Irreversible reactions go through FASTCC's LP7 loop, whose
    optimum below ``epsilon`` proves none of them can reach it. Reversible
    reactions are pushed both ways along one random direction ``c``; when
    ``c . v`` cannot vary, none of them can, and the witness settles them.
    When neither LP proves anything new, the varying reactions are maximized
    one at a time, so the result matches two LPs per reaction up to tolerance.
    """
    threshold = 0.99 * epsilon
    reactions = {
        rid: model.reactions.get_by_id(rid)
        for rid in reaction_ids
        if rid in model.reactions
    }
    found: set[str] = set()

    def harvest(fluxes: dict[str, float], pending: set[str]) -> set[str]:
        new = {rid for rid in pending if abs(fluxes[rid]) >= threshold}
        found.update(new)
        return new

    signs = {}
    for rid, reaction in reactions.items():
        if reaction.lower_bound >= 0 and reaction.upper_bound >= threshold:
            signs[rid] = 1
        elif reaction.upper_bound <= 0 and reaction.lower_bound <= -threshold:
            signs[rid] = -1
    reversible = {
        rid
        for rid, reaction in reactions.items()
        if reaction.lower_bound < 0 < reaction.upper_bound
    }
    while signs:
        solved = _lp7(model, signs, epsilon, reactions)
        if solved is None:
            return found
        value, fluxes = solved
        harvest(fluxes, reversible)
        reversible -= found
        if value < threshold:
            break
        new = harvest(fluxes, set(signs))
        if not new:
            # Flux spread too thin to reach epsilon anywhere: settle singly.
            tried = {rid for rid in signs if abs(fluxes[rid]) > 0} or set(signs)
            for rid in tried:
                if _max_flux(model, rid, signs[rid]) >= threshold:
                    found.add(rid)
            new = tried
        signs = {rid: sign for rid, sign in signs.items() if rid not in new}
    rng = random.Random(0)
    while reversible:
        weights = {
            rid: rng.choice((-1, 1)) * rng.uniform(0.5, 1.0)
            for rid in sorted(reversible)
        }
        high = _optimize_direction(model, weights, "max", reactions)
        low = _optimize_direction(model, weights, "min", reactions)
        if high is None or low is None:
            return found
        new = harvest(high[1], reversible) | harvest(low[1], reversible)
        reversible -= new
        if new:
            continue
        if high[0] - low[0] < threshold:
            break
        tried = {
            rid for rid in reversible if abs(high[1][rid] - low[1][rid]) > 0
        } or set(reversible)
        for rid in tried:
            if max(_max_flux(model, rid, 1), _max_flux(model, rid, -1)) >= threshold:
                found.add(rid)
        reversible -= tried
    return found


def _max_flux(model: Any, reaction_id: str, sign: int) -> float:
    reaction = model.reactions.get_by_id(reaction_id)
    with model:
        model.objective = model.problem.Objective(
            sign * reaction.flux_expression, direction="max"
        )
        value = _solve(model)
        return 0.0 if value is None else value


@dataclass
class ComponentCoverage:
    """Blocked reactions of one original component and what each PTR unblocks.

    ``targets`` are reactions originally in the component that are blocked
    without sinks; ``sink_only`` are those the temporary sinks unblock alone,
    which no candidate is credited for. ``coverage`` lists, per candidate
    reaction ID with any coverage, the targets it newly unblocks.
    """

    component: int
    targets: list[str]
    sink_only: list[str]
    coverage: dict[str, list[str]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> ComponentCoverage:
        return cls(
            int(payload["component"]),
            list(payload["targets"]),
            list(payload["sink_only"]),
            {key: list(value) for key, value in payload["coverage"].items()},
        )


def _add_temporary_exchanges(model: Any) -> None:
    """Source every dead-end substrate and sink every dead-end product.

    Dead ends account for bounds (legacy ``get_deadend_info``); metabolites
    that can be neither produced nor consumed get nothing.
    """
    from cobra import Reaction

    exchanges = []
    for metabolite in model.metabolites:
        produced = consumed = False
        for reaction in metabolite.reactions:
            coefficient = reaction.metabolites[metabolite]
            forward, backward = reaction.upper_bound > 0, reaction.lower_bound < 0
            produced |= (coefficient > 0 and forward) or (coefficient < 0 and backward)
            consumed |= (coefficient < 0 and forward) or (coefficient > 0 and backward)
        if produced != consumed:
            exchange = Reaction(f"_PTR_TEMP_{metabolite.id}", lower_bound=0.0)
            exchange.add_metabolites({metabolite: 1.0 if consumed else -1.0})
            exchanges.append(exchange)
    model.add_reactions(exchanges)


def _add_ptr(model: Any, candidate: PtrCandidate) -> None:
    from cobra import Reaction

    reaction = Reaction(candidate.reaction_id, lower_bound=-1000.0, upper_bound=1000.0)
    reaction.add_metabolites(
        {
            model.metabolites.get_by_id(candidate.met1): -1.0,
            model.metabolites.get_by_id(candidate.met2): 1.0,
        }
    )
    model.add_reactions([reaction])


def compute_coverage(
    model: Any,
    candidates: list[PtrCandidate],
    components: Components,
    *,
    min_component_size: int = 4,
    done: Mapping[int, ComponentCoverage] | None = None,
    on_component: Callable[[ComponentCoverage], None] | None = None,
) -> list[ComponentCoverage]:
    """Per original component, the blocked reactions each candidate unblocks.

    ``model`` is the phase-2 model (connectors added); ``components`` are those
    of the model before phase 2. Components below ``min_component_size`` nodes
    are skipped. A component in ``done`` is reused, and ``on_component`` is
    called after each newly computed one. ``model`` is left unchanged.
    """
    done = dict(done or {})
    epsilon = EPSILON
    numbers = sorted(
        number
        for number, size in components.sizes.items()
        if size >= min_component_size
    )
    members: dict[int, set[str]] = {}
    for reaction in model.reactions:
        number = components.of.get(reaction.id)
        if number is not None:
            members.setdefault(number, set()).add(reaction.id)
    testable: dict[int, list[PtrCandidate]] = {}
    for candidate in candidates:
        if not candidate.present and candidate.reaction_id not in model.reactions:
            for number in set(candidate.components):
                testable.setdefault(number, []).append(candidate)
    todo = [number for number in numbers if number not in done]
    computed: dict[int, ComponentCoverage] = {}
    if todo:
        reactions = set().union(*(members.get(number, set()) for number in todo))
        blocked = reactions - unblockable(model, reactions, epsilon)
        with model:
            _add_temporary_exchanges(model)
            for number in todo:
                targets = blocked & members.get(number, set())
                sink_only = unblockable(model, targets, epsilon)
                remaining = targets - sink_only
                coverage = {}
                for candidate in testable.get(number, []) if remaining else []:
                    with model:
                        _add_ptr(model, candidate)
                        unblocked = unblockable(model, remaining, epsilon)
                    if unblocked:
                        coverage[candidate.reaction_id] = sorted(unblocked)
                entry = ComponentCoverage(
                    number, sorted(targets), sorted(sink_only), coverage
                )
                computed[number] = entry
                if on_component is not None:
                    on_component(entry)
    return [done.get(number) or computed[number] for number in numbers]


@dataclass
class Selection:
    """MILP choice of unblocking PTRs; ``failed`` carries the solver status."""

    selected: list[str]
    covered: list[str]
    status: str
    failure: str | None = None
    solver: dict[str, Any] = field(default_factory=dict)


def select_unblockers(
    coverage: list[ComponentCoverage],
    *,
    tradeoff_lambda: float,
    budget: int,
    interface: Any,
) -> Selection:
    """Maximize covered targets minus ``tradeoff_lambda`` per selected PTR.

    One global problem on an optlang ``interface``: binary y per candidate,
    z_r <= sum of y over the candidates covering target r, sum y <= budget.
    Status is ``partial`` when the budget binds with coverable targets left.
    """
    from optlang.symbolics import add

    covering: dict[str, list[str]] = {}
    for component in coverage:
        for candidate, targets in component.coverage.items():
            for target in targets:
                covering.setdefault(target, []).append(candidate)
    candidates = sorted({item for items in covering.values() for item in items})
    budget = max(budget, 0)
    solver = {
        "strategy": "sink-milp",
        "tradeoff_lambda": tradeoff_lambda,
        "budget": budget,
        "candidates": len(candidates),
        "coverable_targets": len(covering),
    }
    if not candidates:
        return Selection([], [], "solved", solver={**solver, "milp_status": "empty"})
    problem = interface.Model()
    y = {
        name: interface.Variable(f"y_{index}", type="binary")
        for index, name in enumerate(candidates)
    }
    targets = sorted(covering)
    z = {
        target: interface.Variable(f"z_{index}", lb=0, ub=1)
        for index, target in enumerate(targets)
    }
    problem.add([*y.values(), *z.values()])
    problem.add(
        [
            interface.Constraint(
                z[target] - add([y[name] for name in covering[target]]),
                ub=0,
                name=f"cover_{index}",
            )
            for index, target in enumerate(targets)
        ]
        + [interface.Constraint(add(list(y.values())), ub=budget, name="budget")]
    )
    problem.objective = interface.Objective(
        add(list(z.values())) - tradeoff_lambda * add(list(y.values())), direction="max"
    )
    status = problem.optimize()
    solver["milp_status"] = status
    if status != "optimal":
        return Selection(
            [], [], "failed", f"sink MILP ended with status {status}", solver
        )
    solver["objective"] = problem.objective.value
    selected = sorted(name for name, variable in y.items() if variable.primal > 0.5)
    chosen = set(selected)
    covered = sorted(
        target for target, names in covering.items() if chosen.intersection(names)
    )
    partial = len(selected) >= budget and len(covered) < len(covering)
    return Selection(
        selected, covered, "partial" if partial else "solved", solver=solver
    )


def verify_selection(
    model: Any,
    connectors: list[PtrCandidate],
    selected: list[PtrCandidate],
    targets: set[str],
) -> dict[str, list[str]]:
    """Check the final model without sinks; report, never act.

    ``verified_unblocked`` are the targets that now carry flux and
    ``inactive_connectors`` the phase-2 reactions that carry none. Connectors
    and selected PTRs missing from ``model`` are added for the check only.
    """
    with model:
        for candidate in [*connectors, *selected]:
            if candidate.reaction_id not in model.reactions:
                _add_ptr(model, candidate)
        connector_ids = {candidate.reaction_id for candidate in connectors}
        active = unblockable(model, set(targets) | connector_ids, EPSILON)
    return {
        "verified_unblocked": sorted(active & set(targets)),
        "inactive_connectors": [
            candidate.reaction_id
            for candidate in connectors
            if candidate.reaction_id not in active
        ],
    }


def ptr_collisions(model: Any, candidates: list[PtrCandidate]) -> list[str]:
    """Reaction IDs of addable candidates that ``model`` already uses."""
    return sorted(
        candidate.reaction_id
        for candidate in candidates
        if not candidate.present and candidate.reaction_id in model.reactions
    )


def _failed(
    model: Any, parameters: dict[str, Any], before: dict[str, Any], reason: str
) -> GapfillResult:
    return GapfillResult(
        model,
        [],
        {},
        "failed",
        reason,
        {"strategy": "sink-milp"},
        "sink-milp",
        parameters,
        before,
        before,
        reason,
    )


def run_sink_milp(
    model: Any,
    parameters: dict[str, Any],
    *,
    candidates: list[PtrCandidate] | None = None,
    connectors: list[PtrCandidate] | None = None,
    coverage: list[ComponentCoverage] | None = None,
) -> GapfillResult:
    """Run candidates, connectors, coverage and MILP on a copy of ``model``.

    Phases already computed (by workflow stages) are passed in and reused.
    The result selects the connectors (phase 2) and then the MILP's PTRs
    (phase 3); ``solver`` carries MILP metadata and the verification report.
    """
    parameters = _resolved_parameters("sink-milp", parameters)
    if isinstance(model, dict):
        from cobra.io.dict import model_from_dict

        model = model_from_dict(model)
    result_model = model.copy()
    before = _metrics(result_model)
    components = network_components(model)
    if candidates is None:
        candidates = generate_ptr_candidates(
            model,
            parameters["allowed_connections"],
            parameters["candidate_types"],
            components,
        )
    if connectors is None:
        connectors = select_connectors(candidates)
    budget = parameters["max_additions"] - len(connectors)
    if budget < 0:
        return _failed(
            result_model,
            parameters,
            before,
            f"{len(connectors)} connectors exceed max_additions",
        )
    collisions = ptr_collisions(result_model, candidates)
    if collisions:
        return _failed(
            result_model,
            parameters,
            before,
            f"reaction-ID collision: {', '.join(collisions)}",
        )
    for candidate in connectors:
        _add_candidate(result_model, candidate.as_gapfill_candidate(phase=2))
    if coverage is None:
        coverage = compute_coverage(
            result_model,
            candidates,
            components,
            min_component_size=parameters["min_component_size"],
        )
    selection = select_unblockers(
        coverage,
        tradeoff_lambda=parameters["tradeoff_lambda"],
        budget=budget,
        interface=result_model.solver.interface,
    )
    if selection.status == "failed":
        failed = _failed(model.copy(), parameters, before, "milp-failed")
        failed.failure = selection.failure
        failed.solver = {**failed.solver, **selection.solver}
        return failed
    by_id = {candidate.reaction_id: candidate for candidate in candidates}
    chosen = [by_id[reaction_id] for reaction_id in selection.selected]
    for candidate in chosen:
        _add_candidate(result_model, candidate.as_gapfill_candidate(phase=3))
    targets = {target for item in coverage for target in item.targets}
    verification = verify_selection(result_model, connectors, chosen, targets)
    connector_ids = {candidate.reaction_id for candidate in connectors}
    chosen_ids = set(selection.selected)
    candidate_coverage = {
        candidate.reaction_id: "already-present"
        if candidate.present
        else "connector"
        if candidate.reaction_id in connector_ids
        else "selected"
        if candidate.reaction_id in chosen_ids
        else "available"
        for candidate in candidates
    }
    return GapfillResult(
        result_model,
        [candidate.reaction_id for candidate in [*connectors, *chosen]],
        candidate_coverage,
        selection.status,
        solver={
            **selection.solver,
            "connectors": len(connectors),
            "targets": len(targets),
            "sink_only": sum(len(item.sink_only) for item in coverage),
            "verification": verification,
        },
        method="sink-milp",
        parameters=parameters,
        before_metrics=before,
        after_metrics=_metrics(result_model),
        stop_reason="max-additions"
        if selection.status == "partial"
        else "milp-optimal",
    )
