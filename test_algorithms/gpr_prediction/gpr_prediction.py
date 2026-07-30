"""Explicit report generator for archived GPR prediction results."""

from __future__ import annotations

import argparse
from pathlib import Path


def summarize_results(input_path: str | Path, output_path: str | Path) -> Path:
    """Copy/normalize a historical CSV result table to an Excel report."""
    import pandas as pd

    source = Path(input_path)
    destination = Path(output_path)
    frame = pd.read_csv(source)
    if "expected_gprs" in frame.columns:
        frame = frame.rename(columns={"expected_gprs": "expected_gpr"})
    if "message" in frame.columns:
        frame = frame.drop(columns=["message"])
    destination.parent.mkdir(parents=True, exist_ok=True)
    frame.to_excel(destination, engine="xlsxwriter", index=False)
    return destination


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="archived CSV results")
    parser.add_argument("output", type=Path, help="destination Excel report")
    args = parser.parse_args(argv)
    summarize_results(args.input, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
