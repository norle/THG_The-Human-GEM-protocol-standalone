"""Compatibility CLI for compartment-level model comparison.

The maintained implementation lives in :mod:`thg_protocol.analysis.compare`.
This module keeps the historical import names available while making model
inputs and report output explicit.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from thg_protocol.analysis.compare import (
    compare_reactions,
    compare_models_from_files,
    reactions_by_compartment,
    remove_blocked_reactions,
    save_comparison_csv,
)


def normalize_stoichiometry(reaction: Any) -> frozenset[tuple[str, float]]:
    """Return a reaction's normalized stoichiometry for legacy callers."""
    items = reaction.metabolites.items()
    return frozenset((metabolite.id, float(coefficient)) for metabolite, coefficient in items)


def comp_compare(model_a: Any, model_b: Any) -> dict[str, Any]:
    """Compatibility alias for the package comparison implementation."""
    return compare_reactions(model_a, model_b)


def print_comparison(comparison: dict[str, Any], title: str = "Comparison") -> None:
    """Print a compact human-readable summary of a comparison."""
    summary = comparison.get("_summary", {})
    print(title)
    for compartment, data in comparison.items():
        if compartment == "_summary":
            continue
        print(
            f"{compartment or 'UNASSIGNED'}: "
            f"{data['n_a']} vs {data['n_b']} reactions, "
            f"{data['intersect_id']} shared by ID, "
            f"{data['intersect_stoich']} shared by stoichiometry"
        )
    print(
        f"SUMMARY: Model A = {summary.get('total_rxns_a', 0)} rxns | "
        f"Model B = {summary.get('total_rxns_b', 0)} rxns"
    )


def save_csv(comparison: dict[str, Any], output_path: str | Path) -> None:
    """Compatibility alias for :func:`save_comparison_csv`."""
    save_comparison_csv(comparison, output_path)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model_a", type=Path, help="First JSON or SBML model.")
    parser.add_argument("model_b", type=Path, help="Second JSON or SBML model.")
    parser.add_argument(
        "--output-dir", type=Path, required=True, help="Directory for CSV reports."
    )
    parser.add_argument(
        "--no-blocked",
        action="store_true",
        help="Only write the raw comparison; skip solver-backed blocked filtering.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Compare two explicit model paths and write CSV reports."""
    args = build_parser().parse_args(argv)
    reports = compare_models_from_files(
        args.model_a,
        args.model_b,
        args.output_dir,
        include_blocked=not args.no_blocked,
    )
    for name, comparison in reports.items():
        print_comparison(comparison, title=name.replace("_", " ").title())
    return 0


__all__ = [
    "comp_compare",
    "main",
    "normalize_stoichiometry",
    "print_comparison",
    "reactions_by_compartment",
    "remove_blocked_reactions",
    "save_csv",
]


if __name__ == "__main__":
    raise SystemExit(main())
