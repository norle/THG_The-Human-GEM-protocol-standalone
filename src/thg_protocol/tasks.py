"""Versioned metabolic task contract and non-mutating evaluation.

Task contract (``TASK_SCHEMA_VERSION``), following RAVEN task semantics:

* ``inputs`` and ``outputs`` map model metabolite IDs to ``[lower, upper]``
  bounds on the allowed net consumption and net production. Each is evaluated
  as a temporary reaction: a source ``-> m`` named ``TASK_IN_<m>`` and a sink
  ``m ->`` named ``TASK_OUT_<m>``. Existing exchange reactions are not used.
* A metabolite listed in both may be consumed or produced. A nonzero lower
  bound on one side is a requirement and closes the other side, so a source
  and sink cannot satisfy it by cycling; nonzero lower bounds on both sides
  are an invalid definition.
* ``temporary_reactions`` add reactions over existing model metabolite IDs
  and must state ``lower_bound`` and ``upper_bound``; there is no default, so
  importers write their source format's defaults explicitly.
* ``bounds`` maps model or temporary reaction IDs (RAVEN ``CHANGED RXN``) to
  signed ``[lower, upper]`` flux bounds. Repeated constraints on one reaction,
  including a temporary reaction's own bounds, are intersected (greatest
  lower bound, least upper bound). An empty intersection is an invalid
  definition.
* ``medium`` is ``"closed"`` (default: every model boundary reaction is set to
  ``[0, 0]``, so only inputs and outputs connect the model to the outside) or
  ``"model"`` (the input model's boundary bounds are retained). Explicit
  ``bounds`` are applied afterwards and may reopen boundaries.
* Without ``objective`` a task is a feasibility task: the inherited objective
  is replaced by a constant zero objective and the task succeeds when the
  constraints are feasible. With ``objective`` (``reaction``, ``direction``
  ``"max"``/``"min"``, finite ``threshold``; a JSON-only extension) the task
  succeeds when the solve is optimal and the value is at least (``max``) or at
  most (``min``) the threshold, within ``OBJECTIVE_TOLERANCE``.
* ``expected`` is ``False`` for tasks that should fail. Only a biological
  failure (infeasible, or optimal but short of the threshold) satisfies it;
  invalid definitions and solver/infrastructure errors never pass.
* ``metadata`` is an optional JSON object preserved verbatim. Imported legacy
  rows are stored as ordered ``source_rows`` entries of ``file``, ``row``, and
  ``columns`` (ordered ``[name, value]`` pairs, missing cells as ``null``).
"""

from __future__ import annotations

import copy
import json
import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

TASK_SCHEMA_VERSION = 2
REPORT_SCHEMA_VERSION = 2
OBJECTIVE_TOLERANCE = 1e-6
MEDIUM_MODES = ("closed", "model")
OBJECTIVE_DIRECTIONS = ("max", "min")
SOURCE_PREFIX = "TASK_IN_"
SINK_PREFIX = "TASK_OUT_"

_TASK_KEYS = frozenset(
    {
        "id",
        "version",
        "description",
        "inputs",
        "outputs",
        "bounds",
        "temporary_reactions",
        "objective",
        "expected",
        "group",
        "identity",
        "solver",
        "medium",
        "metadata",
    }
)
_SUITE_KEYS = frozenset({"id", "version", "schema_version", "tasks", "metadata"})
_TEMPORARY_KEYS = frozenset(
    {
        "id",
        "name",
        "lower_bound",
        "upper_bound",
        "stoichiometry",
        "gene_reaction_rule",
    }
)
_OBJECTIVE_KEYS = frozenset({"reaction", "direction", "threshold"})
_SOURCE_ROW_KEYS = frozenset({"file", "row", "columns"})


def _number(value: object, where: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{where} must be a number, got {value!r}")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{where} must be finite, got {value!r}")
    return result


def _text(value: object, where: str, *, optional: bool = False) -> str | None:
    if value is None and optional:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{where} must be a non-empty string")
    return value


