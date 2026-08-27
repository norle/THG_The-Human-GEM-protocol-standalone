"""Dependency-light reaction comparison helpers.

The comparison functions operate on any model exposing ``reactions`` whose
reactions expose ``id`` and ``metabolites``.  COBRApy is imported only by the
file-oriented helper, keeping package imports and CLI argument parsing safe in
minimal environments.
"""

from __future__ import annotations

import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from .model_signature import diff_model_signatures, model_signature

__all__ = [
    "compare_models",
    "compare_models_from_files",
    "compare_reactions",
    "reactions_by_compartment",
    "remove_blocked_reactions",
    "save_comparison_csv",
    "compare_semantic_models",
    "compare_model_files_semantically",
    "compare_workflow_runs",
    "save_semantic_comparison",
]


def reactions_by_compartment(model: Any) -> dict[str, set[str]]:
    """Return reaction IDs grouped by every compartment they involve."""
    grouped: defaultdict[str, set[str]] = defaultdict(set)
    for reaction in model.reactions:
        compartments = {
            getattr(metabolite, "compartment", "")
            for metabolite in reaction.metabolites
        }
        for compartment in compartments or {""}:
            grouped[compartment].add(reaction.id)
    return dict(grouped)


def _stoichiometry(reaction: Any) -> frozenset[tuple[str, float]]:
    metabolites = reaction.metabolites
    items = metabolites.items() if hasattr(metabolites, "items") else metabolites
    return frozenset(
        (metabolite.id, float(coefficient)) for metabolite, coefficient in items
    )


def compare_reactions(model_a: Any, model_b: Any) -> dict[str, Any]:
    """Compare reaction IDs and stoichiometry per compartment."""
    by_a = reactions_by_compartment(model_a)
    by_b = reactions_by_compartment(model_b)
    stoich_a = {reaction.id: _stoichiometry(reaction) for reaction in model_a.reactions}
    stoich_b = {reaction.id: _stoichiometry(reaction) for reaction in model_b.reactions}

    result: dict[str, Any] = {}
    for compartment in sorted(set(by_a) | set(by_b)):
        ids_a = by_a.get(compartment, set())
        ids_b = by_b.get(compartment, set())
        common = ids_a & ids_b
        matching_stoich = {rid for rid in common if stoich_a[rid] == stoich_b[rid]}
        result[compartment] = {
            "n_a": len(ids_a),
            "n_b": len(ids_b),
            "intersect_id": len(common),
            "intersect_stoich": len(matching_stoich),
            "rxns_a": ids_a,
            "rxns_b": ids_b,
            "match_ids": sorted(common),
            "match_stoich_ids": sorted(matching_stoich),
        }
    result["_summary"] = {
        "total_rxns_a": len(model_a.reactions),
        "total_rxns_b": len(model_b.reactions),
    }
    return result


# Public name matching the plan and the legacy workflow terminology.
compare_models = compare_reactions


_CHANGE_CATEGORIES = (
    "identifier_normalization",
    "annotation_enrichment",
    "formula_or_charge_correction",
    "gpr_correction",
    "localization_expansion",
    "database_only_addition",
    "duplicate_consolidation",
    "manual_override",
    "validation_result_changes",
    "task_result_changes",
    "other_semantic_changes",
)


def _category_for_object(collection: str, value: Any, *, added: bool = False) -> str:
    """Classify a semantic change using stable, inspectable model metadata."""
    if collection in {"metabolites", "reactions", "genes"} and added:
        annotation = value.get("annotation", {}) if isinstance(value, dict) else {}
        text = json.dumps(annotation, sort_keys=True).lower()
        if any(token in text for token in ("database", "hmdb", "bigg", "kegg")):
            return "database_only_addition"
        if collection == "reactions" and "compartment" in text:
            return "localization_expansion"
    if collection == "reactions":
        return "other_semantic_changes"
    if collection == "metabolites":
        return "other_semantic_changes"
    return "other_semantic_changes"


def _without_id(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _without_id(item) for key, item in value.items() if key != "id"}
    if isinstance(value, list):
        return [_without_id(item) for item in value]
    return value


