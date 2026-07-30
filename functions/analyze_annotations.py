"""Compatibility CLI for JSON model annotation analysis."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from thg_protocol.annotation.model_annotations import (
    analyze_model_annotations,
    extract_metabolite_annotations,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model", type=Path, help="Input JSON model path.")
    parser.add_argument(
        "--target", action="append", required=True, help="Target metabolite name; repeat."
    )
    parser.add_argument("--output", type=Path, help="Optional JSON output path.")
    parser.add_argument("--quiet", action="store_true", help="Suppress summary output.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    annotations, not_found = extract_metabolite_annotations(args.model, args.target)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps({"annotations": annotations, "not_found": not_found}, indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
    if not args.quiet:
        counts = analyze_model_annotations(args.model)
        print(f"Found {len(annotations)}/{len(args.target)} target metabolites.")
        print(f"Annotation fields: {len(counts)}")
        if not_found:
            print("Not found: " + ", ".join(not_found))
    return 0


__all__ = ["analyze_model_annotations", "build_parser", "extract_metabolite_annotations", "main"]


if __name__ == "__main__":
    raise SystemExit(main())