def _check_keys(payload: Mapping[str, object], allowed: frozenset[str], where: str):
    unknown = sorted(str(key) for key in payload if key not in allowed)
    if unknown:
        raise ValueError(f"{where} has unknown fields: {', '.join(unknown)}")


def _bound_pair(value: object, where: str) -> tuple[float, float]:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError(f"{where} must be a [lower, upper] pair")
    lower = _number(value[0], f"{where} lower bound")
    upper = _number(value[1], f"{where} upper bound")
    if lower > upper:
        raise ValueError(f"{where} has reversed bounds [{lower}, {upper}]")
    return lower, upper


def _constraint_map(
    value: object, where: str, kind: str = "reaction"
) -> dict[str, tuple[float, float]]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ValueError(f"{where} must be an object of {kind} bounds")
    return {
        _text(key, f"{where} {kind} ID"): _bound_pair(item, f"{where}[{key!r}]")
        for key, item in value.items()
    }


def _temporary_reaction(value: object, where: str) -> dict[str, object]:
    if not isinstance(value, Mapping):
        # cobra.Reaction (or a compatible object) built in Python.
        if not hasattr(value, "id") or not hasattr(value, "metabolites"):
            raise ValueError(f"{where} must be an object")
        value = {
            "id": str(value.id),
            "name": str(getattr(value, "name", "") or ""),
            "lower_bound": float(value.lower_bound),
            "upper_bound": float(value.upper_bound),
            "stoichiometry": {
                str(metabolite.id): float(coefficient)
                for metabolite, coefficient in value.metabolites.items()
            },
            "gene_reaction_rule": str(getattr(value, "gene_reaction_rule", "") or ""),
        }
    _check_keys(value, _TEMPORARY_KEYS, where)
    reaction_id = _text(value.get("id"), f"{where} id")
    where = f"temporary reaction {reaction_id!r}"
    missing = [key for key in ("lower_bound", "upper_bound") if key not in value]
    if missing:
        raise ValueError(f"{where} is missing {' and '.join(missing)}")
    lower, upper = _bound_pair([value["lower_bound"], value["upper_bound"]], where)
    stoichiometry = value.get("stoichiometry")
    if not isinstance(stoichiometry, Mapping) or not stoichiometry:
        raise ValueError(f"{where} stoichiometry must be a non-empty object")
    coefficients: dict[str, float] = {}
    for metabolite_id, coefficient in stoichiometry.items():
        number = _number(coefficient, f"{where} coefficient for {metabolite_id!r}")
        if number == 0.0:
            raise ValueError(f"{where} has a zero coefficient for {metabolite_id!r}")
        coefficients[_text(metabolite_id, f"{where} metabolite ID")] = number
    name = value.get("name", "")
    rule = value.get("gene_reaction_rule", "")
    if not isinstance(name, str) or not isinstance(rule, str):
        raise ValueError(f"{where} name and gene_reaction_rule must be strings")
    return {
        "id": reaction_id,
        "name": name,
        "lower_bound": lower,
        "upper_bound": upper,
        "stoichiometry": coefficients,
        "gene_reaction_rule": rule,
    }


def _metadata(value: object, where: str) -> dict[str, object]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ValueError(f"{where} metadata must be an object")
    try:
        result = json.loads(json.dumps(value, allow_nan=False))
    except (TypeError, ValueError) as error:
        raise ValueError(f"{where} metadata must be JSON-serializable") from error
    rows = result.get("source_rows")
    if rows is None:
        return result
    if not isinstance(rows, list):
        raise ValueError(f"{where} metadata source_rows must be a list")
    for index, row in enumerate(rows):
        label = f"{where} metadata source_rows[{index}]"
        if not isinstance(row, dict):
            raise ValueError(f"{label} must be an object")
        _check_keys(row, _SOURCE_ROW_KEYS, label)
        _text(row.get("file"), f"{label} file")
        line = row.get("row")
        if isinstance(line, bool) or not isinstance(line, int) or line < 1:
            raise ValueError(f"{label} row must be a positive integer")
        columns = row.get("columns")
        if not isinstance(columns, list):
            raise ValueError(f"{label} columns must be a list of [name, value]")
        for column in columns:
            if (
                not isinstance(column, list)
                or len(column) != 2
                or not isinstance(column[0], str)
                or not (column[1] is None or isinstance(column[1], str))
            ):
                raise ValueError(
                    f"{label} columns must be [name, value] pairs of a string "
                    "name and a string or null value"
                )
    return result