def _categorize_signature_diff(
    signature_a: dict[str, Any], signature_b: dict[str, Any], diff: dict[str, Any]
) -> dict[str, list[dict[str, Any]]]:
    categories = {name: [] for name in _CHANGE_CATEGORIES}
    for collection, items in diff["changed"].items():
        for item in items:
            before, after = item.get("a", {}), item.get("b", {})
            fields = set(before) | set(after)
            if collection == "reactions":
                if before.get("gene_reaction_rule") != after.get("gene_reaction_rule"):
                    category = "gpr_correction"
                elif before.get("annotation") != after.get("annotation"):
                    category = "annotation_enrichment"
                elif before.get("stoichiometry") != after.get("stoichiometry"):
                    category = "formula_or_charge_correction"
                elif {"lower_bound", "upper_bound"} & fields:
                    category = "manual_override"
                else:
                    category = "other_semantic_changes"
            elif collection == "metabolites":
                if (
                    before.get("formula") != after.get("formula")
                    or before.get("charge") != after.get("charge")
                ):
                    category = "formula_or_charge_correction"
                elif before.get("compartment") != after.get("compartment"):
                    category = "localization_expansion"
                elif before.get("annotation") != after.get("annotation"):
                    category = "annotation_enrichment"
                elif before.get("id") != after.get("id"):
                    category = "identifier_normalization"
                else:
                    category = "other_semantic_changes"
            elif collection == "genes" and before.get("annotation") != after.get(
                "annotation"
            ):
                category = "annotation_enrichment"
            elif collection == "groups":
                category = "localization_expansion"
            else:
                category = "other_semantic_changes"
            categories[category].append({"collection": collection, **item})
    paired_ids: set[tuple[str, str]] = set()
    for collection in diff["added"]:
        identifier_key = "reaction" if collection == "objective" else "id"
        added_items = {
            identifier: next(
                item
                for item in signature_b.get(collection, ())
                if item.get(identifier_key) == identifier
            )
            for identifier in diff["added"][collection]
        }
        removed_items = {
            identifier: next(
                item
                for item in signature_a.get(collection, ())
                if item.get(identifier_key) == identifier
            )
            for identifier in diff["removed"].get(collection, ())
        }
        for added_id, added_item in added_items.items():
            for removed_id, removed_item in removed_items.items():
                if (collection, removed_id) in paired_ids:
                    continue
                if _without_id(added_item) == _without_id(removed_item):
                    categories["identifier_normalization"].append(
                        {
                            "collection": collection,
                            "change": "renamed",
                            "from": removed_id,
                            "to": added_id,
                        }
                    )
                    paired_ids.update(
                        {(collection, removed_id), (collection, added_id)}
                    )
                    break
    for kind in ("added", "removed"):
        for collection, identifiers in diff[kind].items():
            for identifier in identifiers:
                if (collection, identifier) in paired_ids:
                    continue
                right = next(
                    (
                        x
                        for x in signature_b.get(collection, ())
                        if x.get("id") == identifier
                    ),
                    {},
                )
                category = _category_for_object(
                    collection, right, added=kind == "added"
                )
                if kind == "removed" and collection == "reactions":
                    category = "duplicate_consolidation"
                categories[category].append(
                    {"collection": collection, "change": kind, "id": identifier}
                )
    return {key: value for key, value in categories.items() if value}


def compare_semantic_models(model_a: Any, model_b: Any) -> dict[str, Any]:
    """Compare model meaning and classify every added, removed, or changed object.

    The result is JSON-compatible and deterministic, making it suitable for a
    run artifact and for comparing uninterrupted and resumed releases.
    """
    signature_a = model_signature(model_a)
    signature_b = model_signature(model_b)
    diff = diff_model_signatures(signature_a, signature_b)
    categories = _categorize_signature_diff(signature_a, signature_b, diff)
    return {
        "schema_version": 1,
        "signature_version": signature_a["signature_version"],
        "equal": signature_a == signature_b,
        "a_sha256": hashlib.sha256(
            json.dumps(signature_a, sort_keys=True).encode()
        ).hexdigest(),
        "b_sha256": hashlib.sha256(
            json.dumps(signature_b, sort_keys=True).encode()
        ).hexdigest(),
        "diff": diff,
        "categories": categories,
        "category_counts": {key: len(value) for key, value in categories.items()},
    }


def _load_model(path: Path) -> Any:
    from thg_protocol.io.models import load_model

    return load_model(path)


