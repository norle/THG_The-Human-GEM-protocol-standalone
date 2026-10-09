"""Small, deterministic gapfill operations for JSON model mappings."""

from __future__ import annotations

import re
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

__all__ = [
    "GapfillCandidate",
    "GapfillResult",
    "run_gapfill",
    "gapfill_model",
    "generate_gapfill_plan",
    "validate_gapfill_plan",
    "apply_gapfill_plan",
]


@dataclass(frozen=True)
class GapfillCandidate:
    """A proposed reaction that may be added by a gapfill operation."""

    id: str
    metabolites: dict[str, float]
    lower_bound: float = 0.0
    upper_bound: float = 1000.0
    cost: float = 1.0
    source: str = "candidate-universe"
    annotation: dict[str, Any] = field(default_factory=dict)


@dataclass
class GapfillResult:
    """Explicit, serializable outcome of a gapfill attempt."""

    model: Any
    selected: list[str]
    candidate_coverage: dict[str, str]
    status: str
    failure: str | None = None
    solver: dict[str, Any] = field(default_factory=dict)
    method: str = "deterministic"
    parameters: dict[str, Any] = field(default_factory=dict)
    before_metrics: dict[str, Any] = field(default_factory=dict)
    after_metrics: dict[str, Any] = field(default_factory=dict)
    stop_reason: str = ""

    @property
    def selected_reactions(self) -> list[str]:
        """Canonical name for selected reactions (``selected`` is retained)."""
        return self.selected

    def as_dict(self) -> dict[str, Any]:
        return {
            "selected": list(self.selected),
            "candidate_coverage": dict(self.candidate_coverage),
            "status": self.status,
            "failure": self.failure,
            "solver": dict(self.solver),
            "method": self.method,
            "parameters": dict(self.parameters),
            "selected_reactions": list(self.selected),
            "before_metrics": dict(self.before_metrics),
            "after_metrics": dict(self.after_metrics),
            "stop_reason": self.stop_reason,
        }


def _candidate_model_copy(model: Any) -> Any:
    return deepcopy(model) if isinstance(model, dict) else model.copy()


def _add_candidate(model: Any, candidate: GapfillCandidate) -> None:
    if isinstance(model, dict):
        model.setdefault("reactions", []).append(
            {
                "id": candidate.id,
                "metabolites": dict(candidate.metabolites),
                "lower_bound": candidate.lower_bound,
                "upper_bound": candidate.upper_bound,
                "annotation": {**candidate.annotation, "thg_protocol": "gapfill"},
            }
        )
        return
    from cobra import Reaction

    reaction = Reaction(
        candidate.id,
        lower_bound=candidate.lower_bound,
        upper_bound=candidate.upper_bound,
    )
    reaction.add_metabolites(
        {
            model.metabolites.get_by_id(mid): coefficient
            for mid, coefficient in candidate.metabolites.items()
        }
    )
    reaction.annotation.update(candidate.annotation)
    reaction.annotation["thg_protocol"] = "gapfill"
    model.add_reactions([reaction])


def run_gapfill(
    model: Any,
    candidates: list[GapfillCandidate | dict[str, Any]],
    *,
    max_additions: int | None = None,
) -> GapfillResult:
    """Run deterministic gapfill without temporary sinks or sources."""
    normalized = [
        item if isinstance(item, GapfillCandidate) else GapfillCandidate(**item)
        for item in candidates
    ]
    candidate_ids = [candidate.id for candidate in normalized]
    if len(candidate_ids) != len(set(candidate_ids)):
        return GapfillResult(
            _candidate_model_copy(model),
            [],
            {candidate.id: "invalid-duplicate" for candidate in normalized},
            "failed",
            "candidate IDs must be unique",
            {"strategy": "deterministic"},
        )
    ordered = sorted(normalized, key=lambda item: (item.cost, item.id))
    limit = len(ordered) if max_additions is None else max(0, max_additions)
    selected = ordered[:limit]
    result_model = _candidate_model_copy(model)
    coverage = {candidate.id: "available" for candidate in ordered}
    try:
        for candidate in selected:
            if isinstance(result_model, dict):
                known = {item["id"] for item in result_model.get("metabolites", [])}
                missing = sorted(set(candidate.metabolites) - known)
                if missing:
                    raise KeyError(
                        f"candidate {candidate.id} references unknown "
                        f"metabolites: {missing}"
                    )
            _add_candidate(result_model, candidate)
            coverage[candidate.id] = "selected"
    except (KeyError, ValueError, TypeError) as error:
        return GapfillResult(
            result_model,
            [],
            coverage,
            "failed",
            str(error),
            {"strategy": "deterministic"},
        )
    return GapfillResult(
        result_model,
        [candidate.id for candidate in selected],
        coverage,
        "solved",
        solver={
            "strategy": "deterministic",
            "objective": sum(candidate.cost for candidate in selected),
        },
    )


