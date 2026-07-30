"""Compatibility entry point for the package pathway workflow.

Use ``thg-pathway`` after installing the package.  This module remains for
checkouts and older automation, but contains no workflow logic, prompts, or
repository-relative paths.
"""

from __future__ import annotations

import argparse
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    """Build the parser without requiring an installed package or COBRA."""
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
    """Delegate execution to the installed package API."""
    args = build_parser().parse_args(argv)
    from thg_protocol.pathway.workflow import implement_pathway_files

    result = implement_pathway_files(
        args.model, args.config, args.database, args.output
    )
    print(
        f"Added {result['compartments_added']} compartments, "
        f"{result['metabolites_added']} metabolites, and "
        f"{result['reactions_added']} reactions to {args.output}"
    )
    return 0

__all__ = ["build_parser", "main"]


if __name__ == "__main__":
    raise SystemExit(main())
