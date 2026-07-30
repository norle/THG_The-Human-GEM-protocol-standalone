"""Compatibility entry point for cell-specific activity reduction.

The maintained, dependency-light implementation is
``thg_protocol.cell_specific.reduce_model_by_activity``.  This legacy path
keeps a small function and CLI for existing automation while requiring all
inputs and outputs explicitly.  Gapfilling is a separate workflow and is not
performed implicitly by this command.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Sequence


def model_reduce(
    model: Any,
    solutions_gimme: str | Path,
    output_model_path: str | Path,
    *,
    presence_threshold: float = 0.0,
    preserve_reactions: Sequence[str] = (),
    matrix_key: str = "all_Solutions_matrix5",
) -> Any:
    """Reduce ``model`` using the package activity-reduction API."""
    from thg_protocol.cell_specific import reduce_model_by_activity

    tailored, _ = reduce_model_by_activity(
        model,
        solutions_gimme,
        presence_threshold=presence_threshold,
        preserve_reactions=preserve_reactions,
        matrix_key=matrix_key,
        output_path=output_model_path,
    )
    return tailored


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser without importing COBRA or optional solvers."""
    parser = argparse.ArgumentParser(
        description="Reduce a COBRA model using reaction activity data."
    )
    parser.add_argument("model", type=Path, help="Input JSON or SBML model.")
    parser.add_argument(
        "activity",
        type=Path,
        help="Reaction activity CSV or MAT file.",
    )
    parser.add_argument("output", type=Path, help="Output JSON or SBML model.")
    parser.add_argument(
        "--presence-threshold",
        type=float,
        default=0.0,
        help="Remove reactions present at or below this fraction of samples.",
    )
    parser.add_argument(
        "--preserve-reaction",
        action="append",
        default=[],
        dest="preserve_reactions",
        help="Reaction ID to retain; may be supplied more than once.",
    )
    parser.add_argument(
        "--matrix-key",
        default="all_Solutions_matrix5",
        help="MAT variable containing the activity matrix.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Load the model, run package tailoring, and return an exit status."""
    args = build_parser().parse_args(argv)
    from cobra import io

    model = (
        io.load_json_model(str(args.model))
        if args.model.suffix.lower() == ".json"
        else io.read_sbml_model(str(args.model))
    )
    tailored = model_reduce(
        model,
        args.activity,
        args.output,
        presence_threshold=args.presence_threshold,
        preserve_reactions=args.preserve_reactions,
        matrix_key=args.matrix_key,
    )
    print(f"Wrote {len(tailored.reactions)} reactions to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