class _UnionFind:
    """Disjoint sets with path halving; ``union`` keeps the left root."""

    def __init__(self, items: Any = ()) -> None:
        self.parent: dict[Any, Any] = {item: item for item in items}

    def __contains__(self, item: Any) -> bool:
        return item in self.parent

    def __iter__(self) -> Any:
        return iter(self.parent)

    def add(self, item: Any) -> None:
        self.parent.setdefault(item, item)

    def find(self, item: Any) -> Any:
        parent = self.parent
        while parent[item] != item:
            parent[item] = parent[parent[item]]
            item = parent[item]
        return item

    def union(self, left: Any, right: Any) -> bool:
        """Merge two sets; ``False`` if they were already one."""
        left, right = self.find(left), self.find(right)
        if left == right:
            return False
        self.parent[right] = left
        return True


def _components(model: dict[str, Any]) -> dict[str, int]:
    sets = _UnionFind(met["id"] for met in model.get("metabolites", []))
    for reaction in model.get("reactions", []):
        ids = [mid for mid in reaction.get("metabolites", {}) if mid in sets]
        for metabolite_id in ids[1:]:
            sets.union(ids[0], metabolite_id)
    roots: dict[str, int] = {}
    result: dict[str, int] = {}
    for metabolite_id in sets:
        root = sets.find(metabolite_id)
        roots.setdefault(root, len(roots) + 1)
        result[metabolite_id] = roots[root]
    return result


def _suffix(metabolite_id: str) -> str:
    return (
        re.search(r"[a-z]+$", metabolite_id).group(0)
        if re.search(r"[a-z]+$", metabolite_id)
        else ""
    )


def _produced_consumed(model: dict[str, Any]) -> tuple[set[str], set[str]]:
    produced, consumed = set(), set()
    for reaction in model.get("reactions", []):
        for metabolite_id, coefficient in reaction.get("metabolites", {}).items():
            if coefficient > 0:
                produced.add(metabolite_id)
            elif coefficient < 0:
                consumed.add(metabolite_id)
    return produced, consumed


def _metabolite_kind(metabolite_id: str, produced: set[str], consumed: set[str]) -> str:
    """Sign-only dead-end kind, as legacy candidate typing (bounds ignored)."""
    if metabolite_id in produced - consumed:
        return "product"
    if metabolite_id in consumed - produced:
        return "substrate"
    return "none"


def _pair_type(left_kind: str, right_kind: str) -> str:
    """A: product with substrate; B: two of one dead-end kind; C: otherwise."""
    if {left_kind, right_kind} == {"product", "substrate"}:
        return "A"
    if left_kind == right_kind != "none":
        return "B"
    return "C"


# Standalone API.
_DEFAULTS = {
    "greedy": {
        "max_additions": 500,
        "allowed_connections": [("c", "e"), ("c", "m")],
        "candidate_types": ["A", "B", "C"],
    },
    "deadends": {
        "max_additions": 1000,
        "allowed_connections": [("c", "e")],
        "candidate_types": ["A", "B"],
    },
    "milp": {"minimum_flux": 0.05, "penalties": {}, "max_additions": 100},
    "sink-milp": {
        "max_additions": 1000,
        "candidate_types": ["A", "B", "C"],
        "tradeoff_lambda": 0.01,
        "min_component_size": 4,
    },
}