@dataclass(frozen=True)
class TaskObjective:
    reaction: str
    direction: str
    threshold: float

    def __post_init__(self) -> None:
        _text(self.reaction, "objective reaction")
        if self.direction not in OBJECTIVE_DIRECTIONS:
            raise ValueError(
                f"objective direction must be one of {OBJECTIVE_DIRECTIONS}, "
                f"got {self.direction!r}"
            )
        object.__setattr__(
            self, "threshold", _number(self.threshold, "objective threshold")
        )

    @classmethod
    def from_mapping(cls, payload: object) -> TaskObjective:
        if not isinstance(payload, Mapping):
            raise ValueError(
                "objective must be an object with reaction, direction, and threshold"
            )
        _check_keys(payload, _OBJECTIVE_KEYS, "objective")
        missing = sorted(_OBJECTIVE_KEYS - set(payload))
        if missing:
            raise ValueError(f"objective is missing: {', '.join(missing)}")
        return cls(
            reaction=payload["reaction"],  # type: ignore[arg-type]
            direction=payload["direction"],  # type: ignore[arg-type]
            threshold=payload["threshold"],  # type: ignore[arg-type]
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "reaction": self.reaction,
            "direction": self.direction,
            "threshold": self.threshold,
        }

    def satisfied_by(self, value: float) -> bool:
        if self.direction == "max":
            return value >= self.threshold - OBJECTIVE_TOLERANCE
        return value <= self.threshold + OBJECTIVE_TOLERANCE


