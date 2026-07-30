"""Compatibility entry point for the package model-builder workflow.

The former script contained a repository-specific, import-heavy reconstruction
pipeline with fixed model, cache, and report paths.  The maintained workflow
now lives in :mod:`thg_protocol.model_build` and accepts explicit paths.
"""

from __future__ import annotations

import argparse
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    """Build the parser without importing COBRA or service clients."""
    parser = argparse.ArgumentParser(
        description="Annotate a COBRA model through package service clients."
    )
    parser.add_argument("input_model", type=Path, help="Input JSON or SBML model.")
    parser.add_argument("output_model", type=Path, help="Output JSON or SBML model.")
    parser.add_argument(
        "--cache-dir", type=Path, help="Directory for service response caches."
    )
    parser.add_argument(
        "--errors",
        type=Path,
        help="Optional JSON path for service errors collected during the run.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Delegate execution to :func:`thg_protocol.model_build.build_model`."""
    args = build_parser().parse_args(argv)
    from thg_protocol.model_build import build_model

    report = build_model(
        args.input_model,
        args.output_model,
        cache_dir=args.cache_dir,
        errors_path=args.errors,
    )
    print(
        f"Wrote {report.output_path}; KEGG={report.kegg_reactions}, "
        f"BioCyc={report.biocyc_ec_pages}, Ensembl={report.ensembl_genes}"
    )
    if report.errors:
        print(f"Completed with {len(report.errors)} service errors.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
