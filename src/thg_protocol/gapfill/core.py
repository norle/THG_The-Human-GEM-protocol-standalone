"""Small, deterministic gapfill operations for JSON model mappings."""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any

__all__ = [
    "generate_candidates",
    "run_phase1",
    "run_phase2",
    "run_phase3",
    "run_pipeline",
]


def _components(model: dict[str, Any]) -> dict[str, int]:
    parent: dict[str, str] = {
        met["id"]: met["id"] for met in model.get("metabolites", [])
    }

    def find(item: str) -> str:
        while parent[item] != item:
            parent[item] = parent[parent[item]]
            item = parent[item]
        return item

    def union(left: str, right: str) -> None:
        left, right = find(left), find(right)
        if left != right:
            parent[right] = left

    for reaction in model.get("reactions", []):
        ids = [mid for mid in reaction.get("metabolites", {}) if mid in parent]
        for metabolite_id in ids[1:]:
            union(ids[0], metabolite_id)
    roots: dict[str, int] = {}
    result: dict[str, int] = {}
    for metabolite_id in parent:
        root = find(metabolite_id)
        roots.setdefault(root, len(roots) + 1)
        result[metabolite_id] = roots[root]
    return result


def _suffix(metabolite_id: str) -> str:
    return (
        re.search(r"[a-z]+$", metabolite_id).group(0)
        if re.search(r"[a-z]+$", metabolite_id)
        else ""
    )


def generate_candidates(
    model: dict[str, Any],
    allowed_connections: list[tuple[str, str]] | None = None,
) -> list[dict[str, Any]]:
    """Generate deterministic transport candidates from a JSON model.

    Candidate records contain metabolite IDs, component IDs, dead-end types,
    and a stable ``type`` (A/B/C) compatible with the legacy CSV workflow.
    """
    component = _components(model)
    produced: set[str] = set()
    consumed: set[str] = set()
    for reaction in model.get("reactions", []):
        for metabolite_id, coefficient in reaction.get("metabolites", {}).items():
            (produced if coefficient > 0 else consumed).add(metabolite_id)
    met_type = {
        met["id"]: (
            "product"
            if met["id"] in produced - consumed
            else "substrate"
            if met["id"] in consumed - produced
            else "none"
        )
        for met in model.get("metabolites", [])
    }
    allowed = {(a, b) for a, b in allowed_connections} if allowed_connections else None
    buckets: dict[str, list[str]] = {}
    for metabolite in model.get("metabolites", []):
        base = re.sub(r"[a-z]+$", "", metabolite["id"])
        buckets.setdefault(base, []).append(metabolite["id"])
    candidates: list[dict[str, Any]] = []
    for base, metabolite_ids in sorted(buckets.items()):
        for index, first in enumerate(metabolite_ids):
            for second in metabolite_ids[index + 1 :]:
                first_suffix, second_suffix = _suffix(first), _suffix(second)
                if component.get(first) == component.get(second):
                    continue
                if (
                    allowed
                    and (first_suffix, second_suffix) not in allowed
                    and (second_suffix, first_suffix) not in allowed
                ):
                    continue
                first_type, second_type = met_type[first], met_type[second]
                kind = (
                    "A"
                    if {first_type, second_type} == {"product", "substrate"}
                    else "B"
                    if first_type == second_type and first_type != "none"
                    else "C"
                )
                candidates.append(
                    {
                        "met1": first,
                        "met2": second,
                        "base": base,
                        "suffix1": first_suffix,
                        "suffix2": second_suffix,
                        "component1": component[first],
                        "component2": component[second],
                        "type": kind,
                        "met1_type": first_type,
                        "met2_type": second_type,
                    }
                )
    return candidates


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = (
        list(rows[0])
        if rows
        else [
            "met1",
            "met2",
            "base",
            "suffix1",
            "suffix2",
            "component1",
            "component2",
            "type",
        ]
    )
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    return path


def run_phase1(model: dict[str, Any], output_dir: str | Path) -> dict[str, Any]:
    """Generate candidate, dead-end, and component CSV files."""
    destination = Path(output_dir)
    candidates = generate_candidates(model)
    candidates_path = _write_csv(destination / "candidates_all.csv", candidates)
    produced, consumed = set(), set()
    for reaction in model.get("reactions", []):
        for mid, coefficient in reaction.get("metabolites", {}).items():
            (produced if coefficient > 0 else consumed).add(mid)
    deadends = [
        {
            "met_id": met["id"],
            "type": "product" if met["id"] in produced - consumed else "substrate",
            "component": "",
            "compartment": met.get("compartment", ""),
        }
        for met in model.get("metabolites", [])
        if met["id"] in (produced ^ consumed)
    ]
    deadends_path = _write_csv(destination / "deadends_summary.csv", deadends)
    components = _components(model)
    sizes: dict[int, int] = {}
    for component in components.values():
        sizes[component] = sizes.get(component, 0) + 1
    component_path = _write_csv(
        destination / "components_summary.csv",
        [
            {"component_id": key, "num_nodes": value}
            for key, value in sorted(sizes.items())
        ],
    )
    return {
        "candidates": candidates_path,
        "deadends": deadends_path,
        "components": component_path,
        "count": len(candidates),
    }


