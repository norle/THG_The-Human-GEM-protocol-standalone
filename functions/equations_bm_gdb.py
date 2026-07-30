"""Compatibility exports for the archived equation/mass-balance module.

The historical implementation performed glycan lookups and reformulation at
import time while loading solver and scientific-computing dependencies. The
maintained implementations live in :mod:`thg_protocol.model_build.mass_balance`
and are imported lazily by the compatibility module.
"""

from __future__ import annotations

from functions.functions_mass_balance import (
    Glycan,
    Reformulation,
    RxnCompare,
    atom10,
    formula_atoms,
    gcd,
    missing_atoms,
    reaction_compare,
)

MissingAtom = missing_atoms

__all__ = [
    "Glycan",
    "Reformulation",
    "RxnCompare",
    "atom10",
    "formula_atoms",
    "gcd",
    "missing_atoms",
    "MissingAtom",
    "reaction_compare",
]
