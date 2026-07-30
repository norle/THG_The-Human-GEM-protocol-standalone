#!/usr/bin/env python3
"""Compatibility CLI for database reconstruction.

Credentialed KEGG/BioCyc/Ensembl harvesting is intentionally not performed at
module import time. Deterministic reconstruction from a historical pickle is
available through :mod:`thg_protocol.database`; the live harvester remains a
separate workflow until its checkpoint and credential contract is finalized.
"""

from __future__ import annotations

import argparse
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pickle",
        "--records",
        dest="records_path",
        type=Path,
        help="historical database-generator pickle to reconstruct",
    )
    parser.add_argument("--output", type=Path, help="reconstructed model output")
    parser.add_argument(
        "--pathways", type=Path, help="reserved input for the deferred harvester"
    )
    parser.add_argument(
        "--compounds", type=Path, help="reserved input for the deferred harvester"
    )
    parser.add_argument(
        "--extra-formula",
        type=Path,
        help="reserved input for the deferred harvester",
    )
    parser.add_argument(
        "--checkpoint",
        type=Path,
        help="reserved checkpoint path for the deferred harvester",
    )
    parser.add_argument("--max-reactions", type=int, help="reserved debug limit")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.records_path is None:
        raise SystemExit(
            "credentialed database harvesting remains deferred; provide "
            "--pickle/--records for deterministic reconstruction"
        )
    if args.output is None:
        raise SystemExit("--output is required with --pickle/--records")

    from thg_protocol.database import reconstruct_model_from_pickle

    reconstruct_model_from_pickle(args.records_path, output_path=args.output)
    print(f"Reconstructed model written to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
