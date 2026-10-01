"""Import RAVEN metabolic task tables into the THG task contract.

Parsing follows RAVEN's ``parseTaskList.m`` and name matching follows
``checkTasks.m`` (commit ``800362e71b9d04ae2e2a16960b9d19aff346d37e``):

* Rows whose first cell is non-empty (normally ``#``) and empty rows are
  skipped. The first remaining row is the header. A row with an ``ID`` starts
  a task; following rows with an empty ``ID`` add constraints to it.
  ``DESCRIPTION``, ``SHOULD FAIL``, ``PRINT FLUX``, and ``COMMENTS`` are read
  from the task's first row.
* ``IN``/``OUT`` hold ``;``-separated ``name[comp]`` metabolites sharing the
  row's bounds (defaults ``IN LB 0``, ``IN UB 1000``, ``OUT LB 0``,
  ``OUT UB 1000``). ``ALLMETS`` and ``ALLMETSIN[comp]`` expand to ``[0, UB]``
  for every matching model metabolite without an explicit constraint on the
  same side.
* ``EQU`` equations become temporary reactions ``TEMPORARY_<n>`` (defaults
  ``EQU LB -1000`` for ``<=>``, ``0`` for ``=>``; ``EQU UB 1000``).
* ``CHANGED RXN`` holds ``;``-separated reaction IDs sharing ``CHANGED LB`` and
  ``CHANGED UB``, which have no default.
* ``name[comp]`` is matched case-insensitively against model metabolite names
  and compartment IDs. A mapping file may override metabolites, translate
  compartment labels, and rename ``CHANGED RXN`` reaction IDs.

Every default is written explicitly into the resulting tasks. Unresolved or
ambiguous names, malformed values, and contradictory constraints make the
task invalid; each problem names the file, row, column, original text, and
candidate matches. Nothing is guessed or dropped.

Departures from RAVEN, recorded per task in ``metadata.import_notes``:

* ``SHOULD FAIL`` is true for ``1``/``true`` and false for empty, ``0``, or
  ``false`` (case-insensitive); other values are rejected. RAVEN treats any
  non-empty cell, including ``0``, as true.
* Repeated constraints on one metabolite or reaction are intersected; RAVEN
  raises an error for metabolites and lets the last reaction bound win.
* An ``IN LB`` on a metabolite that is also an output is kept as a
  requirement (the output side is closed); RAVEN drops it.
* ``EQU`` cannot introduce metabolites that are not in the model.
* A task ID used by several tasks is made unique as ``<ID>-row<row>``.
"""

from __future__ import annotations

import csv
import difflib
import hashlib
import json
import math
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from thg_protocol.tasks import (
    MetabolicTask,
    TaskSuite,
    load_task_suite,
    save_task_suite,
)

DEFAULT_BOUNDS = {
    "IN LB": 0.0,
    "IN UB": 1000.0,
    "OUT LB": 0.0,
    "OUT UB": 1000.0,
    "EQU UB": 1000.0,
}
REVERSIBLE_EQU_LB = -1000.0
IRREVERSIBLE_EQU_LB = 0.0
RAVEN_COLUMNS = (
    "ID",
    "DESCRIPTION",
    "IN",
    "IN LB",
    "IN UB",
    "OUT",
    "OUT LB",
    "OUT UB",
    "EQU",
    "EQU LB",
    "EQU UB",
    "CHANGED RXN",
    "CHANGED LB",
    "CHANGED UB",
    "SHOULD FAIL",
    "PRINT FLUX",
    "COMMENTS",
)
TABLE_SUFFIXES = (".txt", ".tsv", ".csv")
_MAPPING_KEYS = frozenset({"metabolites", "compartments", "reactions", "metadata"})
_METABOLITE = re.compile(r"^(?P<name>.*)\[(?P<comp>[^\[\]]+)\]$")
_COEFFICIENT = re.compile(
    r"^(?P<value>(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?)\s+(?P<rest>.+)$"
)


