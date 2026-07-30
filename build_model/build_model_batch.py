"""Compatibility entry point for the package batch model-builder API."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any


def build_parser() -> argparse.ArgumentParser:
    """Build the parser without importing COBRA or service clients."""
    parser = argparse.ArgumentParser(
        description="Annotate a model through the THG batch model-builder API."
    )
    parser.add_argument("input_model", type=Path, help="Input JSON or SBML model.")
    parser.add_argument("output_model", type=Path, help="Output JSON or SBML model.")
    parser.add_argument("--cache-dir", type=Path, help="Batch cache directory.")
    parser.add_argument(
        "--output-errors", type=Path, help="Optional tab-separated error report."
    )
    return parser


def main(
    argv: list[str] | None = None,
    *,
    input_model: str | Path | None = None,
    output_model_final: str | Path | None = None,
    output_errors: str | Path | None = None,
    cache_dir: str | Path | None = None,
    biocyc_client: Any | None = None,
    kegg_client: Any | None = None,
    ensembl_client: Any | None = None,
) -> None:
    """Run the package batch API, retaining the legacy keyword boundary."""
    if input_model is None or output_model_final is None:
        args = build_parser().parse_args(argv)
        input_model = args.input_model
        output_model_final = args.output_model
        output_errors = args.output_errors
        cache_dir = args.cache_dir

    from thg_protocol.model_build import build_model_batch

    build_model_batch(
        input_model,
        output_model_final,
        output_errors=output_errors,
        cache_dir=cache_dir,
        biocyc_client=biocyc_client,
        kegg_client=kegg_client,
        ensembl_client=ensembl_client,
    )


if __name__ == "__main__":
    main()
