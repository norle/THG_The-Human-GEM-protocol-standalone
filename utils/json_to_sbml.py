"""Compatibility CLI for JSON-to-SBML conversion.

The conversion implementation is maintained in :mod:`thg_protocol.io`.
"""

from __future__ import annotations

import argparse
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="source COBRA JSON model")
    parser.add_argument("output", type=Path, help="destination SBML file")
    args = parser.parse_args(argv)
    from thg_protocol.io import convert_json_to_sbml

    convert_json_to_sbml(args.input, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
