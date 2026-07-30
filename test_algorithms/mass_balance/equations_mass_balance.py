"""Archived-test compatibility exports for mass-balance primitives."""

from __future__ import annotations

from thg_protocol.model_build.mass_balance import (
    atom10,
    formula_atoms,
    gcd,
    missing_atoms,
    reaction_compare,
    reformulate_glycan_equation,
)

MissingAtom = missing_atoms
RxnCompare = reaction_compare
Reformulation = reformulate_glycan_equation


def mass_balance(*_args, **_kwargs):
    """Placeholder for the solver-backed historical balancing workflow."""
    raise NotImplementedError(
        "full-model balancing is deferred; use formula-level package helpers"
    )


__all__ = [
    "atom10",
    "formula_atoms",
    "gcd",
    "missing_atoms",
    "reaction_compare",
    "reformulate_glycan_equation",
    "MissingAtom",
    "RxnCompare",
    "Reformulation",
    "mass_balance",
]