def _as_mapping(model: Any) -> dict[str, Any]:
    if isinstance(model, dict):
        return model
    from cobra.io.dict import model_to_dict

    return model_to_dict(model)


def _transport_key(
    reaction: dict[str, Any],
) -> tuple[tuple[str, str], frozenset[str]] | None:
    """Return pair and capacities relative to lexicographic metabolite order."""
    metabolites = {
        key: value for key, value in reaction["metabolites"].items() if value
    }
    if len(metabolites) != 2:
        return None
    first, second = sorted(metabolites)
    if metabolites[first] * metabolites[second] >= 0:
        return None
    # Scaling does not matter: a two-metabolite transport is normalized to units.
    positive = f"{first}>{second}" if metabolites[first] < 0 else f"{second}>{first}"
    reverse = (
        f"{second}>{first}" if positive == f"{first}>{second}" else f"{first}>{second}"
    )
    directions = set()
    if float(reaction.get("upper_bound", 1000)) > 0:
        directions.add(positive)
    if float(reaction.get("lower_bound", 0)) < 0:
        directions.add(reverse)
    return (first, second), frozenset(directions)


def _covered_transport(model: Any, candidate: GapfillCandidate) -> bool:
    wanted = _transport_key(
        {
            "metabolites": candidate.metabolites,
            "lower_bound": candidate.lower_bound,
            "upper_bound": candidate.upper_bound,
        }
    )
    if wanted is None:
        return False
    for reaction in _as_mapping(model)["reactions"]:
        actual = _transport_key(reaction)
        if actual and actual[0] == wanted[0] and actual[1] >= wanted[1]:
            return True
    return False


def _metrics(model: Any) -> dict[str, int]:
    mapped = _as_mapping(model)
    produced, consumed = _produced_consumed(mapped)
    deadends = produced ^ consumed
    components = set(_components(mapped).values())
    return {
        "dead_ends": len(deadends),
        "components": len(components),
        "reactions": len(mapped["reactions"]),
    }


def _deadend_ids(model: Any) -> set[str]:
    produced, consumed = _produced_consumed(_as_mapping(model))
    return produced ^ consumed


def _transport_candidates(
    model: Any, allowed_connections: list[tuple[str, str]], candidate_types: list[str]
) -> list[GapfillCandidate]:
    mapped = _as_mapping(model)
    allowed = {tuple(sorted(pair)) for pair in allowed_connections}
    produced, consumed = _produced_consumed(mapped)
    buckets: dict[str, list[dict[str, Any]]] = {}
    for met in mapped["metabolites"]:
        buckets.setdefault(re.sub(r"[a-z]+$", "", met["id"]), []).append(met)
    result = []
    for base, metabolites in sorted(buckets.items()):
        ordered = sorted(metabolites, key=lambda item: item["id"])
        for index, left in enumerate(ordered):
            for right in ordered[index + 1 :]:
                compartments = tuple(
                    sorted(
                        (
                            left.get("compartment") or _suffix(left["id"]),
                            right.get("compartment") or _suffix(right["id"]),
                        )
                    )
                )
                if compartments not in allowed:
                    continue
                kind = _pair_type(
                    _metabolite_kind(left["id"], produced, consumed),
                    _metabolite_kind(right["id"], produced, consumed),
                )
                if kind not in candidate_types:
                    continue
                first, second = sorted((left["id"], right["id"]))
                reaction_id = re.sub(r"[^A-Za-z0-9_]", "_", f"GAPFILL_{first}_{second}")
                result.append(
                    GapfillCandidate(
                        reaction_id,
                        {first: -1.0, second: 1.0},
                        -1000.0,
                        1000.0,
                        annotation={"type": kind, "base": base},
                    )
                )
    return sorted(result, key=lambda candidate: candidate.id)


