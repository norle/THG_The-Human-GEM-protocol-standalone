"""Putative-transport (PTR) gapfill: candidates, connectors, sink coverage, MILP.

The legacy three-phase pipeline, as pure functions over COBRApy models:

1. candidates: same-base metabolite pairs in allowed compartment pairs that
   either join two network components or link main-component dead ends;
2. connectors: a minimum spanning tree over components, one PTR per edge;
3. coverage and selection: per component, which blocked reactions each PTR
   unblocks with temporary dead-end sinks, then one MILP picks the PTRs. The
   MILP is solved exactly and ties are broken by candidate type, then ID.

A connector that cannot carry flux in the final model, which has no temporary
sinks, is dropped from the result. Coverage tests can run in a process pool.
"""

from __future__ import annotations

import math
import os
import random
import re
from collections.abc import Callable, Collection, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field, replace
from typing import Any

from thg_protocol.workflow.ids import metabolite_base_ids

from .core import (
    GapfillCandidate,
    GapfillResult,
    _add_candidate,
    _as_mapping,
    _compartment_pair_key,
    _metabolite_kind,
    _metrics,
    _pair_type,
    _produced_consumed,
    _resolved_parameters,
    _suffix,
    _transport_direction,
    _TransportSearch,
    _UnionFind,
    directed_transport,
)
from .exclusions import is_excluded
from .gate import apply_energy_cycle_gate

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
    """A same-base transport between two compartments.

    ``met1 < met2``; ``compartments`` and ``components`` follow that order.
    ``direction`` is 1 for an irreversible ``met1`` -> ``met2`` transport, -1
    for ``met2`` -> ``met1`` and 0 for a reversible one: a pair of a
    product-only and a substrate-only dead end (type A) can only be resolved
    by moving flux from the first to the second.
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
    direction: int = 0

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
        return directed_transport(
            self.met1,
            self.met2,
            self.direction,
            self.reaction_id,
            source="putative-transport",
            annotation=annotation,
        )


def generate_ptr_candidates(
    model: Any,
    allowed_connections: list[tuple[str, str]],
    candidate_types: list[str],
    components: Components,
    *,
    excluded_metabolites: Collection[str] = (),
) -> list[PtrCandidate]:
    """Pairs that join two components, or two main-component dead ends.

    A pair across components qualifies with any type. A pair inside the main
    component qualifies only as type A or B, i.e. when it links dead ends.
    Candidates sorted by ``reaction_id``. Metabolites matching
    ``excluded_metabolites`` (by ID, base ID or cross-reference, see
    :mod:`thg_protocol.gapfill.exclusions`) are never paired.

    Dead ends here are sign-only, as in legacy typing (agreed spec); the
    temporary sinks of :func:`compute_coverage` are bounds-aware instead.
    """
    allowed = {tuple(sorted(pair)) for pair in allowed_connections}
    mapped = _as_mapping(model)
    produced, consumed = _produced_consumed(mapped)
    buckets: dict[str, list[tuple[str, str]]] = {}
    bases = metabolite_base_ids({met["id"]: met for met in mapped["metabolites"]})
    for metabolite in model.metabolites:
        if metabolite.id in components.of and not is_excluded(
            metabolite.id,
            bases[metabolite.id],
            metabolite.annotation,
            excluded_metabolites,
        ):
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
                kinds = (
                    _metabolite_kind(met1, produced, consumed),
                    _metabolite_kind(met2, produced, consumed),
                )
                kind = _pair_type(*kinds)
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
                    direction=_transport_direction(*kinds),
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


_Variables = dict[str, tuple[Any, Any]]


def _flux_variables(model: Any, reaction_ids: Collection[str]) -> _Variables:
    """Forward and reverse solver variables of the reactions found in ``model``.

    Looked up once per call: ``reaction.forward_variable`` synchronizes the
    solver on every access, which costs more than the LPs when repeated for
    hundreds of reactions.
    """
    variables = model.variables
    reactions = model.reactions
    return {
        rid: (variables[rid], variables[reactions.get_by_id(rid).reverse_id])
        for rid in reaction_ids
        if rid in reactions
    }


def _fluxes(variables: _Variables, reaction_ids: Collection[str]) -> dict[str, float]:
    """Net flux of ``reaction_ids`` in the solver's current solution."""
    return {
        rid: variables[rid][0].primal - variables[rid][1].primal for rid in reaction_ids
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
    model: Any,
    variables: _Variables,
    signs: dict[str, int],
    epsilon: float,
    watched: Collection[str],
) -> tuple[float, dict[str, float]] | None:
    """FASTCC LP7: maximize sum z, 0 <= z_r <= epsilon, z_r <= sign_r * v_r.

    Only for reactions whose sign the bounds already fix, so the coupling
    removes no flux. Returns the optimum and the fluxes of ``watched``, or
    ``None`` if infeasible.
    """
    from optlang.symbolics import Zero

    ordered = sorted(signs)
    with model:
        z = [
            model.problem.Variable(f"_ptr_lp7_z_{index}", lb=0, ub=epsilon)
            for index in range(len(ordered))
        ]
        constraints = [
            model.problem.Constraint(Zero, ub=0, name=f"_ptr_lp7_c_{index}")
            for index in range(len(ordered))
        ]
        model.add_cons_vars([*z, *constraints])
        model.solver.update()  # rows must exist before they get coefficients
        for variable, constraint, rid in zip(z, constraints, ordered, strict=True):
            sign = signs[rid]
            forward, reverse = variables[rid]
            constraint.set_linear_coefficients(
                {variable: 1, forward: -sign, reverse: sign}
            )
        model.objective = model.problem.Objective(Zero, direction="max")
        model.objective.set_linear_coefficients({variable: 1 for variable in z})
        value = _solve(model)
        if value is None:
            return None
        return value, _fluxes(variables, watched)


