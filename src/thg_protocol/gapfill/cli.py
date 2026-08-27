"""Standalone, model-agnostic gapfill command."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run standalone THG JSON gapfill operations."
    )
    parser.add_argument(
        "--model", required=True, type=Path, help="Input COBRA JSON or SBML model."
    )
    parser.add_argument(
        "--method", required=True, choices=("milp", "greedy", "deadends")
    )
    parser.add_argument(
        "--output-dir", required=True, type=Path, help="Standalone result directory."
    )
    parser.add_argument(
        "--parameters", type=Path, help="Optional method parameters JSON file."
    )
    parser.add_argument("--max-additions", type=int, help="Maximum reactions to add.")
    parser.add_argument(
        "--allowed-connection",
        action="append",
        metavar="FROM:TO",
        help="Allowed transport compartment pair; repeat as needed.",
    )
    return parser


def _parameters(args: argparse.Namespace) -> dict[str, Any]:
    values: dict[str, Any] = {}
    if args.parameters:
        values = json.loads(args.parameters.read_text())
        if not isinstance(values, dict):
            raise ValueError("parameters file must contain a JSON object")
        if "method" in values:
            raise ValueError("parameters file must not contain method; use --method")
    if args.max_additions is not None:
        values["max_additions"] = args.max_additions
    if args.allowed_connection:
        pairs = []
        for item in args.allowed_connection:
            parts = item.split(":")
            if len(parts) != 2 or not all(parts):
                raise ValueError("--allowed-connection must be FROM:TO")
            pairs.append(parts)
        values["allowed_connections"] = pairs
    return values


def _load_model(path: Path) -> Any:
    from thg_protocol.io.models import load_model

    return load_model(path)


def _write_outputs(result: Any, destination: Path, checksum: str) -> None:
    from thg_protocol.io.models import save_json, save_sbml

    destination.mkdir(parents=True, exist_ok=True)
    save_json(result.model, destination / "gapfilled-model.json")
    save_sbml(result.model, destination / "gapfilled-model.xml")
    report = result.as_dict() | {"input_checksum": checksum}
    (destination / "gapfill-report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n"
    )
    with (destination / "gapfill-selected-reactions.jsonl").open("w") as handle:
        for reaction_id, coverage in sorted(result.candidate_coverage.items()):
            handle.write(
                json.dumps({"reaction_id": reaction_id, "coverage": coverage}) + "\n"
            )


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        from .core import gapfill_model

        parameters = _parameters(args)
        checksum = hashlib.sha256(args.model.read_bytes()).hexdigest()
        result = gapfill_model(
            _load_model(args.model), method=args.method, parameters=parameters
        )
        _write_outputs(result, args.output_dir, checksum)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        build_parser().error(str(error))
    print(f"Gapfill {result.status}: {args.output_dir / 'gapfilled-model.json'}")
    return 0 if result.status != "failed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
