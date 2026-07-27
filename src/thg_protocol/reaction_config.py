"""Helpers for reaction entries stored in workflow configuration files."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

DEFAULT_BIOCHEMICAL_SBO = "SBO:0000176"
DEFAULT_UPPER_BOUND = 1000.0

__all__ = [
    "DEFAULT_BIOCHEMICAL_SBO",
    "DEFAULT_UPPER_BOUND",
    "build_reaction_entry",
    "default_lower_bound",
    "upsert_reaction_entry",
]


def default_lower_bound(equation: str) -> float:
    """Return the default lower bound implied by a config equation string."""
    if "<=>" in equation:
        return -1000.0
    return 0.0


def build_reaction_entry(
    *,
    reaction_id: str,
    name: str,
    equation: str,
    description: str = "",
    subsystem: str = "",
    ec: str = "",
    gpr: str = "",
    lower_bound: float | None = None,
    upper_bound: float = DEFAULT_UPPER_BOUND,
    sbo: str = DEFAULT_BIOCHEMICAL_SBO,
) -> dict[str, Any]:
    """Build and validate a reaction entry compatible with pathway configs."""
    reaction_id = reaction_id.strip()
    name = name.strip()
    equation = equation.strip()

    if not reaction_id:
        raise ValueError("reaction_id is required")
    if not name:
        raise ValueError("name is required")
    if not equation:
        raise ValueError("equation is required")

    if lower_bound is None:
        lower_bound = default_lower_bound(equation)

    return {
        "id": reaction_id,
        "name": name,
        "description": description.strip(),
        "equation": equation,
        "subsystem": subsystem.strip(),
        "ec": ec.strip(),
        "gpr": gpr.strip(),
        "lower_bound": float(lower_bound),
        "upper_bound": float(upper_bound),
        "sbo": sbo.strip() or DEFAULT_BIOCHEMICAL_SBO,
    }


def upsert_reaction_entry(
    config: dict[str, Any],
    reaction_entry: dict[str, Any],
    *,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Return a config copy with ``reaction_entry`` inserted or overwritten."""
    if "id" not in reaction_entry or not str(reaction_entry["id"]).strip():
        raise ValueError("reaction_entry must include a non-empty id")

    updated = deepcopy(config)
    reactions = list(updated.get("reactions", []))
    reaction_id = reaction_entry["id"]
    duplicate_indexes = [
        index
        for index, existing_reaction in enumerate(reactions)
        if existing_reaction.get("id") == reaction_id
    ]

    if duplicate_indexes and not overwrite:
        raise ValueError(f"Reaction with ID {reaction_id!r} already exists")

    if duplicate_indexes:
        reactions = [
            existing_reaction
            for existing_reaction in reactions
            if existing_reaction.get("id") != reaction_id
        ]

    reactions.append(deepcopy(reaction_entry))
    updated["reactions"] = reactions
    return updated
