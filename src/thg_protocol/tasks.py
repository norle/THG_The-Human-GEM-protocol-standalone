"""Non-mutating, versioned metabolic task execution."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class MetabolicTask:
    id: str
    version: str = "1"
    uptake: Mapping[str, tuple[float, float]] = field(default_factory=dict)
    secretion: Mapping[str, tuple[float, float]] = field(default_factory=dict)
    temporary_reactions: tuple[Any, ...] = ()
    bounds: Mapping[str, tuple[float, float]] = field(default_factory=dict)
    objective: str | None = None
    expected: bool = True
    group: str = "core"
    identity: str | None = None
    solver: str | None = None

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> MetabolicTask:
        def bounds(value: object) -> dict[str, tuple[float, float]]:
            if not isinstance(value, Mapping):
                return {}
            return {
                str(key): (float(item[0]), float(item[1]))
                for key, item in value.items()
                if isinstance(item, (list, tuple)) and len(item) == 2
            }

        temporary = payload.get("temporary_reactions", [])
        if not isinstance(temporary, list):
            raise ValueError("temporary_reactions must be a list")
        return cls(
            id=str(payload["id"]),
            version=str(payload.get("version", "1")),
            uptake=bounds(payload.get("uptake")),
            secretion=bounds(payload.get("secretion")),
            temporary_reactions=tuple(
                dict(item) for item in temporary if isinstance(item, Mapping)
            ),
            bounds=bounds(payload.get("bounds")),
            objective=payload.get("objective")
            if isinstance(payload.get("objective"), str)
            else None,
            expected=bool(payload.get("expected", True)),
            group=str(payload.get("group", "core")),
            identity=payload.get("identity")
            if isinstance(payload.get("identity"), str)
            else None,
            solver=payload.get("solver")
            if isinstance(payload.get("solver"), str)
            else None,
        )

    def to_dict(self) -> dict[str, object]:
        temporary = []
        for reaction in self.temporary_reactions:
            if isinstance(reaction, Mapping):
                temporary.append(dict(reaction))
                continue
            metabolites = getattr(reaction, "metabolites", {})
            temporary.append(
                {
                    "id": str(reaction.id),
                    "name": str(getattr(reaction, "name", "") or ""),
                    "lower_bound": float(reaction.lower_bound),
                    "upper_bound": float(reaction.upper_bound),
                    "stoichiometry": {
                        str(metabolite.id): float(coefficient)
                        for metabolite, coefficient in metabolites.items()
                    },
                    "gene_reaction_rule": str(
                        getattr(reaction, "gene_reaction_rule", "") or ""
                    ),
                }
            )
        return {
            "id": self.id,
            "version": self.version,
            "uptake": dict(self.uptake),
            "secretion": dict(self.secretion),
            "temporary_reactions": temporary,
            "bounds": dict(self.bounds),
            "objective": self.objective,
            "expected": self.expected,
            "group": self.group,
            "identity": self.identity,
            "solver": self.solver,
        }


@dataclass(frozen=True)
class TaskSuite:
    id: str
    version: str
    tasks: tuple[MetabolicTask, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "version": self.version,
            "tasks": [task.to_dict() for task in self.tasks],
        }

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> TaskSuite:
        raw_tasks = payload.get("tasks", [])
        if not isinstance(raw_tasks, list):
            raise ValueError("task suite 'tasks' must be a list")
        return cls(
            id=str(payload["id"]),
            version=str(payload.get("version", "1")),
            tasks=tuple(
                MetabolicTask.from_mapping(item)
                for item in raw_tasks
                if isinstance(item, Mapping)
            ),
        )


def load_task_suite(path: str | Path) -> TaskSuite:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("task suite must be a JSON object")
    return TaskSuite.from_mapping(payload)


def run_task(model: Any, task: MetabolicTask) -> dict[str, object]:
    """Execute one task on a copy and classify solver/infrastructure failures."""
    working = model.copy()
    try:
        for reaction_id, bounds in {
            **task.uptake,
            **task.secretion,
            **task.bounds,
        }.items():
            working.reactions.get_by_id(reaction_id).bounds = tuple(bounds)
        for reaction in task.temporary_reactions:
            if isinstance(reaction, Mapping):
                from cobra import Reaction

                temporary = Reaction(
                    str(reaction["id"]),
                    name=str(reaction.get("name", "")),
                    lower_bound=float(reaction.get("lower_bound", -1000.0)),
                    upper_bound=float(reaction.get("upper_bound", 1000.0)),
                )
                stoichiometry = reaction.get("stoichiometry", {})
                if not isinstance(stoichiometry, Mapping):
                    raise ValueError(
                        "temporary reaction stoichiometry must be an object"
                    )
                temporary.add_metabolites(
                    {
                        working.metabolites.get_by_id(str(metabolite_id)): float(
                            coefficient
                        )
                        for metabolite_id, coefficient in stoichiometry.items()
                    }
                )
                temporary.gene_reaction_rule = str(
                    reaction.get("gene_reaction_rule", "")
                )
                working.add_reactions([temporary])
            else:
                working.add_reactions([reaction.copy()])
        if task.objective:
            working.objective = task.objective
        solution = working.optimize()
        status = str(solution.status)
        passed = status == "optimal" and float(solution.objective_value or 0.0) > 1e-9
        return {
            "id": task.id,
            "version": task.version,
            "group": task.group,
            "status": status,
            "passed": passed == task.expected,
            "biological_pass": passed,
            "objective": float(solution.objective_value or 0.0),
            "expected": task.expected,
            "diagnostics": {"identity": task.identity},
            "solver": task.solver,
        }
    except Exception as error:
        return {
            "id": task.id,
            "version": task.version,
            "group": task.group,
            "status": "infrastructure-error",
            "passed": False,
            "expected": task.expected,
            "solver": task.solver,
            "diagnostics": {"error_type": type(error).__name__, "message": str(error)},
        }


def run_tasks(
    model: Any, tasks: tuple[MetabolicTask, ...] | list[MetabolicTask]
) -> dict[str, object]:
    results = [run_task(model, task) for task in tasks]
    return {
        "schema_version": 1,
        "tasks": results,
        "passed": all(bool(item["passed"]) for item in results),
    }


def run_task_suite(model: Any, suite: TaskSuite) -> dict[str, object]:
    report = run_tasks(model, suite.tasks)
    report.update({"suite": suite.id, "suite_version": suite.version})
    return report


__all__ = [
    "MetabolicTask",
    "TaskSuite",
    "load_task_suite",
    "run_task",
    "run_tasks",
    "run_task_suite",
]