def _resolved_parameters(
    method: str, parameters: dict[str, Any] | None
) -> dict[str, Any]:
    if method not in _DEFAULTS:
        raise ValueError(f"unknown gapfill method: {method}")
    values = {**_DEFAULTS[method], **(parameters or {})}
    unsupported = {"allow_exchange", "allow_demand"} & set(values)
    if unsupported:
        raise ValueError(
            f"unsupported gapfill parameters: {', '.join(sorted(unsupported))}"
        )
    foreign = (
        {"allowed_connections", "candidate_types", "tradeoff_lambda"}
        | {"min_component_size"}
        if method == "milp"
        else {"universal_model", "objective", "minimum_flux", "penalties"}
        | (
            set()
            if method == "sink-milp"
            else {"tradeoff_lambda", "min_component_size"}
        )
    ) & set(values)
    if foreign:
        raise ValueError(
            f"parameters not supported by {method}: {', '.join(sorted(foreign))}"
        )
    if not isinstance(values.get("max_additions"), int) or values["max_additions"] <= 0:
        raise ValueError("max_additions must be positive")
    if method == "sink-milp":
        if "allowed_connections" not in values:
            raise ValueError("allowed_connections is required for sink-milp")
        lam = values["tradeoff_lambda"]
        # At lambda >= 1 a PTR costs at least the targets it covers: none selected.
        if (
            isinstance(lam, bool)
            or not isinstance(lam, (int, float))
            or not 0 < lam < 1
        ):
            raise ValueError("tradeoff_lambda must be between 0 and 1")
        size = values["min_component_size"]
        if isinstance(size, bool) or not isinstance(size, int) or size < 1:
            raise ValueError("min_component_size must be a positive integer")
    if method != "milp":
        values["allowed_connections"] = [
            tuple(pair) for pair in values["allowed_connections"]
        ]
        if not values["allowed_connections"]:
            raise ValueError(
                "allowed_connections must name at least one compartment pair"
            )
        if any(len(pair) != 2 for pair in values["allowed_connections"]):
            raise ValueError(
                "allowed_connections entries must contain two compartments"
            )
        if set(values["candidate_types"]) - {"A", "B", "C"}:
            raise ValueError("candidate_types may only contain A, B, and C")
    return values


class _TransportSearch:
    """Running dead-end, component and transport state for greedy scoring.

    A two-metabolite transport only changes the produced/consumed status of its
    own metabolites and merges at most two components, so a trial is scored in
    constant time instead of on a full model copy.
    """

    def __init__(self, mapped: dict[str, Any]) -> None:
        self.produced, self.consumed = _produced_consumed(mapped)
        self.sets = _UnionFind(met["id"] for met in mapped.get("metabolites", []))
        self.transports: dict[tuple[str, str], list[frozenset[str]]] = {}
        for reaction in mapped.get("reactions", []):
            ids = [mid for mid in reaction.get("metabolites", {}) if mid in self.sets]
            for metabolite_id in ids[1:]:
                self.sets.union(ids[0], metabolite_id)
            self._record_transport(reaction)

    def _record_transport(self, reaction: dict[str, Any]) -> None:
        key = _transport_key(reaction)
        if key:
            self.transports.setdefault(key[0], []).append(key[1])

    def dead_end_ids(self) -> set[str]:
        return self.produced ^ self.consumed

    def improvement(self, candidate: GapfillCandidate) -> tuple[int, int]:
        """Dead ends and components removed by adding ``candidate``."""
        dead_ends = 0
        for metabolite_id, coefficient in candidate.metabolites.items():
            produced = metabolite_id in self.produced
            consumed = metabolite_id in self.consumed
            dead_ends += produced != consumed
            if coefficient > 0:
                produced = True
            else:
                consumed = True
            dead_ends -= produced != consumed
        roots = {
            self.sets.find(mid) for mid in candidate.metabolites if mid in self.sets
        }
        return dead_ends, max(len(roots) - 1, 0)

    def covers(self, candidate: GapfillCandidate) -> bool:
        wanted = _transport_key(_candidate_reaction(candidate))
        return wanted is not None and any(
            present >= wanted[1] for present in self.transports.get(wanted[0], [])
        )

    def add(self, candidate: GapfillCandidate) -> None:
        for metabolite_id, coefficient in candidate.metabolites.items():
            (self.produced if coefficient > 0 else self.consumed).add(metabolite_id)
        ids = [mid for mid in candidate.metabolites if mid in self.sets]
        for metabolite_id in ids[1:]:
            self.sets.union(ids[0], metabolite_id)
        self._record_transport(_candidate_reaction(candidate))


