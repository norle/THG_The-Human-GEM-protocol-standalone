"""Compatibility CLI for the package-owned JSON gapfill workflow."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    phase1 = subparsers.add_parser("phase1", help="generate transport candidates")
    phase1.add_argument("--model", required=True, type=Path)
    phase1.add_argument("--out", required=True, type=Path)
    phase2 = subparsers.add_parser("phase2", help="select minimum connectors")
    phase2.add_argument("--model", required=True, type=Path)
    phase2.add_argument("--candidates", required=True, type=Path)
    phase2.add_argument("--out", required=True, type=Path)
    phase3 = subparsers.add_parser("phase3", help="run greedy phase 3")
    phase3.add_argument("--model", required=True, type=Path)
    phase3.add_argument("--candidates", required=True, type=Path)
    phase3.add_argument("--out", required=True, type=Path)
    phase3.add_argument("--max", type=int, default=500)
    pipeline = subparsers.add_parser("run-all", help="run phases 1 through 3")
    pipeline.add_argument("--model", required=True, type=Path)
    pipeline.add_argument("--out", required=True, type=Path)
    pipeline.add_argument("--max", type=int, default=500)
    return parser


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    from thg_protocol.gapfill.core import (
        run_phase1,
        run_phase2,
        run_phase3,
        run_pipeline,
    )

    if args.command == "phase1":
        run_phase1(_load(args.model), args.out)
    elif args.command == "phase2":
        model = _load(args.model)
        run_phase2(model, args.candidates, args.out)
    elif args.command == "phase3":
        model = _load(args.model)
        run_phase3(model, args.candidates, args.out, args.max)
    else:
        run_pipeline(args.model, args.out, args.max)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
