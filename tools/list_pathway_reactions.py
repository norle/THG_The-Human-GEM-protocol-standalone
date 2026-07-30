#!/usr/bin/env python3
"""Compatibility CLI for KEGG pathway reaction listing."""

from __future__ import annotations

import argparse
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pathways", type=Path, help="tab-separated pathway input")
    parser.add_argument("output", type=Path, help="destination TSV")
    parser.add_argument("--all", action="store_true", help="process every pathway")
    parser.add_argument("--limit", type=int, default=5, help="maximum pathways")
    args = parser.parse_args(argv)
    from thg_protocol.pathway.kegg_listing import list_pathway_reactions

    list_pathway_reactions(args.pathways, args.output, limit=None if args.all else args.limit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