def _candidate_reaction(candidate: GapfillCandidate) -> dict[str, Any]:
    return {
        "metabolites": candidate.metabolites,
        "lower_bound": candidate.lower_bound,
        "upper_bound": candidate.upper_bound,
    }


def _run_transport(
    model: Any, method: str, parameters: dict[str, Any]
) -> GapfillResult:
    result_model = _candidate_model_copy(model)
    mapped = _as_mapping(result_model)
    before = _metrics(mapped)
    candidates = _transport_candidates(
        mapped, parameters["allowed_connections"], parameters["candidate_types"]
    )
    known_compartments = {met.get("compartment") for met in mapped["metabolites"]}
    for pair in parameters["allowed_connections"]:
        if not set(pair) <= known_compartments:
            raise ValueError(f"unknown compartment pair: {pair}")
    search = _TransportSearch(mapped)
    coverage = {
        candidate.id: "already-present" if search.covers(candidate) else "available"
        for candidate in candidates
    }
    candidates = [
        candidate for candidate in candidates if coverage[candidate.id] == "available"
    ]
    existing_ids = {reaction["id"] for reaction in mapped["reactions"]}
    collisions = [
        candidate.id for candidate in candidates if candidate.id in existing_ids
    ]
    if collisions:
        return GapfillResult(
            result_model,
            [],
            coverage,
            "failed",
            f"reaction-ID collision: {collisions[0]}",
            {"strategy": method},
            method,
            parameters,
            before,
            before,
            "reaction-id-collision",
        )
    selected: list[GapfillCandidate] = []
    rank = {"A": 0, "B": 1, "C": 2}
    stop_reason = "no-improving-candidate"
    while len(selected) < parameters["max_additions"]:
        scored = []
        for candidate in candidates:
            if search.covers(candidate):
                coverage[candidate.id] = "already-present"
                continue
            improvement = search.improvement(candidate)
            if improvement != (0, 0):
                scored.append(
                    (
                        (
                            -improvement[0],
                            -improvement[1],
                            rank[candidate.annotation["type"]],
                            candidate.id,
                        ),
                        candidate,
                    )
                )
        if not scored:
            break
        _, best = min(scored)
        search.add(best)
        selected.append(best)
        coverage[best.id] = "selected"
        candidates.remove(best)
    for candidate in selected:
        _add_candidate(result_model, candidate)
    after = _metrics(result_model)
    remaining_improvement = False
    targetable = False
    dead_ends = search.dead_end_ids()
    for candidate in candidates:
        removed_dead_ends, merged = search.improvement(candidate)
        remaining_improvement |= removed_dead_ends > 0 or merged > 0
        targetable |= bool(set(candidate.metabolites) & dead_ends)
    at_limit = len(selected) == parameters["max_additions"]
    if at_limit:
        stop_reason = "max-additions"
    status = (
        "partial"
        if at_limit and (remaining_improvement if method == "greedy" else targetable)
        else "solved"
    )
    return GapfillResult(
        result_model,
        [candidate.id for candidate in selected],
        coverage,
        status,
        solver={"strategy": method},
        method=method,
        parameters=parameters,
        before_metrics=before,
        after_metrics=after,
        stop_reason=stop_reason,
    )