def _optimize_direction(
    model: Any,
    variables: _Variables,
    weights: Mapping[str, float],
    direction: str,
    watched: Collection[str],
) -> tuple[float, dict[str, float]] | None:
    """Optimize ``sum weight_r * v_r``; ``watched`` fluxes, ``None`` if infeasible."""
    from optlang.symbolics import Zero

    coefficients = {}
    for rid, weight in weights.items():
        forward, reverse = variables[rid]
        coefficients[forward] = weight
        coefficients[reverse] = -weight
    with model:
        model.objective = model.problem.Objective(Zero, direction=direction)
        model.objective.set_linear_coefficients(coefficients)
        value = _solve(model)
        if value is None:
            return None
        return value, _fluxes(variables, watched)


def unblockable(model: Any, reaction_ids: set[str], epsilon: float) -> set[str]:
    """Reactions of ``reaction_ids`` that can carry at least ``epsilon`` flux.

    Every LP solution is a witness: a reaction it shows at ``epsilon`` or more
    is unblockable. Irreversible reactions are first pushed together: their
    fluxes cannot be negative, so a maximal sum below ``epsilon`` proves none
    of them can reach it, without building anything. Otherwise they go through
    FASTCC's LP7 loop, whose optimum below ``epsilon`` is the same proof.
    Reversible reactions are pushed both ways along one random direction
    ``c``; when ``c . v`` cannot vary, none of them can, and the witness
    settles them. When neither LP proves anything new, the varying reactions
    are maximized one at a time, so the result matches two LPs per reaction up
    to tolerance.
    """
    threshold = 0.99 * epsilon
    variables = _flux_variables(model, reaction_ids)
    reactions = {rid: model.reactions.get_by_id(rid) for rid in variables}
    found: set[str] = set()

    def harvest(fluxes: dict[str, float], pending: Collection[str]) -> set[str]:
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
    # An infinite bound could make the plain sum unbounded; LP7 caps it.
    if signs and all(
        math.isfinite(
            reactions[rid].upper_bound if sign > 0 else reactions[rid].lower_bound
        )
        for rid, sign in signs.items()
    ):
        watched = [*signs, *reversible]
        solved = _optimize_direction(model, variables, signs, "max", watched)
        if solved is None:
            return found
        value, fluxes = solved
        if value < threshold:
            signs = {}
        else:
            harvest(fluxes, watched)
            reversible -= found
            signs = {rid: sign for rid, sign in signs.items() if rid not in found}
    while signs:
        solved = _lp7(model, variables, signs, epsilon, [*signs, *reversible])
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
        high = _optimize_direction(model, variables, weights, "max", reversible)
        low = _optimize_direction(model, variables, weights, "min", reversible)
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
    """Add ``candidate`` exactly as the final model will get it."""
    _add_candidate(model, candidate.as_gapfill_candidate())