@dataclass(frozen=True)
class MetabolicTask:
    id: str
    version: str = "1"
    inputs: Mapping[str, tuple[float, float]] = field(default_factory=dict)
    outputs: Mapping[str, tuple[float, float]] = field(default_factory=dict)
    temporary_reactions: tuple[Any, ...] = ()
    bounds: Mapping[str, tuple[float, float]] = field(default_factory=dict)
    objective: TaskObjective | None = None
    expected: bool = True
    description: str | None = None
    group: str = "core"
    identity: str | None = None
    solver: str | None = None
    medium: str = "closed"
    metadata: Mapping[str, object] = field(default_factory=dict)
    # Import problems (unresolved names and similar) that make the task invalid.
    # They are reported at run time and never serialized; see save_task_suite.
    problems: tuple[Mapping[str, object], ...] = ()

    def __post_init__(self) -> None:
        _text(self.id, "task id")
        where = f"task {self.id!r}"
        for name in ("inputs", "outputs"):
            object.__setattr__(
                self,
                name,
                _constraint_map(getattr(self, name), f"{where} {name}", "metabolite"),
            )
        object.__setattr__(
            self, "bounds", _constraint_map(self.bounds, f"{where} bounds")
        )
        temporary = tuple(
            _temporary_reaction(item, f"{where} temporary_reactions[{index}]")
            for index, item in enumerate(self.temporary_reactions)
        )
        ids = [str(item["id"]) for item in temporary]
        if len(ids) != len(set(ids)):
            raise ValueError(f"{where} has duplicate temporary reaction IDs")
        generated = set(self.exchange_bounds())
        clashes = sorted(generated & set(ids))
        if clashes:
            raise ValueError(
                f"{where} temporary reaction IDs clash with input/output "
                f"reactions: {', '.join(clashes)}"
            )
        object.__setattr__(self, "temporary_reactions", temporary)
        if self.objective is not None and not isinstance(self.objective, TaskObjective):
            object.__setattr__(
                self, "objective", TaskObjective.from_mapping(self.objective)
            )
        if not isinstance(self.expected, bool):
            raise ValueError(f"{where} expected must be true or false")
        if self.medium not in MEDIUM_MODES:
            raise ValueError(f"{where} medium must be one of {MEDIUM_MODES}")
        _text(self.version, f"{where} version")
        if self.description is not None and not isinstance(self.description, str):
            raise ValueError(f"{where} description must be a string")
        _text(self.group, f"{where} group")
        _text(self.identity, f"{where} identity", optional=True)
        _text(self.solver, f"{where} solver", optional=True)
        object.__setattr__(self, "metadata", _metadata(self.metadata, where))
        object.__setattr__(
            self, "problems", tuple(dict(item) for item in self.problems)
        )
        self.reaction_bounds()

    @property
    def kind(self) -> str:
        return "feasibility" if self.objective is None else "objective"

    def exchange_bounds(self) -> dict[str, tuple[str, int, tuple[float, float]]]:
        """Source and sink reactions for inputs and outputs.

        Returns ``{reaction ID: (metabolite ID, coefficient, bounds)}``. For a
        metabolite that is both input and output, a nonzero lower bound on one
        side closes the other side, as RAVEN's balance bounds do.
        """
        result: dict[str, tuple[str, int, tuple[float, float]]] = {}
        for metabolite_id, pair in self.inputs.items():
            if metabolite_id in self.outputs:
                produced = self.outputs[metabolite_id]
                if pair[0] > 0 and produced[0] > 0:
                    raise ValueError(
                        f"task {self.id!r} requires {metabolite_id!r} as both input "
                        f"{list(pair)} and output {list(produced)}; nonzero lower "
                        "bounds on both sides are not allowed"
                    )
                if produced[0] > 0:
                    pair = (0.0, 0.0)
            result[f"{SOURCE_PREFIX}{metabolite_id}"] = (metabolite_id, 1, pair)
        for metabolite_id, pair in self.outputs.items():
            consumed = self.inputs.get(metabolite_id)
            if consumed is not None and consumed[0] > 0:
                pair = (0.0, 0.0)
            result[f"{SINK_PREFIX}{metabolite_id}"] = (metabolite_id, -1, pair)
        return result

    def reaction_bounds(self) -> dict[str, tuple[float, float]]:
        """Intersect every explicit constraint per reaction, in first-seen order."""
        sources: dict[str, list[tuple[str, tuple[float, float]]]] = {}
        for reaction_id, (_, _, pair) in self.exchange_bounds().items():
            group = "inputs" if reaction_id.startswith(SOURCE_PREFIX) else "outputs"
            sources.setdefault(reaction_id, []).append((group, pair))
        for item in self.temporary_reactions:
            sources.setdefault(str(item["id"]), []).append(
                (
                    "temporary_reactions",
                    (float(item["lower_bound"]), float(item["upper_bound"])),
                )
            )
        for reaction_id, pair in self.bounds.items():
            sources.setdefault(reaction_id, []).append(("bounds", pair))
        result: dict[str, tuple[float, float]] = {}
        for reaction_id, declared in sources.items():
            lower = max(pair[0] for _, pair in declared)
            upper = min(pair[1] for _, pair in declared)
            if lower > upper:
                detail = "; ".join(f"{name} {list(pair)}" for name, pair in declared)
                raise ValueError(
                    f"task {self.id!r} has contradictory bounds for "
                    f"{reaction_id!r}: {detail}"
                )
            result[reaction_id] = (lower, upper)
        return result

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> MetabolicTask:
        if not isinstance(payload, Mapping):
            raise ValueError("task must be an object")
        _check_keys(payload, _TASK_KEYS, f"task {payload.get('id')!r}")
        if "id" not in payload:
            raise ValueError("task is missing 'id'")
        temporary = payload.get("temporary_reactions", [])
        if not isinstance(temporary, list):
            raise ValueError("temporary_reactions must be a list")
        version = payload.get("version", "1")
        if isinstance(version, int) and not isinstance(version, bool):
            version = str(version)
        objective = payload.get("objective")
        return cls(
            id=payload["id"],  # type: ignore[arg-type]
            version=version,  # type: ignore[arg-type]
            inputs=payload.get("inputs"),  # type: ignore[arg-type]
            outputs=payload.get("outputs"),  # type: ignore[arg-type]
            temporary_reactions=tuple(temporary),
            bounds=payload.get("bounds"),  # type: ignore[arg-type]
            objective=None
            if objective is None
            else TaskObjective.from_mapping(objective),
            expected=payload.get("expected", True),  # type: ignore[arg-type]
            description=payload.get("description"),  # type: ignore[arg-type]
            group=payload.get("group", "core"),  # type: ignore[arg-type]
            identity=payload.get("identity"),  # type: ignore[arg-type]
            solver=payload.get("solver"),  # type: ignore[arg-type]
            medium=payload.get("medium", "closed"),  # type: ignore[arg-type]
            metadata=payload.get("metadata"),  # type: ignore[arg-type]
        )

    def to_dict(self) -> dict[str, object]:
        result: dict[str, object] = {"id": self.id, "version": self.version}
        if self.description is not None:
            result["description"] = self.description
        for name in ("inputs", "outputs", "bounds"):
            result[name] = {
                key: list(pair) for key, pair in getattr(self, name).items()
            }
        result.update(
            {
                "temporary_reactions": copy.deepcopy(list(self.temporary_reactions)),
                "objective": None
                if self.objective is None
                else self.objective.to_dict(),
                "expected": self.expected,
                "group": self.group,
                "identity": self.identity,
                "solver": self.solver,
                "medium": self.medium,
            }
        )
        if self.metadata:
            result["metadata"] = copy.deepcopy(dict(self.metadata))
        return result


