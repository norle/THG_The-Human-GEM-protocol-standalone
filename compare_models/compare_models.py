"""Compatibility entry point for the installed model-comparison workflow.

The historical script created a workbook at import time using repository-local
model paths.  Keep this path usable for existing callers, but delegate the
actual work to :mod:`thg_protocol.analysis.compare` and require all paths from
the command line.
"""

from __future__ import annotations

import argparse
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    """Build the comparison command-line parser without importing COBRA."""
    parser = argparse.ArgumentParser(
        description="Compare reactions in two THG or Human-GEM models."
    )
    parser.add_argument("model_a", type=Path, help="First JSON or SBML model.")
    parser.add_argument("model_b", type=Path, help="Second JSON or SBML model.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Directory for machine-readable CSV reports.",
    )
    parser.add_argument(
        "--include-blocked",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Also compare copies with universally blocked reactions removed.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the package comparison API and return an exit status."""
    args = build_parser().parse_args(argv)
    from thg_protocol.analysis.compare import compare_models_from_files

    reports = compare_models_from_files(
        args.model_a,
        args.model_b,
        args.output_dir,
        include_blocked=args.include_blocked,
    )
    for name, comparison in reports.items():
        summary = comparison["_summary"]
        print(
            f"{name}: {summary['total_rxns_a']} vs "
            f"{summary['total_rxns_b']} reactions"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
