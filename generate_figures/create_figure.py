"""CLI compatibility wrapper for the figure-generation APIs.

The historical version loaded repository models and rendered figures while the
module was imported.  This wrapper parses explicit paths and performs the
optional COBRA/plotting imports only after argument parsing.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    """Build the parser without importing COBRA or plotting dependencies."""
    parser = argparse.ArgumentParser(
        description="Generate THG model and annotation comparison figures."
    )
    parser.add_argument(
        "--model",
        action="append",
        nargs=2,
        metavar=("NAME", "PATH"),
        required=True,
        help="Named SBML model input; repeat for each model to compare.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Directory for generated SVG figures.",
    )
    parser.add_argument(
        "--report",
        type=Path,
        help="Optional Excel annotation-comparison report.",
    )
    parser.add_argument(
        "--reference-name",
        help="Name of the reference model for new-reaction comparison.",
    )
    parser.add_argument(
        "--new-reaction-name",
        help="Name of the comparison model for new-reaction comparison.",
    )
    parser.add_argument(
        "--memote-scores",
        type=Path,
        help="Optional JSON mapping of category to model scores.",
    )
    parser.add_argument(
        "--algorithm-results",
        type=Path,
        help="Optional JSON mapping of chart title to pie-chart values.",
    )
    return parser


def _read_json(path: Path | None) -> dict | None:
    if path is None:
        return None
    return json.loads(path.read_text())


def main(argv: list[str] | None = None) -> int:
    """Load explicit inputs, generate figures, and return an exit code."""
    args = build_parser().parse_args(argv)

    from cobra.io import read_sbml_model
    from thg_protocol.figures import (
        NamedModel,
        generate_annotation_comparison_figures,
        generate_model_comparison_figures,
    )

    named_models = tuple(
        NamedModel(name, read_sbml_model(path)) for name, path in args.model
    )
    model_by_name = {item.name: item.model for item in named_models}
    reference_model = (
        model_by_name.get(args.reference_name) if args.reference_name else None
    )
    new_reaction_model = (
        model_by_name.get(args.new_reaction_name)
        if args.new_reaction_name
        else None
    )
    if bool(args.reference_name) != bool(args.new_reaction_name):
        raise SystemExit(
            "--reference-name and --new-reaction-name must be supplied together"
        )
    if args.reference_name and reference_model is None:
        raise SystemExit(f"Unknown reference model: {args.reference_name}")
    if args.new_reaction_name and new_reaction_model is None:
        raise SystemExit(f"Unknown comparison model: {args.new_reaction_name}")

    result = generate_model_comparison_figures(
        named_models,
        args.output_dir,
        reference_model=reference_model,
        new_reaction_model=new_reaction_model,
        memote_scores=_read_json(args.memote_scores),
        algorithm_results=_read_json(args.algorithm_results),
    )
    output_paths = list(result.output_paths)
    if args.report is not None:
        output_paths.extend(
            generate_annotation_comparison_figures(
                args.report, args.output_dir
            ).output_paths
        )
    print(f"Generated {len(output_paths)} figure(s) in {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
