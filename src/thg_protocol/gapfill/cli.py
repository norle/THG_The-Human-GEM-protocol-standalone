"""Import-safe command-line entry point for gapfill workflows."""

from __future__ import annotations

import argparse
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the THG JSON gapfill pipeline.")
    parser.add_argument("--model", required=True, type=Path, help="Input model JSON.")
    parser.add_argument(
        "--output-dir", required=True, type=Path, help="Output directory."
    )
    parser.add_argument(
        "--max-additions", type=int, default=500, help="Maximum phase-3 additions."
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    from .core import run_pipeline

    result = run_pipeline(args.model, args.output_dir, args.max_additions)
    print(f"Gapfill model written to {result['model']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
