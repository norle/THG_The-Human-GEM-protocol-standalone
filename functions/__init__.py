"""Compatibility package for legacy ``functions`` imports."""

from __future__ import annotations

from importlib import import_module
from typing import Any

from .config import get_model_paths, load_config, resolve_all_compartments

_PATHWAY_BUILDER_EXPORTS = {
    "add_compartment",
    "build_reaction_from_config",
    "check_pathway_exists",
    "create_compartment_metabolites",
    "create_compartment_reactions",
    "find_metabolite_by_annotation",
    "find_metabolite_robust",
    "get_next_metabolite_id",
    "get_next_reaction_id",
    "parse_reaction_equation",
    "parse_universal_reaction",
    "select_pathway_metabolites",
    "substitute_compartment_abbreviations",
}

__all__ = [
    "get_model_paths",
    "load_config",
    "resolve_all_compartments",
    *_PATHWAY_BUILDER_EXPORTS,
]


def __getattr__(name: str) -> Any:
    """Lazy-load legacy pathway helpers only when requested."""
    if name in _PATHWAY_BUILDER_EXPORTS:
        return getattr(import_module("thg_protocol.pathway"), name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