@dataclass(frozen=True)
class TaskMapping:
    """Name overrides for importing a RAVEN table against one model."""

    metabolites: Mapping[str, str] = field(default_factory=dict)
    compartments: Mapping[str, str] = field(default_factory=dict)
    reactions: Mapping[str, str] = field(default_factory=dict)
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in ("metabolites", "compartments", "reactions"):
            value = getattr(self, name)
            if not isinstance(value, Mapping) or not all(
                isinstance(key, str) and isinstance(item, str) and key and item
                for key, item in value.items()
            ):
                raise ValueError(f"task mapping {name} must map strings to strings")
            folded: dict[str, str] = {}
            for key, item in value.items():
                lookup = key.strip() if name == "reactions" else key.strip().upper()
                if lookup in folded and folded[lookup] != item:
                    raise ValueError(
                        f"task mapping {name} has conflicting entries for {key!r}"
                    )
                folded[lookup] = item
            object.__setattr__(self, name, dict(value))
            object.__setattr__(self, f"_{name}", folded)
        if not isinstance(self.metadata, Mapping):
            raise ValueError("task mapping metadata must be an object")

    def metabolite(self, text: str) -> str | None:
        return self._metabolites.get(text.strip().upper())  # type: ignore[attr-defined]

    def compartment(self, label: str) -> str:
        return self._compartments.get(label.strip().upper(), label.strip())  # type: ignore[attr-defined]

    def reaction(self, reaction_id: str) -> str:
        return self._reactions.get(reaction_id.strip(), reaction_id.strip())  # type: ignore[attr-defined]


