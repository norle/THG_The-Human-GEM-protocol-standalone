"""Archived mass-balance runner.

The historical script wrote reports during import. Reusable formula-level
helpers now live in :mod:`thg_protocol.model_build.mass_balance`; full-model
solver balancing remains an explicit deferred workflow.
"""

from __future__ import annotations

import argparse
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, help="reserved model input")
    parser.add_argument("--output", type=Path, help="reserved report output")
    parser.parse_args(argv)
    raise SystemExit(
        "full-model mass-balance solving remains deferred; use "
        "thg_protocol.model_build.mass_balance for formula-level helpers"
    )


if __name__ == "__main__":
    raise SystemExit(main())
