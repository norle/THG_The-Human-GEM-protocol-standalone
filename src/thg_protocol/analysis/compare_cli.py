"""CLI for reaction-level model comparison."""

from __future__ import annotations

import argparse
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compare reactions in two COBRA models."
    )
    parser.add_argument("model_a", type=Path, help="First JSON or SBML model.")
    parser.add_argument("model_b", type=Path, help="Second JSON or SBML model.")
    parser.add_argument("--output-dir", type=Path, help="Directory for CSV reports.")
    parser.add_argument(
        "--include-blocked",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Also compare copies with universally blocked reactions removed.",
    )
    parser.add_argument(
        "--semantic",
        action="store_true",
        help="Write a deterministic semantic JSON comparison instead of CSV reports.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    from .compare import compare_models_from_files

    if args.semantic:
        from .compare import compare_model_files_semantically, save_semantic_comparison

        comparison = compare_model_files_semantically(args.model_a, args.model_b)
        if args.output_dir is not None:
            save_semantic_comparison(
                comparison, args.output_dir / "semantic-comparison.json"
            )
        print(f"semantic: equal={comparison['equal']}")
        return 0
    reports = compare_models_from_files(
        args.model_a,
        args.model_b,
        args.output_dir,
        include_blocked=args.include_blocked,
    )
    for name, comparison in reports.items():
        summary = comparison["_summary"]
        print(
            f"{name}: {summary['total_rxns_a']} vs {summary['total_rxns_b']} reactions"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