def candidate_costs(
    candidates: Collection[PtrCandidate], connection_costs: Mapping[str, float]
) -> dict[str, float]:
    """MILP cost per candidate: its compartment pair's cost, else 1.

    ``connection_costs`` maps ``"c:e"`` (order does not matter) to a positive
    cost, e.g. to make cytosol-mitochondrion transports dearer than
    cytosol-extracellular ones.
    """
    costs = {
        _compartment_pair_key(*key.split(":")): value
        for key, value in connection_costs.items()
    }
    return {
        candidate.reaction_id: costs.get(
            _compartment_pair_key(*candidate.compartments), 1.0
        )
        for candidate in candidates
    }


def _newly_unblocked(model: Any, candidate: PtrCandidate, wanted: set[str]) -> set[str]:
    """Reactions of ``wanted`` that adding ``candidate`` lets carry flux."""
    with model:
        _add_ptr(model, candidate)
        return unblockable(model, wanted, EPSILON)


#: Candidate tests that justify starting one more worker process.
TESTS_PER_WORKER = 64
#: Most worker processes started when the caller does not say how many.
MAX_AUTO_WORKERS = 8

_Test = tuple[PtrCandidate, tuple[int, ...]]
_WORKER: dict[str, Any] = {}


#: Gurobi parameters a spawned worker must share with its parent: tolerances
#: decide which reactions count as able to carry flux, and a worker that falls
#: back to Gurobi's own thread default would oversubscribe the machine.
_GUROBI_WORKER_PARAMETERS = (
    "Threads",
    "FeasibilityTol",
    "OptimalityTol",
    "IntFeasTol",
    "MIPGap",
    "Method",
)


def _gurobi_parameters(solver: str) -> dict[str, Any]:
    """Parameters set on the parent's global Gurobi environment."""
    if solver != "gurobi":
        return {}
    import gurobipy

    return {name: gurobipy.getParamInfo(name)[2] for name in _GUROBI_WORKER_PARAMETERS}


def _start_worker(
    payload: dict[str, Any],
    solver: str,
    tolerance: float,
    remaining: dict[int, set[str]],
    solver_parameters: dict[str, Any],
) -> None:
    """Rebuild the coverage model (temporary sinks included) in a worker."""
    from cobra import Configuration
    from cobra.io.dict import model_from_dict
    from cobra.util.solver import interface_to_str

    # Build the model on the parent's solver from the start: a spawned process
    # would otherwise use cobra's default, which may be an unlicensed Gurobi.
    Configuration().solver = solver
    if solver_parameters:
        import gurobipy

        for name, value in solver_parameters.items():
            gurobipy.setParam(name, value)
    model = model_from_dict(payload)
    if interface_to_str(model.problem) != solver:
        model.solver = solver
    model.tolerance = tolerance
    _WORKER.update(model=model, remaining=remaining)


def _test_in_worker(task: tuple[dict[str, Any], tuple[int, ...]]) -> list[str]:
    payload, numbers = task
    wanted = set().union(*(_WORKER["remaining"][number] for number in numbers))
    return sorted(
        _newly_unblocked(_WORKER["model"], PtrCandidate.from_dict(payload), wanted)
    )


