"""Compatibility wrapper for configuration helpers.

New code should import from :mod:`thg_protocol.config`. This module keeps the
legacy ``functions.config`` import path working during the package migration.
"""

from thg_protocol.config import (
    get_compartments,
    get_model_paths,
    get_project_root,
    load_config,
    resolve_all_compartments,
    resolve_compartment_abbreviation,
)

__all__ = [
    "get_compartments",
    "get_model_paths",
    "get_project_root",
    "load_config",
    "resolve_all_compartments",
    "resolve_compartment_abbreviation",
]