def _run_milp(model: Any, parameters: dict[str, Any]) -> GapfillResult:
    import cobra
    from cobra.flux_analysis.gapfilling import GapFiller

    from thg_protocol.io.models import load_model

    universal_path = Path(parameters["universal_model"])
    if not universal_path.is_file():
        raise ValueError("universal_model must be a readable model file")
    working = _candidate_model_copy(model)
    if not hasattr(working, "reactions"):
        raise ValueError("milp requires a COBRApy model")
    if parameters["objective"] not in working.reactions:
        raise ValueError(f"objective not found: {parameters['objective']}")
    universal = load_model(universal_path)
    original_objective = working.objective
    working.objective = parameters["objective"]
    try:
        before = _metrics(working)
        filler = GapFiller(
            working,
            universal=universal,
            lower_bound=parameters["minimum_flux"],
            penalties=parameters["penalties"],
            demand_reactions=False,
            exchange_reactions=False,
        )
        additions = filler.fill(iterations=1)[0]
        if len(additions) > parameters["max_additions"]:
            return GapfillResult(
                working,
                [],
                {},
                "failed",
                "max_additions exceeded",
                {"strategy": "milp"},
                "milp",
                parameters,
                before,
                before,
                "max-additions",
            )
        existing = {reaction.id for reaction in working.reactions}
        if any(reaction.id in existing for reaction in additions):
            return GapfillResult(
                working,
                [],
                {},
                "failed",
                "reaction-ID collision",
                {"strategy": "milp"},
                "milp",
                parameters,
                before,
                before,
                "reaction-id-collision",
            )
        working.add_reactions([reaction.copy() for reaction in additions])
        solution = working.optimize()
        status = (
            "solved"
            if solution.status == "optimal"
            and abs(solution.fluxes[parameters["objective"]])
            >= parameters["minimum_flux"]
            else "failed"
        )
        return GapfillResult(
            working,
            [reaction.id for reaction in additions],
            {reaction.id: "selected" for reaction in additions},
            status,
            None if status == "solved" else "configured objective is infeasible",
            {
                "strategy": "milp",
                "solver": str(working.solver),
                "cobra_version": cobra.__version__,
            },
            "milp",
            parameters,
            before,
            _metrics(working),
            "objective-feasible" if status == "solved" else "objective-infeasible",
        )
    finally:
        working.objective = original_objective


def gapfill_model(
    model: Any, *, method: str, parameters: dict[str, Any] | None = None
) -> GapfillResult:
    """Gap-fill a copied COBRApy or JSON model with one standalone method."""
    try:
        values = _resolved_parameters(method, dict(parameters or {}))
        if method == "sink-milp":
            from .ptr import run_sink_milp

            return run_sink_milp(model, values)
        return (
            _run_milp(model, values)
            if method == "milp"
            else _run_transport(model, method, values)
        )
    except Exception as error:
        return _error_result(model, method, parameters, error)


def _error_result(
    model: Any, method: str, parameters: dict[str, Any] | None, error: Exception
) -> GapfillResult:
    """A ``failed`` result for a validation or execution error."""
    return GapfillResult(
        _candidate_model_copy(model),
        [],
        {},
        "failed",
        str(error),
        {"strategy": method},
        method,
        dict(parameters or {}),
        stop_reason="validation-or-execution-error",
    )


