"""Compatibility CLI for resuming database model reconstruction."""

from __future__ import annotations

import argparse
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    """Build the parser without importing ``generate_db.py`` or ``dill``."""
    parser = argparse.ArgumentParser(
        description="Resume model reconstruction from database pickle data."
    )
    parser.add_argument("input", type=Path, help="Database-generator pickle path.")
    parser.add_argument("output", type=Path, help="Output JSON or SBML model path.")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Delegate reconstruction to the maintained package API."""
    args = build_parser().parse_args(argv)
    from thg_protocol.database import reconstruct_model_from_pickle

    model = reconstruct_model_from_pickle(args.input, output_path=args.output)
    print(
        f"Wrote {args.output}: {len(model.metabolites)} metabolites, "
        f"{len(model.reactions)} reactions, and {len(model.genes)} genes"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
