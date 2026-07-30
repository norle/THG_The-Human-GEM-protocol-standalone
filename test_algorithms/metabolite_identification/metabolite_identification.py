"""Explicit report generator for archived metabolite-identification results."""

from __future__ import annotations

import argparse
from pathlib import Path


def process_met_file(met_file: str | Path):
    import pandas as pd

    frame = pd.read_csv(met_file)
    if "identifier" in frame:
        frame["identifier"] = frame["identifier"].replace(r"[a-z]+", "", regex=True)
    if "message" in frame:
        frame = frame.drop(columns=["message"])
    return frame


def write_report(inputs: list[str | Path], output_path: str | Path) -> Path:
    import pandas as pd

    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(destination) as writer:
        for index, input_path in enumerate(inputs):
            process_met_file(input_path).to_excel(
                writer, sheet_name=f"threshold_{index + 1}", index=False
            )
    return destination


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+", type=Path, help="CSV result files")
    parser.add_argument("--output", required=True, type=Path, help="Excel report")
    args = parser.parse_args(argv)
    write_report(args.inputs, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