def compare_model_files_semantically(
    model_a_path: str | Path, model_b_path: str | Path
) -> dict[str, Any]:
    """Run a semantic comparison on two JSON or SBML model files."""
    return compare_semantic_models(
        _load_model(Path(model_a_path)), _load_model(Path(model_b_path))
    )


def _run_model_path(run_dir: Path) -> Path:
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    candidates = []
    for entry in manifest.get("steps", {}).values():
        for output in entry.get("outputs", []):
            if output.get("role") in {"model", "sbml"}:
                candidates.append(run_dir / output["path"])
    if not candidates:
        raise ValueError(f"run has no model artifact: {run_dir}")
    return candidates[-1]


def compare_workflow_runs(run_a: str | Path, run_b: str | Path) -> dict[str, Any]:
    """Compare final model artifacts and non-model validation/task artifacts."""
    left, right = Path(run_a), Path(run_b)
    result = {
        "schema_version": 1,
        "model": compare_model_files_semantically(
            _run_model_path(left), _run_model_path(right)
        ),
    }
    for role in ("validation", "tasks", "task-results"):
        def payload(root: Path, artifact_role: str = role) -> Any:
            manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
            paths = [
                root / output["path"]
                for entry in manifest.get("steps", {}).values()
                for output in entry.get("outputs", [])
                if output.get("role") == artifact_role
            ]
            return json.loads(paths[-1].read_text(encoding="utf-8")) if paths else None
        a, b = payload(left), payload(right)
        if a != b:
            result[role] = {"changed": True, "a": a, "b": b}
    result["equal"] = all(
        value.get("changed") is not True
        for key, value in result.items()
        if key != "equal"
    )
    return result


def save_semantic_comparison(
    comparison: dict[str, Any], output_path: str | Path
) -> None:
    """Write a stable JSON semantic-comparison artifact."""
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(comparison, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def remove_blocked_reactions(model: Any) -> Any:
    """Return a copy with COBRA universally blocked reactions removed."""
    from cobra.flux_analysis import find_blocked_reactions

    copied = model.copy()
    blocked = set(find_blocked_reactions(copied, open_exchanges=True))
    for reaction_id in sorted(blocked):
        copied.reactions.remove(copied.reactions.get_by_id(reaction_id))
    return copied


def compare_models_from_files(
    model_a_path: str | Path,
    model_b_path: str | Path,
    output_dir: str | Path | None = None,
    *,
    include_blocked: bool = True,
) -> dict[str, dict[str, Any]]:
    """Load two JSON/SBML models and optionally write comparison CSV reports."""
    def load(path: Path) -> Any:
        from thg_protocol.io.models import load_model

        return load_model(path)

    model_a = load(Path(model_a_path))
    model_b = load(Path(model_b_path))
    reports = {"raw": compare_reactions(model_a, model_b)}
    if include_blocked:
        reports["no_blocked"] = compare_reactions(
            remove_blocked_reactions(model_a), remove_blocked_reactions(model_b)
        )
    if output_dir is not None:
        destination = Path(output_dir)
        destination.mkdir(parents=True, exist_ok=True)
        for name, comparison in reports.items():
            save_comparison_csv(
                comparison, destination / f"compartments_comparison_{name}.csv"
            )
    return reports


def save_comparison_csv(comparison: dict[str, Any], output_path: str | Path) -> None:
    """Write a stable, machine-readable comparison report."""
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "compartment",
                "n_model_a",
                "n_model_b",
                "only_in_a",
                "only_in_b",
                "n_in_both_by_id",
                "n_in_both_by_stoich",
                "overlap_a_pct",
                "overlap_b_pct",
                "match_ids",
                "match_stoich_ids",
            ]
        )
        for compartment, data in comparison.items():
            if compartment == "_summary":
                continue
            overlap_a = 100 * data["intersect_id"] / data["n_a"] if data["n_a"] else 0
            overlap_b = 100 * data["intersect_id"] / data["n_b"] if data["n_b"] else 0
            writer.writerow(
                [
                    compartment,
                    data["n_a"],
                    data["n_b"],
                    data["n_a"] - data["intersect_id"],
                    data["n_b"] - data["intersect_id"],
                    data["intersect_id"],
                    data["intersect_stoich"],
                    f"{overlap_a:.1f}%",
                    f"{overlap_b:.1f}%",
                    ";".join(data["match_ids"]),
                    ";".join(data["match_stoich_ids"]),
                ]
            )