@dataclass(frozen=True)
class TaskSuite:
    id: str
    version: str
    tasks: tuple[MetabolicTask, ...]
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _text(self.id, "task suite id")
        _text(self.version, "task suite version")
        ids = [task.id for task in self.tasks]
        duplicates = sorted({item for item in ids if ids.count(item) > 1})
        if duplicates:
            raise ValueError(f"duplicate task IDs: {', '.join(duplicates)}")
        object.__setattr__(self, "tasks", tuple(self.tasks))
        object.__setattr__(
            self, "metadata", _metadata(self.metadata, f"task suite {self.id!r}")
        )

    def to_dict(self) -> dict[str, object]:
        result: dict[str, object] = {
            "schema_version": TASK_SCHEMA_VERSION,
            "id": self.id,
            "version": self.version,
            "tasks": [task.to_dict() for task in self.tasks],
        }
        if self.metadata:
            result["metadata"] = copy.deepcopy(dict(self.metadata))
        return result

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> TaskSuite:
        _check_keys(payload, _SUITE_KEYS, "task suite")
        schema = payload.get("schema_version", TASK_SCHEMA_VERSION)
        if schema != TASK_SCHEMA_VERSION:
            raise ValueError(
                f"unsupported task schema_version {schema!r}; "
                f"expected {TASK_SCHEMA_VERSION}"
            )
        raw_tasks = payload.get("tasks", [])
        if not isinstance(raw_tasks, list):
            raise ValueError("task suite 'tasks' must be a list")
        if "id" not in payload:
            raise ValueError("task suite is missing 'id'")
        version = payload.get("version", "1")
        if isinstance(version, int) and not isinstance(version, bool):
            version = str(version)
        return cls(
            id=payload["id"],  # type: ignore[arg-type]
            version=version,  # type: ignore[arg-type]
            tasks=tuple(MetabolicTask.from_mapping(item) for item in raw_tasks),
            metadata=payload.get("metadata"),  # type: ignore[arg-type]
        )


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key {key!r} in task suite")
        result[key] = value
    return result


def load_task_suite(path: str | Path) -> TaskSuite:
    payload = json.loads(
        Path(path).read_text(encoding="utf-8"),
        object_pairs_hook=_reject_duplicate_keys,
    )
    if not isinstance(payload, Mapping):
        raise ValueError("task suite must be a JSON object")
    return TaskSuite.from_mapping(payload)


