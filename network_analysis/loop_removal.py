"""Archived solver-backed loop-removal workflow; not an installed API."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any


def remove_loops(model: Any, no_blocked_reactions: bool = False) -> tuple[Any, list[Any], list[str]]:
    """Run the historical compaction algorithm without import-time side effects.

    The package connectivity API intentionally does not perform solver-backed
    loop removal. This compatibility function keeps that optional workflow
    available while loading its heavy implementation only when called.
    """
    from network_analysis.compaction import full_compaction

    compacted, loop_reactions = full_compaction(
        model, no_blocked_reactions=no_blocked_reactions
    )
    reaction_ids: list[str] = []
    for compacted_reaction in loop_reactions:
        cleaned = compacted_reaction.id.replace("(", "").replace(")", "")
        for part in cleaned.split("#"):
            reaction_ids.extend(part.split("@"))
    compacted.remove_reactions(reaction_ids)
    return compacted, loop_reactions, reaction_ids


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model", type=Path, help="input JSON model")
    parser.add_argument("output", type=Path, help="output JSON model")
    parser.add_argument(
        "--allow-blocked", action="store_true", help="skip blocked-reaction filtering"
    )
    args = parser.parse_args(argv)

    from cobra.io import load_json_model, save_json_model

    model = load_json_model(str(args.model))
    result, _, _ = remove_loops(model, no_blocked_reactions=args.allow_blocked)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    save_json_model(result, str(args.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
