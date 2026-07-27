"""Command-line wrapper for the pathway workflow."""

from __future__ import annotations

import argparse
from pathlib import Path

from .workflow import implement_pathway_files


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Implement configured pathway components in a JSON model."
    )
    parser.add_argument("--model", required=True, type=Path, help="Input model JSON.")
    parser.add_argument(
        "--config", required=True, type=Path, help="Pathway config JSON."
    )
    parser.add_argument(
        "--database", required=True, type=Path, help="Metabolite ID database JSON."
    )
    parser.add_argument("--output", required=True, type=Path, help="Output model JSON.")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the pathway CLI and return an exit status."""
    args = build_parser().parse_args(argv)
    result = implement_pathway_files(
        args.model, args.config, args.database, args.output
    )
    print(
        f"Added {result['compartments_added']} compartments, "
        f"{result['metabolites_added']} metabolites, and "
        f"{result['reactions_added']} reactions to {args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