def save_task_suite(suite: TaskSuite, path: str | Path) -> Path:
    """Write ``suite`` as JSON; tasks with unresolved import problems are refused."""
    unresolved = [task.id for task in suite.tasks if task.problems]
    if unresolved:
        raise ValueError(
            "cannot save tasks with unresolved import problems: "
            + ", ".join(unresolved)
        )
    target = Path(path)
    target.write_text(
        json.dumps(suite.to_dict(), indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return target


def _definition_problems(model: Any, task: MetabolicTask) -> list[str]:
    problems = [str(item.get("message", item)) for item in task.problems]
    exchanges = task.exchange_bounds()
    for reaction_id, (metabolite_id, _, _) in exchanges.items():
        if metabolite_id not in model.metabolites:
            group = "input" if reaction_id.startswith(SOURCE_PREFIX) else "output"
            problems.append(f"unknown {group} metabolite {metabolite_id!r}")
    temporary_ids = {str(item["id"]) for item in task.temporary_reactions}
    temporary_ids.update(exchanges)
    for reaction_id in sorted(temporary_ids):
        if reaction_id in model.reactions:
            problems.append(
                f"temporary reaction {reaction_id!r} already exists in the model"
            )
    for reaction in task.temporary_reactions:
        for metabolite_id in reaction["stoichiometry"]:
            if metabolite_id not in model.metabolites:
                problems.append(
                    f"unknown metabolite {metabolite_id!r} in temporary reaction "
                    f"{reaction['id']!r}"
                )
    referenced = list(task.reaction_bounds())
    if task.objective is not None:
        referenced.append(task.objective.reaction)
    for reaction_id in referenced:
        if reaction_id not in temporary_ids and reaction_id not in model.reactions:
            problems.append(f"unknown reaction {reaction_id!r}")
    return problems


def _result(task: MetabolicTask, **values: object) -> dict[str, object]:
    result: dict[str, object] = {
        "id": task.id,
        "version": task.version,
        "group": task.group,
        "kind": task.kind,
        "identity": task.identity,
        "solver": task.solver,
        "expected_outcome": "success" if task.expected else "failure",
        "actual_outcome": None,
        "solver_status": None,
        "objective_value": None,
        "diagnostics": {},
    }
    result.update(values)
    result["passed"] = result["status"] == "passed"
    return result


def _evaluate(working: Any, task: MetabolicTask) -> dict[str, object]:
    """Evaluate one task inside a model context so every change is reverted."""
    problems = _definition_problems(working, task)
    if problems:
        diagnostics: dict[str, object] = {"problems": problems}
        if task.problems:
            diagnostics["import_problems"] = copy.deepcopy(list(task.problems))
        return _result(task, status="invalid", diagnostics=diagnostics)
    from cobra import Reaction
    from optlang.symbolics import Zero

    with working:
        if task.medium == "closed":
            for reaction in working.boundary:
                reaction.bounds = (0.0, 0.0)
        added = []
        for reaction_id, exchange in task.exchange_bounds().items():
            metabolite_id, coefficient, pair = exchange
            reaction = Reaction(reaction_id, lower_bound=pair[0], upper_bound=pair[1])
            reaction.add_metabolites(
                {working.metabolites.get_by_id(metabolite_id): coefficient}
            )
            added.append(reaction)
        for spec in task.temporary_reactions:
            reaction = Reaction(
                str(spec["id"]),
                name=str(spec["name"]),
                lower_bound=float(spec["lower_bound"]),
                upper_bound=float(spec["upper_bound"]),
            )
            reaction.add_metabolites(
                {
                    working.metabolites.get_by_id(metabolite_id): coefficient
                    for metabolite_id, coefficient in spec["stoichiometry"].items()
                }
            )
            if spec["gene_reaction_rule"]:
                reaction.gene_reaction_rule = str(spec["gene_reaction_rule"])
            added.append(reaction)
        working.add_reactions(added)
        for reaction_id, pair in task.reaction_bounds().items():
            working.reactions.get_by_id(reaction_id).bounds = pair
        if task.objective is None:
            working.objective = working.problem.Objective(Zero, direction="max")
        else:
            working.objective = {
                working.reactions.get_by_id(task.objective.reaction): 1.0
            }
            working.objective_direction = task.objective.direction
        working.solver.optimize()
        solver_status = str(working.solver.status)
        value = (
            float(working.solver.objective.value)
            if solver_status == "optimal" and task.objective is not None
            else None
        )

    infeasible = {"infeasible"}
    if task.objective is None:
        # A zero objective cannot be unbounded, so this status is infeasible.
        infeasible.add("infeasible_or_unbounded")
    diagnostics = {}
    if task.objective is not None:
        diagnostics["objective"] = task.objective.to_dict()
        diagnostics["tolerance"] = OBJECTIVE_TOLERANCE
    if solver_status == "optimal":
        success = value is None or task.objective.satisfied_by(value)  # type: ignore[union-attr]
        actual = "success" if success else "failure"
    elif solver_status in infeasible:
        actual = "failure"
    else:
        diagnostics["message"] = (
            f"solver status {solver_status!r} is not a biological outcome"
        )
        return _result(
            task,
            status="error",
            solver_status=solver_status,
            diagnostics=diagnostics,
        )
    expected = "success" if task.expected else "failure"
    return _result(
        task,
        status="passed" if actual == expected else "failed",
        actual_outcome=actual,
        solver_status=solver_status,
        objective_value=value,
        diagnostics=diagnostics,
    )


def _run_on(working: Any, task: MetabolicTask) -> dict[str, object]:
    try:
        return _evaluate(working, task)
    except Exception as error:
        return _result(
            task,
            status="error",
            diagnostics={"error_type": type(error).__name__, "message": str(error)},
        )


def _solver_model(model: Any, task: MetabolicTask, cache: dict[str | None, Any]) -> Any:
    if task.solver not in cache:
        working = model.copy()
        if task.solver is not None:
            working.solver = task.solver
        cache[task.solver] = working
    return cache[task.solver]


def run_task(model: Any, task: MetabolicTask) -> dict[str, object]:
    """Execute one task on a copy of ``model``; the input is never modified."""
    return run_tasks(model, (task,))["tasks"][0]  # type: ignore[index]


def run_tasks(
    model: Any, tasks: tuple[MetabolicTask, ...] | list[MetabolicTask]
) -> dict[str, object]:
    """Execute tasks serially, in order, on per-solver copies of ``model``."""
    cache: dict[str | None, Any] = {}
    results = []
    for task in tasks:
        try:
            working = _solver_model(model, task, cache)
        except Exception as error:
            results.append(
                _result(
                    task,
                    status="error",
                    diagnostics={
                        "error_type": type(error).__name__,
                        "message": str(error),
                    },
                )
            )
            continue
        results.append(_run_on(working, task))
    counts = {
        status: sum(item["status"] == status for item in results)
        for status in ("passed", "failed", "invalid", "error")
    }
    passed = all(bool(item["passed"]) for item in results)
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "task_schema_version": TASK_SCHEMA_VERSION,
        "tolerance": OBJECTIVE_TOLERANCE,
        "status": "passed" if passed else "failed",
        "passed": passed,
        "counts": counts,
        "tasks": results,
    }


def run_task_suite(model: Any, suite: TaskSuite) -> dict[str, object]:
    report = run_tasks(model, suite.tasks)
    report.update({"suite": suite.id, "suite_version": suite.version})
    return report


__all__ = [
    "OBJECTIVE_TOLERANCE",
    "TASK_SCHEMA_VERSION",
    "MetabolicTask",
    "TaskObjective",
    "TaskSuite",
    "load_task_suite",
    "save_task_suite",
    "run_task",
    "run_tasks",
    "run_task_suite",
]
