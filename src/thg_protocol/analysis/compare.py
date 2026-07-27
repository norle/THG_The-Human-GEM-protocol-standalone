"""Dependency-light reaction comparison helpers.

The comparison functions operate on any model exposing ``reactions`` whose
reactions expose ``id`` and ``metabolites``.  COBRApy is imported only by the
file-oriented helper, keeping package imports and CLI argument parsing safe in
minimal environments.
"""

from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path
from typing import Any

__all__ = [
    "compare_models",
    "compare_models_from_files",
    "compare_reactions",
    "reactions_by_compartment",
    "remove_blocked_reactions",
    "save_comparison_csv",
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
    from cobra.io import load_json_model, read_sbml_model

    def load(path: Path) -> Any:
        return (
            load_json_model(path)
            if path.suffix.lower() == ".json"
            else read_sbml_model(path)
        )

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
