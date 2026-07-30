"""Explicit report generator for archived reaction-identification results."""

from __future__ import annotations

import argparse
from pathlib import Path


def write_report(input_path: str | Path, output_path: str | Path) -> Path:
    import pandas as pd

    frame = pd.read_csv(input_path)
    if "reac" in frame:
        frame = frame.rename(columns={"reac": "kegg_reac_id"})
    if "message" in frame:
        frame = frame.drop(columns=["message"])
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    frame.to_excel(destination, engine="xlsxwriter", index=False)
    return destination


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="CSV result file")
    parser.add_argument("output", type=Path, help="Excel report")
    args = parser.parse_args(argv)
    write_report(args.input, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
