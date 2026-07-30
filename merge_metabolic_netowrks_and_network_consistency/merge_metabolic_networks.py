"""Compatibility entry point for the package model-merge workflow.

The historical script merged three repository-local models at import time.
This wrapper keeps the legacy location usable while making inputs, output, and
isolated-metabolite cleanup explicit.
"""

from __future__ import annotations

import argparse
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    """Build the parser without importing COBRA or loading model files."""
    parser = argparse.ArgumentParser(description="Merge two COBRA model files.")
    parser.add_argument("base_model", type=Path, help="Target/base JSON or SBML model.")
    parser.add_argument(
        "incoming_model", type=Path, help="Source/incoming JSON or SBML model."
    )
    parser.add_argument("output", type=Path, help="Merged JSON or SBML output path.")
    parser.add_argument(
        "--remove-isolated-metabolites",
        action="store_true",
        help="Remove metabolites not referenced by any reaction.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Delegate execution to :func:`thg_protocol.merge.merge_models_from_paths`."""
    args = build_parser().parse_args(argv)
    from thg_protocol.merge import merge_models_from_paths

    _, report = merge_models_from_paths(
        args.base_model,
        args.incoming_model,
        args.output,
        remove_isolated_metabolites=args.remove_isolated_metabolites,
    )
    print(
        f"Merged {report.added_reactions} reactions and "
        f"{report.added_metabolites} metabolites into {report.output_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