def load_task_mapping(path: str | Path) -> TaskMapping:
    """Load a JSON mapping of ``metabolites``, ``compartments``, ``reactions``."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("task mapping must be a JSON object")
    unknown = sorted(set(payload) - _MAPPING_KEYS)
    if unknown:
        raise ValueError(f"task mapping has unknown fields: {', '.join(unknown)}")
    return TaskMapping(
        metabolites=payload.get("metabolites", {}),
        compartments=payload.get("compartments", {}),
        reactions=payload.get("reactions", {}),
        metadata=payload.get("metadata", {}),
    )


@dataclass(frozen=True)
class SourceRow:
    row: int
    cells: tuple[tuple[str, str | None], ...]

    def get(self, column: str) -> str | None:
        for name, value in self.cells:
            if name == column:
                return value
        return None

    def to_dict(self, file: str) -> dict[str, object]:
        return {
            "file": file,
            "row": self.row,
            "columns": [[name, value] for name, value in self.cells],
        }


def read_raven_rows(path: str | Path) -> list[SourceRow]:
    """Read the header and data rows of a tab-delimited RAVEN task table."""
    source = Path(path)
    if source.suffix.lower() in {".xlsx", ".xls"}:
        raise ValueError(
            f"{source}: Excel task tables are not supported; "
            "export the TASKS sheet as tab-delimited text"
        )
    with source.open(encoding="utf-8-sig", newline="") as handle:
        lines = list(csv.reader(handle, delimiter="\t"))
    header: list[str] | None = None
    rows: list[SourceRow] = []
    for number, cells in enumerate(lines, start=1):
        if not any(cell.strip() for cell in cells) or (cells and cells[0].strip()):
            continue
        if header is None:
            header = [cell.strip() for cell in cells]
            if "ID" not in header:
                raise ValueError(f"{source}: the header row has no ID column")
            continue
        values = []
        for index, name in enumerate(header):
            if not name:
                continue
            cell = cells[index].strip() if index < len(cells) else ""
            values.append((name, cell or None))
        rows.append(SourceRow(number, tuple(values)))
    if header is None:
        raise ValueError(f"{source}: no header row found")
    return rows


@dataclass
class _Draft:
    raven_id: str
    rows: list[SourceRow]
    problems: list[dict[str, object]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class RavenImport:
    """A suite imported from a RAVEN table, with every import problem."""

    suite: TaskSuite
    problems: tuple[Mapping[str, object], ...]

    @property
    def resolved(self) -> TaskSuite:
        """The suite without invalid tasks; omitted tasks are listed in metadata."""
        kept = tuple(task for task in self.suite.tasks if not task.problems)
        omitted = [
            {"id": task.id, "problems": [dict(item) for item in task.problems]}
            for task in self.suite.tasks
            if task.problems
        ]
        metadata = dict(self.suite.metadata)
        if omitted:
            metadata["omitted_tasks"] = omitted
        return TaskSuite(self.suite.id, self.suite.version, kept, metadata)


class _Resolver:
    def __init__(self, model: Any, mapping: TaskMapping, file: str) -> None:
        self.model = model
        self.mapping = mapping
        self.file = file
        self.compartments = {str(key).upper(): str(key) for key in model.compartments}
        for metabolite in model.metabolites:
            self.compartments.setdefault(
                str(metabolite.compartment).upper(), str(metabolite.compartment)
            )
        self.by_name: dict[tuple[str, str], list[str]] = {}
        self.names: dict[str, list[tuple[str, str]]] = {}
        for metabolite in model.metabolites:
            name = str(metabolite.name or "")
            comp = str(metabolite.compartment or "")
            self.by_name.setdefault((name.upper(), comp.upper()), []).append(
                metabolite.id
            )
            self.names.setdefault(name.upper(), []).append((metabolite.id, comp))

    def problem(
        self,
        draft: _Draft | None,
        row: SourceRow,
        column: str,
        text: str | None,
        message: str,
        candidates: list[str] | None = None,
    ) -> dict[str, object]:
        item: dict[str, object] = {
            "task": None if draft is None else draft.raven_id,
            "file": self.file,
            "row": row.row,
            "column": column,
            "text": text,
            "message": f"{self.file} row {row.row} {column}"
            + ("" if text is None else f" {text!r}")
            + f": {message}",
            "candidates": candidates or [],
        }
        if draft is not None:
            draft.problems.append(item)
        return item

    def compartment(self, label: str) -> str | None:
        return self.compartments.get(self.mapping.compartment(label).upper())

    def wildcard(self, text: str) -> tuple[list[str], str | None] | None:
        """Expand ALLMETS / ALLMETSIN[comp]; ``None`` if ``text`` is neither."""
        upper = text.upper()
        if upper == "ALLMETS":
            return [item.id for item in self.model.metabolites], None
        if not (upper.startswith("ALLMETSIN[") and upper.endswith("]")):
            return None
        label = text[len("ALLMETSIN[") : -1]
        comp = self.compartment(label)
        if comp is None:
            return [], f"compartment {label!r} is not in the model"
        return [
            item.id for item in self.model.metabolites if item.compartment == comp
        ], None

    def metabolite(self, text: str) -> tuple[str | None, str, list[str]]:
        """Resolve ``name[comp]`` to a metabolite ID, or explain why not."""
        override = self.mapping.metabolite(text)
        if override is not None:
            if override in self.model.metabolites:
                return override, "", []
            return None, f"mapped metabolite {override!r} is not in the model", []
        match = _METABOLITE.match(text)
        if match is None:
            return None, "expected a metabolite as name[compartment]", []
        name, label = match.group("name").strip(), match.group("comp")
        comp = self.compartment(label)
        if comp is None:
            return None, f"compartment {label!r} is not in the model", []
        found = self.by_name.get((name.upper(), comp.upper()), [])
        if len(found) == 1:
            return found[0], "", []
        if found:
            return None, f"ambiguous: {len(found)} model metabolites match", found
        candidates = [
            f"{metabolite_id} ({name}[{other}])"
            for metabolite_id, other in self.names.get(name.upper(), [])
        ]
        in_compartment = sorted(
            {key[0] for key in self.by_name if key[1] == comp.upper()}
        )
        for close in difflib.get_close_matches(name.upper(), in_compartment, n=3):
            candidates.extend(
                f"{metabolite_id} ({close}[{comp}])"
                for metabolite_id in self.by_name[(close, comp.upper())]
            )
        return None, "no model metabolite matches", candidates


def _number(
    resolver: _Resolver, draft: _Draft, row: SourceRow, column: str
) -> float | None:
    text = row.get(column)
    if text is None:
        if column in DEFAULT_BOUNDS:
            return DEFAULT_BOUNDS[column]
        resolver.problem(draft, row, column, text, "a bound is required")
        return None
    try:
        value = float(text)
    except ValueError:
        value = math.nan
    if not math.isfinite(value):
        resolver.problem(draft, row, column, text, "expected a finite number")
        return None
    return value


def _split(text: str) -> list[str]:
    return [item.strip() for item in text.split(";") if item.strip()]


def _should_fail(resolver: _Resolver, draft: _Draft, row: SourceRow) -> bool:
    text = row.get("SHOULD FAIL")
    if text is None:
        return False
    value = text.strip().lower()
    if value in {"1", "true"}:
        return True
    if value in {"0", "false"}:
        draft.notes.append(
            f"SHOULD FAIL {text!r} read as false; RAVEN treats any non-empty "
            "cell as true"
        )
        return False
    resolver.problem(
        draft, row, "SHOULD FAIL", text, "expected empty, 0, 1, false, or true"
    )
    return False


def _intersect(
    resolver: _Resolver,
    draft: _Draft,
    side: str,
    declared: dict[str, list[tuple[tuple[float, float], SourceRow, str]]],
) -> dict[str, tuple[float, float]]:
    result = {}
    for key, entries in declared.items():
        lower = max(pair[0] for pair, _, _ in entries)
        upper = min(pair[1] for pair, _, _ in entries)
        if len(entries) > 1:
            if lower > upper:
                detail = "; ".join(
                    f"row {row.row} {text!r} {list(pair)}"
                    for pair, row, text in entries
                )
                _, row, text = entries[-1]
                resolver.problem(
                    draft,
                    row,
                    side,
                    text,
                    f"contradictory constraints on {key!r}: {detail}",
                )
                continue
            draft.notes.append(
                f"repeated {side} constraints on {key!r} intersected to "
                f"[{lower}, {upper}]"
            )
        result[key] = (lower, upper)
    return result


def _side(
    resolver: _Resolver, draft: _Draft, side: str
) -> dict[str, tuple[float, float]]:
    explicit: dict[str, list[tuple[tuple[float, float], SourceRow, str]]] = {}
    wildcards: dict[str, list[tuple[tuple[float, float], SourceRow, str]]] = {}
    for row in draft.rows:
        cell = row.get(side)
        if cell is None:
            continue
        lower = _number(resolver, draft, row, f"{side} LB")
        upper = _number(resolver, draft, row, f"{side} UB")
        if lower is None or upper is None:
            continue
        if lower > upper:
            resolver.problem(
                draft, row, side, cell, f"reversed bounds [{lower}, {upper}]"
            )
            continue
        for text in _split(cell):
            expanded = resolver.wildcard(text)
            if expanded is not None:
                metabolites, message = expanded
                if message:
                    resolver.problem(draft, row, side, text, message)
                # RAVEN uses only the upper bound: flux is allowed, never required.
                for metabolite_id in metabolites:
                    wildcards.setdefault(metabolite_id, []).append(
                        ((0.0, upper), row, text)
                    )
                continue
            metabolite_id, message, candidates = resolver.metabolite(text)
            if metabolite_id is None:
                resolver.problem(draft, row, side, text, message, candidates)
                continue
            explicit.setdefault(metabolite_id, []).append(((lower, upper), row, text))
    result = _intersect(resolver, draft, side, explicit)
    for metabolite_id, entries in wildcards.items():
        if metabolite_id in explicit:
            continue
        lower = max(pair[0] for pair, _, _ in entries)
        upper = min(pair[1] for pair, _, _ in entries)
        result[metabolite_id] = (lower, upper)
    return result


def _equation(
    resolver: _Resolver, draft: _Draft, row: SourceRow, text: str, index: int
) -> dict[str, object] | None:
    if " <=> " in f" {text} ":
        arrow, lower_default = "<=>", REVERSIBLE_EQU_LB
    elif " => " in f" {text} ":
        arrow, lower_default = "=>", IRREVERSIBLE_EQU_LB
    else:
        resolver.problem(draft, row, "EQU", text, "expected '<=>' or '=>'")
        return None
    left, _, right = f" {text} ".partition(f" {arrow} ")
    coefficients: dict[str, float] = {}
    ok = True
    for sign, half in ((-1.0, left), (1.0, right)):
        for term in (item.strip() for item in half.strip().split(" + ")):
            if not term:
                continue
            match = _COEFFICIENT.match(term)
            value, name = (
                (float(match.group("value")), match.group("rest").strip())
                if match
                else (1.0, term)
            )
            metabolite_id, message, candidates = resolver.metabolite(name)
            if metabolite_id is None:
                if message == "no model metabolite matches":
                    message += " (RAVEN would add it; THG tasks cannot)"
                resolver.problem(draft, row, "EQU", name, message, candidates)
                ok = False
                continue
            coefficients[metabolite_id] = (
                coefficients.get(metabolite_id, 0.0) + sign * value
            )
    coefficients = {key: value for key, value in coefficients.items() if value != 0.0}
    if not ok:
        return None
    if not coefficients:
        resolver.problem(draft, row, "EQU", text, "the equation has no net change")
        return None
    lower = (
        lower_default
        if row.get("EQU LB") is None
        else _number(resolver, draft, row, "EQU LB")
    )
    upper = _number(resolver, draft, row, "EQU UB")
    if lower is None or upper is None:
        return None
    if lower > upper:
        resolver.problem(draft, row, "EQU", text, f"reversed bounds [{lower}, {upper}]")
        return None
    return {
        "id": f"TEMPORARY_{index}",
        "name": text,
        "lower_bound": lower,
        "upper_bound": upper,
        "stoichiometry": coefficients,
    }


def _changed(
    resolver: _Resolver, draft: _Draft, temporary: set[str]
) -> dict[str, tuple[float, float]]:
    declared: dict[str, list[tuple[tuple[float, float], SourceRow, str]]] = {}
    for row in draft.rows:
        cell = row.get("CHANGED RXN")
        if cell is None:
            continue
        lower = _number(resolver, draft, row, "CHANGED LB")
        upper = _number(resolver, draft, row, "CHANGED UB")
        if lower is None or upper is None:
            continue
        if lower > upper:
            resolver.problem(
                draft, row, "CHANGED RXN", cell, f"reversed bounds [{lower}, {upper}]"
            )
            continue
        for text in _split(cell):
            reaction_id = resolver.mapping.reaction(text)
            if (
                reaction_id not in resolver.model.reactions
                and reaction_id not in temporary
            ):
                candidates = difflib.get_close_matches(
                    reaction_id, [item.id for item in resolver.model.reactions], n=3
                )
                resolver.problem(
                    draft,
                    row,
                    "CHANGED RXN",
                    text,
                    f"reaction {reaction_id!r} is not in the model",
                    candidates,
                )
                continue
            declared.setdefault(reaction_id, []).append(((lower, upper), row, text))
    return _intersect(resolver, draft, "CHANGED RXN", declared)


def _build_task(resolver: _Resolver, draft: _Draft, task_id: str) -> MetabolicTask:
    first = draft.rows[0]
    expected = not _should_fail(resolver, draft, first)
    inputs = _side(resolver, draft, "IN")
    outputs = _side(resolver, draft, "OUT")
    temporary = []
    for row in draft.rows:
        cell = row.get("EQU")
        if cell is not None:
            reaction = _equation(resolver, draft, row, cell, len(temporary) + 1)
            # Keep numbering stable even when an equation is invalid.
            temporary.append(reaction)
    temporary_ids = {f"TEMPORARY_{index}" for index in range(1, len(temporary) + 1)}
    bounds = _changed(resolver, draft, temporary_ids)
    for metabolite_id, pair in inputs.items():
        produced = outputs.get(metabolite_id)
        if produced is None:
            continue
        if pair[0] > 0 and produced[0] > 0:
            resolver.problem(
                draft,
                first,
                "IN",
                None,
                f"{metabolite_id!r} has nonzero IN LB and OUT LB",
            )
        elif pair[0] > 0:
            draft.notes.append(
                f"IN LB {pair[0]} on {metabolite_id!r}, also an output, is kept as "
                "a requirement; RAVEN drops it"
            )
    metadata: dict[str, object] = {
        "raven_id": draft.raven_id,
        "source_rows": [row.to_dict(resolver.file) for row in draft.rows],
    }
    if draft.notes:
        metadata["import_notes"] = list(draft.notes)
    description = first.get("DESCRIPTION")
    if not draft.problems:
        try:
            return MetabolicTask(
                task_id,
                inputs=inputs,
                outputs=outputs,
                temporary_reactions=tuple(item for item in temporary if item),
                bounds=bounds,
                expected=expected,
                description=description,
                metadata=metadata,
            )
        except ValueError as error:
            resolver.problem(draft, first, "ID", draft.raven_id, str(error))
    return MetabolicTask(
        task_id,
        expected=expected,
        description=description,
        metadata=metadata,
        problems=tuple(draft.problems),
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def import_raven_tasks(
    path: str | Path,
    model: Any,
    *,
    mapping: TaskMapping | str | Path | None = None,
    suite_id: str | None = None,
) -> RavenImport:
    """Import a RAVEN task table against ``model``.

    Tasks with problems stay in the suite and run as ``invalid``; use
    :attr:`RavenImport.resolved` for the resolved tasks only. Rows that do not
    belong to any task raise ``ValueError``.
    """
    source = Path(path)
    if mapping is None:
        mapping = TaskMapping()
    elif not isinstance(mapping, TaskMapping):
        mapping = load_task_mapping(mapping)
    resolver = _Resolver(model, mapping, source.name)
    drafts: list[_Draft] = []
    for row in read_raven_rows(source):
        raven_id = row.get("ID")
        if raven_id is not None:
            drafts.append(_Draft(raven_id, [row]))
        elif drafts:
            drafts[-1].rows.append(row)
        else:
            problem = resolver.problem(
                None, row, "ID", None, "constraint row before the first task"
            )
            raise ValueError(str(problem["message"]))
    counts: dict[str, int] = {}
    for draft in drafts:
        counts[draft.raven_id] = counts.get(draft.raven_id, 0) + 1
    tasks = []
    for draft in drafts:
        task_id = draft.raven_id
        if counts[task_id] > 1:
            task_id = f"{task_id}-row{draft.rows[0].row}"
            draft.notes.append(
                f"task ID {draft.raven_id!r} is used by {counts[draft.raven_id]} "
                f"tasks; renamed to {task_id!r}"
            )
        tasks.append(_build_task(resolver, draft, task_id))
    metadata: dict[str, object] = {
        "source": {"file": source.name, "format": "raven", "sha256": _sha256(source)},
        "model": str(getattr(model, "id", "") or ""),
    }
    if mapping.metabolites or mapping.compartments or mapping.reactions:
        metadata["mapping"] = {
            "metabolites": dict(mapping.metabolites),
            "compartments": dict(mapping.compartments),
            "reactions": dict(mapping.reactions),
            **({"metadata": dict(mapping.metadata)} if mapping.metadata else {}),
        }
    suite = TaskSuite(
        suite_id or source.stem,
        _sha256(source)[:16],
        tuple(tasks),
        metadata,
    )
    problems = tuple(item for task in tasks for item in task.problems)
    return RavenImport(suite, problems)


def convert_raven_tasks(
    path: str | Path,
    model: Any,
    output: str | Path,
    *,
    mapping: TaskMapping | str | Path | None = None,
    suite_id: str | None = None,
    resolved_only: bool = False,
) -> RavenImport:
    """Import a RAVEN table and write it as a JSON task suite.

    Refuses to write while problems remain, unless ``resolved_only`` writes the
    resolved tasks and lists the omitted ones in ``metadata.omitted_tasks``.
    """
    result = import_raven_tasks(path, model, mapping=mapping, suite_id=suite_id)
    if result.problems and not resolved_only:
        lines = "\n".join(f"- {item['message']}" for item in result.problems)
        raise ValueError(
            f"{len(result.problems)} unresolved problems in {Path(path).name}:\n{lines}"
        )
    save_task_suite(result.resolved, output)
    return result


def is_raven_table(path: str | Path) -> bool:
    return Path(path).suffix.lower() in TABLE_SUFFIXES


def task_input_version(path: str | Path) -> str:
    """The suite version a task input has, without importing a RAVEN table."""
    if is_raven_table(path):
        return _sha256(Path(path))[:16]
    return load_task_suite(path).version


def load_task_input(
    path: str | Path,
    model: Any,
    *,
    mapping: TaskMapping | str | Path | None = None,
) -> TaskSuite:
    """Load a JSON task suite, or import a RAVEN table against ``model``."""
    if is_raven_table(path):
        return import_raven_tasks(path, model, mapping=mapping).suite
    if mapping is not None:
        raise ValueError("a task mapping applies only to RAVEN task tables")
    return load_task_suite(path)


__all__ = [
    "RavenImport",
    "TaskMapping",
    "convert_raven_tasks",
    "import_raven_tasks",
    "is_raven_table",
    "load_task_input",
    "load_task_mapping",
    "read_raven_rows",
    "task_input_version",
]
