"""Compatibility boundary for mass-balance utilities.

Formula-level helpers are maintained in
:mod:`thg_protocol.model_build.mass_balance`. The historical solver-backed
balancer is intentionally not imported or executed from this module.
"""

from __future__ import annotations

from thg_protocol.model_build.mass_balance import (
    atom10,
    eq2mat,
    equation_matrix,
    formula_atoms,
    gcd,
    inarray,
    inv,
    maximumGCD,
    maximum_gcd,
    missing_atoms,
    nullity,
    reaction_compare,
)
from thg_protocol.glycan import glycan_atoms

MissingAtom = missing_atoms
RxnCompare = reaction_compare


def Glycan(glycan_id: str, *, kegg_client=None):
    """Resolve a glycan using an injected KEGG client and record its formula."""
    if kegg_client is None:
        from thg_protocol.services.kegg import KeggClient

        kegg_client = KeggClient()
    return glycan_atoms(glycan_id, client=kegg_client, record_path="Glycans")


def Reformulation(equation: str, *, kegg_client=None) -> str:
    """Reformulate a glycan equation through the package API."""
    if kegg_client is None:
        from thg_protocol.services.kegg import KeggClient

        kegg_client = KeggClient()
    from thg_protocol.model_build.mass_balance import reformulate_glycan_equation

    return reformulate_glycan_equation(equation, client=kegg_client)


def _deferred(*_args, **_kwargs):
    raise NotImplementedError(
        "solver-backed mass balancing is deferred; use "
        "thg_protocol.model_build.mass_balance"
    )


# Solver-backed operations remain deferred; these matrix helpers are pure.
WrapRxnSubsProdParam = UnwrapRxnSubsProdParam = RxnParam2Eq = _deferred
AddMissingAtom = CountAtom = MB_Core = MB_REM = MB_LP = _deferred
RxnBalance2 = Proton = Water = add_extra_compound = _deferred

__all__ = [
    "Glycan",
    "Reformulation",
    "MissingAtom",
    "RxnCompare",
    "atom10",
    "formula_atoms",
    "gcd",
    "missing_atoms",
    "reaction_compare",
    "inarray",
    "eq2mat",
    "nullity",
    "equation_matrix",
    "inv",
    "maximumGCD",
    "maximum_gcd",
    "WrapRxnSubsProdParam",
    "UnwrapRxnSubsProdParam",
    "RxnParam2Eq",
    "AddMissingAtom",
    "CountAtom",
    "MB_Core",
    "MB_REM",
    "MB_LP",
    "RxnBalance2",
    "Proton",
    "Water",
    "add_extra_compound",
]
