#!/usr/bin/env python3
"""Compatibility CLI for multi-pass metabolite/reaction annotation."""

from __future__ import annotations

import argparse
from pathlib import Path
from thg_protocol.annotation.metabolite_reactions import (
    run_metabolite_reaction_identification,
)


def build_parser() -> argparse.ArgumentParser:
    """Build the parser without importing COBRA or loading model files."""
    parser = argparse.ArgumentParser(
        description=(
            "Annotate a THG model and retry unresolved PubChem metabolites."
        )
    )
    parser.add_argument(
        "--model",
        type=Path,
        required=True,
        help="Input model SBML path.",
    )
    parser.add_argument(
        "--database",
        type=Path,
        required=True,
        help="Reference database SBML path used for reaction matching.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Directory for annotation reports and default model outputs.",
    )
    parser.add_argument(
        "--model-output",
        type=Path,
        help="Annotated SBML output path.",
    )
    parser.add_argument(
        "--normalized-model-output",
        type=Path,
        help="Normalized annotated SBML output path.",
    )
    parser.add_argument(
        "--annotation-delay",
        type=float,
        default=1.0,
        help="Minimum delay between initial PubChem requests, in seconds.",
    )
    parser.add_argument(
        "--max-retry-rounds",
        type=int,
        default=10,
        help="Maximum retry passes for unresolved metabolites.",
    )
    parser.add_argument(
        "--retry-stop-threshold",
        type=float,
        default=0.1,
        help="Stop when unresolved metabolites reach this fraction of total.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the retry workflow and return a process exit code."""
    args = build_parser().parse_args(argv)
    result = run_metabolite_reaction_identification(
        args.model,
        args.database,
        args.output_dir,
        model_output_path=args.model_output,
        normalized_model_output_path=args.normalized_model_output,
        annotation_delay=args.annotation_delay,
        max_retry_rounds=args.max_retry_rounds,
        retry_stop_threshold=args.retry_stop_threshold,
    )
    print(
        "Annotated "
        f"{result.annotated_metabolite_count}/{result.metabolite_count} "
        f"metabolites and {result.annotated_reaction_count} reactions "
        f"after {result.retry_rounds_executed} retry rounds."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