def _json_parameters(value: Any) -> Any:
    """Normalize tuples and other small configuration values for JSON output."""
    if isinstance(value, dict):
        return {str(key): _json_parameters(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_parameters(item) for item in value]
    return value


def _reaction_payload(reaction: Any) -> dict[str, Any]:
    metabolites = getattr(reaction, "metabolites", None)
    if metabolites is None:
        metabolites = reaction.get("metabolites", {})
        lower = reaction.get("lower_bound", 0.0)
        upper = reaction.get("upper_bound", 1000.0)
        annotation = reaction.get("annotation", {})
        name = reaction.get("name", "")
    else:
        metabolites = {
            str(metabolite.id): float(coefficient)
            for metabolite, coefficient in metabolites.items()
        }
        lower = reaction.lower_bound
        upper = reaction.upper_bound
        annotation = dict(getattr(reaction, "annotation", {}) or {})
        name = getattr(reaction, "name", "") or ""
    reaction_id = reaction.id if hasattr(reaction, "id") else reaction["id"]
    return {
        "reaction_id": str(reaction_id),
        "metabolites": {str(key): float(value) for key, value in metabolites.items()},
        "bounds": {"lower": float(lower), "upper": float(upper)},
        "annotation": _json_parameters(annotation),
        "name": str(name),
    }


def generate_gapfill_plan(
    model: Any,
    *,
    method: str,
    parameters: dict[str, Any] | None = None,
    source_model_checksum: str | None = None,
    result: GapfillResult | None = None,
) -> dict[str, Any]:
    """Generate an auditable proposal without mutating ``model``.

    ``result`` is a gapfill already run on ``model`` (e.g. from workflow
    stages); without it the method runs here.
    """
    if result is None:
        result = gapfill_model(model, method=method, parameters=parameters)
    selected = set(result.selected)
    result_reactions = {
        str(reaction.id if hasattr(reaction, "id") else reaction["id"]): reaction
        for reaction in (
            result.model.reactions
            if hasattr(result.model, "reactions")
            else result.model.get("reactions", [])
        )
    }
    source_reactions = {
        str(reaction.id if hasattr(reaction, "id") else reaction["id"])
        for reaction in (
            model.reactions
            if hasattr(model, "reactions")
            else model.get("reactions", [])
        )
    }
    source_metabolites = {
        str(item.id if hasattr(item, "id") else item["id"]): item
        for item in (
            model.metabolites
            if hasattr(model, "metabolites")
            else model.get("metabolites", [])
        )
    }
    proposals = []
    for reaction_id in sorted(selected):
        reaction = result_reactions[reaction_id]
        payload = _reaction_payload(reaction)
        annotation = payload.pop("annotation", {})
        candidate_type = (
            annotation.get("type") if isinstance(annotation, dict) else None
        )
        proposal = {
            "schema_version": 1,
            "proposal_id": f"gapfill:{method}:{reaction_id}",
            "reaction_id": reaction_id,
            "method": method,
            "source": annotation.get("source", "thg_protocol.gapfill")
            if isinstance(annotation, dict)
            else "thg_protocol.gapfill",
            "metabolites": payload["metabolites"],
            "bounds": payload["bounds"],
            "candidate_type": candidate_type,
            "reason": result.stop_reason or "selected by configured method",
            "cost": None,
            "coverage_or_improvement": {
                "coverage": result.candidate_coverage.get(reaction_id)
            },
            "solver_evidence": dict(result.solver),
            "name": payload["name"],
            "source_reaction_id": reaction_id
            if reaction_id in source_reactions
            else None,
        }
        if method == "sink-milp" and isinstance(annotation, dict):
            proposal["phase"] = annotation.get("phase")
        if method != "milp":
            proposal["transport"] = {
                "source_metabolites": sorted(payload["metabolites"]),
                "source_compartments": {
                    metabolite_id: str(
                        getattr(source_metabolites[metabolite_id], "compartment", "")
                        if hasattr(source_metabolites[metabolite_id], "compartment")
                        else source_metabolites[metabolite_id].get("compartment", "")
                    )
                    for metabolite_id in sorted(payload["metabolites"])
                },
                "connection_rule": _json_parameters(
                    result.parameters.get("allowed_connections", [])
                ),
                "candidate_generation_algorithm": (
                    "putative transport: spanning-tree connectors and sink MILP"
                    if method == "sink-milp"
                    else "same-base cross-compartment transport"
                ),
            }
        proposals.append(proposal)
    return {
        "header": {
            "schema_version": 1,
            "source_model_checksum": source_model_checksum,
            "method": method,
            "parameters": _json_parameters(result.parameters),
            "implementation_version": 1,
            "proposal_count": len(proposals),
            "status": result.status,
            "failure": result.failure,
            "solver": _json_parameters(result.solver),
        },
        "proposals": proposals,
        "result": _json_parameters(result.as_dict()),
    }


def _plan_proposals(plan: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    proposals = plan.get("proposals", [])
    if not isinstance(proposals, list) or any(
        not isinstance(item, Mapping) for item in proposals
    ):
        raise ValueError("gapfill plan proposals must be a list of objects")
    return proposals


def validate_gapfill_plan(
    plan: Mapping[str, Any], model: Any, *, source_model_checksum: str | None = None
) -> tuple[Mapping[str, Any], ...]:
    """Validate proposal identity and the deliberately narrow mutation policy."""
    header = plan.get("header")
    if not isinstance(header, Mapping):
        raise ValueError("gapfill plan header is required")
    expected = header.get("source_model_checksum")
    if source_model_checksum is not None and expected != source_model_checksum:
        raise ValueError("gapfill plan source checksum does not match model")
    existing = {
        str(reaction.id if hasattr(reaction, "id") else reaction["id"])
        for reaction in (
            model.reactions
            if hasattr(model, "reactions")
            else model.get("reactions", [])
        )
    }
    metabolites = (
        {str(item.id) for item in model.metabolites}
        if hasattr(model, "metabolites")
        else {str(item["id"]) for item in model.get("metabolites", [])}
    )
    proposals = _plan_proposals(plan)
    ids: set[str] = set()
    reaction_ids: set[str] = set()
    for proposal in proposals:
        proposal_id = proposal.get("proposal_id")
        reaction_id = proposal.get("reaction_id")
        if not isinstance(proposal_id, str) or not proposal_id or proposal_id in ids:
            raise ValueError("gapfill plan proposal IDs must be unique and non-empty")
        if not isinstance(reaction_id, str) or not reaction_id:
            raise ValueError("gapfill plan reaction_id is required")
        if reaction_id in existing or reaction_id in reaction_ids:
            raise ValueError(f"reaction-ID collision: {reaction_id}")
        ids.add(proposal_id)
        reaction_ids.add(reaction_id)
        stoich = proposal.get("metabolites")
        if not isinstance(stoich, Mapping) or not stoich:
            raise ValueError(f"proposal {proposal_id} has no metabolites")
        missing = sorted(set(map(str, stoich)) - metabolites)
        if missing:
            raise ValueError(
                f"proposal {proposal_id} references unknown metabolites: {missing}"
            )
        if (
            proposal.get("gene_reaction_rule")
            or proposal.get("genes")
            or proposal.get("compartments")
        ):
            raise ValueError(
                f"proposal {proposal_id} introduces unsupported model objects"
            )
        bounds = proposal.get("bounds")
        if not isinstance(bounds, Mapping) or set(bounds) != {"lower", "upper"}:
            raise ValueError(f"proposal {proposal_id} has unsupported bounds")
        try:
            lower, upper = float(bounds["lower"]), float(bounds["upper"])
        except (TypeError, ValueError) as error:
            raise ValueError(
                f"proposal {proposal_id} has unsupported bounds"
            ) from error
        if not (-float("inf") < lower <= upper < float("inf")):
            raise ValueError(f"proposal {proposal_id} has unsupported bounds")
    return tuple(proposals)


def apply_gapfill_plan(
    model: Any, plan: Mapping[str, Any], *, source_model_checksum: str | None = None
) -> tuple[Any, list[dict[str, Any]]]:
    """Apply every validated proposal to a private copy and return a ledger."""
    proposals = validate_gapfill_plan(
        plan, model, source_model_checksum=source_model_checksum
    )
    result = _candidate_model_copy(model)
    ledger: list[dict[str, Any]] = []
    for proposal in proposals:
        bounds = proposal["bounds"]
        candidate = GapfillCandidate(
            str(proposal["reaction_id"]),
            {str(key): float(value) for key, value in proposal["metabolites"].items()},
            float(bounds["lower"]),
            float(bounds["upper"]),
            source=str(proposal.get("source", "gapfill-plan")),
            annotation={
                "gapfill_proposal_id": str(proposal["proposal_id"]),
                "gapfill_method": str(proposal.get("method", "unknown")),
                "gapfill_source_checksum": source_model_checksum,
            },
        )
        _add_candidate(result, candidate)
        ledger.append(
            {
                "schema_version": 1,
                "proposal_id": proposal["proposal_id"],
                "reaction_id": candidate.id,
                "operation": "add-reaction",
                "status": "applied",
                "source_model_checksum": source_model_checksum,
            }
        )
    return result, ledger
