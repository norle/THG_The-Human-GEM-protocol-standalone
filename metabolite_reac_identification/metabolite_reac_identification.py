"""CLI compatibility wrapper for metabolite/reaction identification."""

from __future__ import annotations

import argparse
from pathlib import Path

from thg_protocol.annotation.metabolite_reactions import (
    run_metabolite_reaction_identification,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser without loading COBRA or model files."""
    parser = argparse.ArgumentParser(
        description="Annotate a THG model's metabolites and reactions."
    )
    parser.add_argument(
        "--model",
        type=Path,
        default=PROJECT_ROOT / "models" / "Human-GEM1_19.xml",
        help="Input model SBML path.",
    )
    parser.add_argument(
        "--database",
        type=Path,
        default=PROJECT_ROOT / "models" / "Human Database.xml",
        help="Reference database SBML path used for reaction matching.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "metabolite_reac_identification" / "reports",
        help="Directory for annotation reports and default model outputs.",
    )
    parser.add_argument(
        "--model-output",
        type=Path,
        default=PROJECT_ROOT / "models" / "THG-beta1.1.1.xml",
        help="Annotated SBML output path.",
    )
    parser.add_argument(
        "--normalized-model-output",
        type=Path,
        default=PROJECT_ROOT / "models" / "THG-beta1.1.xml",
        help="Normalized annotated SBML output path.",
    )
    parser.add_argument(
        "--annotation-delay",
        type=float,
        default=1.0,
        help="Minimum delay between PubChem requests, in seconds.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the annotation workflow and return a process exit code."""
    args = build_parser().parse_args(argv)
    result = run_metabolite_reaction_identification(
        args.model,
        args.database,
        args.output_dir,
        model_output_path=args.model_output,
        normalized_model_output_path=args.normalized_model_output,
        annotation_delay=args.annotation_delay,
    )
    print(
        "Annotated "
        f"{result.annotated_metabolite_count}/{result.metabolite_count} metabolites "
        f"and {result.annotated_reaction_count} reactions."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
