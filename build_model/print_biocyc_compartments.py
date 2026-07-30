#!/usr/bin/env python3
"""Print a summary of explicit BioCyc compartment cache files."""

from __future__ import annotations

import argparse
import pickle
from pathlib import Path
from typing import Any


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "locations",
        type=Path,
        help="Pickle mapping BioCyc IDs to location dictionaries.",
    )
    parser.add_argument(
        "names",
        type=Path,
        help="Pickle mapping ORG:FRAMEID keys to compartment names.",
    )
    parser.add_argument("--sample-size", type=int, default=10)
    return parser


def _load_mapping(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        value = pickle.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"cache must contain a mapping: {path}")
    return value


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    from thg_protocol.database import summarize_biocyc_compartments

    summary = summarize_biocyc_compartments(
        _load_mapping(args.locations),
        _load_mapping(args.names),
        sample_size=args.sample_size,
    )
    print("BioCyc compartments summary")
    print("=================================")
    print(f"Biovelo location entries: {summary.entry_count}")
    print(f"Unique frameids found: {summary.frameid_count}")
    print(f"Unique resolved compartment names: {summary.resolved_count}")
    print("\nResolved compartment mapping (org:frameid -> name):")
    for key, name in summary.resolved.items():
        print(f"{key} -> {name}")
    print("\nUnique compartment names (sorted):")
    for name in summary.unique_names:
        print(name)
    print("\nSample Biocyc ID -> locations")
    for identifier, locations in summary.sample:
        print(f"{identifier}:")
        for location in locations:
            org = location.get("orgid") or "HUMAN"
            frameid = location.get("frameid")
            key = f"{org}:{frameid}"
            print(f"  - frameid={frameid} ({key}) -> {summary.resolved.get(key, frameid)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