def _read_candidates(path: str | Path) -> list[dict[str, Any]]:
    with Path(path).open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        for key in ("component1", "component2"):
            if key in row:
                row[key] = int(row[key])
    return rows


def _add_transport(
    model: dict[str, Any], candidate: dict[str, Any], prefix: str, index: int
) -> str | None:
    ids = {met["id"] for met in model.get("metabolites", [])}
    if candidate["met1"] not in ids or candidate["met2"] not in ids:
        return None
    reaction_id = (
        f"{prefix}_{candidate.get('base', '')}_{candidate.get('suffix1', '')}_"
        f"{candidate.get('suffix2', '')}_{index}"
    )
    reaction_id = re.sub(r"[^A-Za-z0-9_]", "_", reaction_id)
    model.setdefault("reactions", []).append(
        {
            "id": reaction_id,
            "name": "gapfill transport",
            "metabolites": {candidate["met1"]: -1.0, candidate["met2"]: 1.0},
            "lower_bound": -1000.0,
            "upper_bound": 1000.0,
            "annotation": {"thg_protocol": "gapfill"},
        }
    )
    return reaction_id


def run_phase2(
    model: dict[str, Any],
    candidates: str | Path | list[dict[str, Any]],
    output_dir: str | Path,
) -> dict[str, Any]:
    """Select a deterministic minimum component connector set."""
    rows = (
        _read_candidates(candidates)
        if isinstance(candidates, (str, Path))
        else list(candidates)
    )
    components = sorted(
        {row["component1"] for row in rows} | {row["component2"] for row in rows}
    )
    parent = {component: component for component in components}

    def find(component: int) -> int:
        while parent[component] != component:
            parent[component] = parent[parent[component]]
            component = parent[component]
        return component

    selected: list[dict[str, Any]] = []
    rank = {"A": 0, "B": 1, "C": 2}
    for row in sorted(
        rows,
        key=lambda item: (
            rank.get(item.get("type", "C"), 2),
            item.get("base", ""),
            item["met1"],
            item["met2"],
        ),
    ):
        left, right = find(row["component1"]), find(row["component2"])
        if left == right:
            continue
        parent[right] = left
        selected.append(row)
    created = []
    for index, row in enumerate(selected):
        reaction_id = _add_transport(model, row, "TRANS_MIN", index)
        if reaction_id:
            created.append({**row, "reaction_id": reaction_id})
    csv_path = _write_csv(Path(output_dir) / "selected_minimal_connectors.csv", created)
    return {"model": model, "selected": created, "output": csv_path}


def run_phase3(
    model: dict[str, Any],
    candidates: str | Path | list[dict[str, Any]],
    output_dir: str | Path,
    max_additions: int = 500,
) -> dict[str, Any]:
    """Greedily add candidates that connect currently unmatched dead ends."""
    rows = (
        _read_candidates(candidates)
        if isinstance(candidates, (str, Path))
        else list(candidates)
    )
    selected: list[dict[str, Any]] = []
    remaining = list(rows)
    for index in range(max_additions):
        produced, consumed = set(), set()
        for reaction in model.get("reactions", []):
            for mid, coefficient in reaction.get("metabolites", {}).items():
                (produced if coefficient > 0 else consumed).add(mid)
        deadends = produced ^ consumed
        best = next(
            (
                row
                for row in remaining
                if row["met1"] in deadends or row["met2"] in deadends
            ),
            None,
        )
        if best is None:
            break
        reaction_id = _add_transport(model, best, "PH3_TRANS", index)
        remaining.remove(best)
        if reaction_id:
            selected.append({**best, "reaction_id": reaction_id})
    csv_path = _write_csv(Path(output_dir) / "selected_phase3_connectors.csv", selected)
    return {"model": model, "selected": selected, "output": csv_path}


def run_pipeline(
    model_path: str | Path, output_dir: str | Path, max_additions: int = 500
) -> dict[str, Any]:
    """Run the JSON phase 1→2→3 pipeline and write the final model."""
    model = json.loads(Path(model_path).read_text())
    phase1 = run_phase1(model, output_dir)
    phase2 = run_phase2(model, phase1["candidates"], output_dir)
    phase3 = run_phase3(model, phase1["candidates"], output_dir, max_additions)
    output_model = Path(output_dir) / "gapfilled_model.json"
    output_model.write_text(json.dumps(model, indent=2) + "\n")
    return {"model": output_model, "phase1": phase1, "phase2": phase2, "phase3": phase3}