@contextmanager
def _candidate_tests(
    model: Any, remaining: dict[int, set[str]], workers: int
) -> Iterator[Callable[[list[_Test]], list[set[str]]]]:
    """Yield ``run(tests)``: what each candidate unblocks in its components.

    A test is a candidate and the components whose remaining targets it is
    tried against. With ``workers`` above 1 the tests run in that many
    processes, each on its own copy of ``model``; the candidates are
    independent, so the answers are those of a serial run.
    """
    if workers <= 1:

        def run(tests: list[_Test]) -> list[set[str]]:
            return [
                _newly_unblocked(
                    model,
                    candidate,
                    set().union(*(remaining[number] for number in numbers)),
                )
                for candidate, numbers in tests
            ]

        yield run
        return
    import multiprocessing
    from concurrent.futures import ProcessPoolExecutor

    from cobra.io.dict import model_to_dict
    from cobra.util.solver import interface_to_str

    # Spawned, not forked: solver environments and threads do not survive a fork.
    with ProcessPoolExecutor(
        workers,
        mp_context=multiprocessing.get_context("spawn"),
        initializer=_start_worker,
        initargs=(
            model_to_dict(model),
            interface_to_str(model.problem),
            model.tolerance,
            remaining,
            _gurobi_parameters(interface_to_str(model.problem)),
        ),
    ) as pool:

        def run(tests: list[_Test]) -> list[set[str]]:
            tasks = [(candidate.to_dict(), numbers) for candidate, numbers in tests]
            chunk = max(1, min(16, len(tasks) // (workers * 4)))
            return [
                set(item) for item in pool.map(_test_in_worker, tasks, chunksize=chunk)
            ]

        yield run


def compute_coverage(
    model: Any,
    candidates: list[PtrCandidate],
    components: Components,
    *,
    min_component_size: int = 4,
    done: Mapping[int, ComponentCoverage] | None = None,
    on_component: Callable[[ComponentCoverage], None] | None = None,
    workers: int | None = 1,
) -> list[ComponentCoverage]:
    """Per original component, the blocked reactions each candidate unblocks.

    ``model`` is the phase-2 model (connectors added); ``components`` are those
    of the model before phase 2. Components below ``min_component_size`` nodes
    are skipped. A component in ``done`` is reused, and ``on_component`` is
    called after each newly computed one. ``model`` is left unchanged.

    A candidate between two components is tested once, against the targets of
    both. ``workers`` is the number of processes that test candidates;
    ``None`` starts one per ``TESTS_PER_WORKER`` tests, up to the CPU count
    and ``MAX_AUTO_WORKERS``. The result does not depend on it.
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
            sink_only = unblockable(model, blocked, epsilon)
            targets = {number: blocked & members.get(number, set()) for number in todo}
            remaining = {
                number: targets[number] - sink_only
                for number in todo
                if targets[number] - sink_only
            }
            tests: dict[str, list[int]] = {}
            for number in remaining:
                for candidate in testable.get(number, []):
                    tests.setdefault(candidate.reaction_id, []).append(number)
            if workers is None:
                workers = min(
                    os.cpu_count() or 1,
                    MAX_AUTO_WORKERS,
                    len(tests) // TESTS_PER_WORKER,
                )
            unblocked: dict[str, set[str]] = {}
            with _candidate_tests(model, remaining, min(workers, len(tests))) as run:
                for number in todo:
                    batch = [
                        (candidate, tuple(tests[candidate.reaction_id]))
                        for candidate in testable.get(number, [])
                        if number in remaining
                        and candidate.reaction_id not in unblocked
                    ]
                    for (candidate, _), found in zip(batch, run(batch), strict=True):
                        unblocked[candidate.reaction_id] = found
                    coverage = {}
                    for candidate in testable.get(number, []):
                        mine = unblocked.get(
                            candidate.reaction_id, set()
                        ) & remaining.get(number, set())
                        if mine:
                            coverage[candidate.reaction_id] = sorted(mine)
                    entry = ComponentCoverage(
                        number,
                        sorted(targets[number]),
                        sorted(targets[number] & sink_only),
                        coverage,
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


def _exact_mip(problem: Any) -> float | None:
    """Ask for a proven optimum; the relative gap in force, ``None`` if unknown.

    Gurobi and HiGHS stop at a relative gap of 1e-4 by default. With hundreds
    of targets in the objective that is more than ``tradeoff_lambda``, i.e.
    room for PTRs a true optimum would not contain.
    """
    interface = type(problem).__module__
    if interface == "optlang.gurobi_interface":
        problem.problem.Params.MIPGap = 0.0
        return float(problem.problem.Params.MIPGap)
    if interface == "optlang.glpk_interface":
        return 0.0  # GLPK's default, which optlang leaves alone
    if interface == "optlang.hybrid_interface":
        # HiGHS (default gap 1e-4). optlang rebuilds the HiGHS options from its
        # own settings on every solve, so the gap is added to that step.
        inner = problem.problem
        base = inner.highs_settings

        def highs_settings() -> Any:
            options = base()
            options.mip_rel_gap = 0.0
            return options

        inner.highs_settings = highs_settings
        return float(highs_settings().mip_rel_gap)
    return None


def select_unblockers(
    coverage: list[ComponentCoverage],
    *,
    tradeoff_lambda: float,
    budget: int,
    interface: Any,
    costs: Mapping[str, float] | None = None,
    ranks: Mapping[str, int] | None = None,
) -> Selection:
    """Maximize covered targets minus ``tradeoff_lambda * cost`` per selected PTR.

    ``costs`` gives a candidate's relative price (default 1), so implausible
    transports must unblock more to be worth adding.

    One global problem on an optlang ``interface``: binary y per candidate,
    z_r <= sum of y over the candidates covering target r, sum y <= budget.
    Status is ``partial`` when the budget binds with coverable targets left.

    Equally good selections are common (two transports that unblock the same
    reactions), and which one a solver returns is arbitrary. A second solve
    therefore keeps the coverage and cost of the optimum and minimizes the
    summed preference position of the selected candidates, ordered by
    ``ranks`` (lower first, default 0) and then by ID.
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
        "interface": interface.__name__.rsplit(".", 1)[-1],
    }
    if not candidates:
        return Selection([], [], "solved", solver={**solver, "milp_status": "empty"})
    price = {name: (costs or {}).get(name, 1.0) for name in candidates}
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
        add(list(z.values()))
        - tradeoff_lambda * add([price[name] * y[name] for name in y]),
        direction="max",
    )
    solver["mip_gap"] = _exact_mip(problem)

    def solution() -> tuple[list[str], list[str]]:
        selected = sorted(name for name, variable in y.items() if variable.primal > 0.5)
        chosen = set(selected)
        return selected, sorted(
            target for target, names in covering.items() if chosen.intersection(names)
        )

    status = problem.optimize()
    solver["milp_status"] = status
    if status != "optimal":
        return Selection(
            [], [], "failed", f"sink MILP ended with status {status}", solver
        )
    solver["objective"] = problem.objective.value
    selected, covered = solution()
    # Covering fewer targets or paying more would no longer be an optimum.
    spent = sum(price[name] for name in selected)
    problem.add(
        [
            interface.Constraint(
                add(list(z.values())), lb=len(covered) - 0.5, name="keep_coverage"
            ),
            interface.Constraint(
                add([price[name] * y[name] for name in y]),
                ub=spent + 1e-6 * max(1.0, spent),
                name="keep_cost",
            ),
        ]
    )
    order = sorted(candidates, key=lambda name: ((ranks or {}).get(name, 0), name))
    problem.objective = interface.Objective(
        add([position * y[name] for position, name in enumerate(order, 1)]),
        direction="min",
    )
    status = problem.optimize()
    solver["tie_break"] = {"order": "rank, then ID", "milp_status": status}
    if status != "optimal":
        return Selection(
            [], [], "failed", f"sink MILP tie-break ended with status {status}", solver
        )
    selected, covered = solution()
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
    The result selects the connectors (phase 2) that carry flux in the final
    model and then the MILP's PTRs (phase 3). A connector that stays inactive
    is removed, listed in ``verification["inactive_connectors"]`` and marked
    ``connector-inactive`` in the candidate coverage. ``solver`` carries MILP
    metadata and the verification report.
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
            excluded_metabolites=parameters["excluded_metabolites"],
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
        costs=candidate_costs(candidates, parameters["connection_costs"]),
        ranks={
            candidate.reaction_id: _RANK[candidate.type] for candidate in candidates
        },
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
    gate: dict[str, Any] = {"status": "disabled"}
    if parameters["energy_cycle_gate"]:
        gate = apply_energy_cycle_gate(
            result_model,
            [candidate.reaction_id for candidate in [*connectors, *chosen]],
        )
    rejected = set(gate.get("rejected", {}))
    connectors = [item for item in connectors if item.reaction_id not in rejected]
    chosen = [item for item in chosen if item.reaction_id not in rejected]
    targets = {target for item in coverage for target in item.targets}
    # A connector joins components on paper only until it can carry flux. One
    # that cannot is left out: removing a blocked reaction changes no flux.
    inactive: list[str] = []
    while True:
        verification = verify_selection(result_model, connectors, chosen, targets)
        if not verification["inactive_connectors"]:
            break
        inactive += verification["inactive_connectors"]
        result_model.remove_reactions(verification["inactive_connectors"])
        connectors = [item for item in connectors if item.reaction_id not in inactive]
    verification["inactive_connectors"] = inactive
    connector_ids = {candidate.reaction_id for candidate in connectors}
    chosen_ids = {candidate.reaction_id for candidate in chosen}
    candidate_coverage = {
        candidate.reaction_id: "rejected-energy-cycle"
        if candidate.reaction_id in rejected
        else "already-present"
        if candidate.present
        else "connector-inactive"
        if candidate.reaction_id in inactive
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
        "partial" if rejected else selection.status,
        solver={
            **selection.solver,
            "energy_cycle_gate": gate,
            "connectors": len(connectors),
            "targets": len(targets),
            "sink_only": sum(len(item.sink_only) for item in coverage),
            "verification": verification,
        },
        method="sink-milp",
        parameters=parameters,
        before_metrics=before,
        after_metrics=_metrics(result_model),
        stop_reason="energy-cycle-gate"
        if rejected
        else "max-additions"
        if selection.status == "partial"
        else "milp-optimal",
    )
