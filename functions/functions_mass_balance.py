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


from thg_protocol.model_build.mass_balance import (
    balance_equation,
    balance_reaction,
    count_atoms,
)


def AddMissingAtom(equation):
    """Preserve the equation; balancing never invents chemical species."""
    return equation


def CountAtom(eq, AddH=0, H2O=0, RxnID=None):
    return count_atoms(eq, AddH, H2O, RxnID)


MB_Core = CountAtom
MB_REM = CountAtom
MB_LP = CountAtom


def RxnBalance2(eq, RxnID=None):
    return balance_reaction(eq, RxnID)


def RxnParam2Eq(Reaction, MetList, MetEquiv):
    """Build an equation from the historical reaction/metabolite objects."""
    del MetEquiv
    substrates = Reaction.Substrate()
    products = Reaction.Product()

    def formula(item):
        metabolite = MetList[item[2]]
        return metabolite.Formula1()

    left = " + ".join(f"{item[0]} {formula(item)}" for item in substrates)
    right = " + ".join(f"{item[0]} {formula(item)}" for item in products)
    equation = f"{left} -> {right}"
    return equation, 1 if left and right else 0


def WrapRxnSubsProdParam(Reaction, MetList, MetEquiv):
    del MetEquiv
    return (
        {MetList[item[2]].Formula1(): [1, MetList[item[2]].ID1()] for item in Reaction.Substrate()},
        {MetList[item[2]].Formula1(): [1, MetList[item[2]].ID1()] for item in Reaction.Product()},
    )


def UnwrapRxnSubsProdParam(Reaction, LibIni, IthRxnMB):
    del Reaction
    for side, coefficients in zip(LibIni, IthRxnMB[:2]):
        for formula, coefficient in zip(side, coefficients):
            if formula in side:
                side[formula][0] = coefficient
    return LibIni


def Proton(isH, Reaction, time, MetIdent, MetList, EF, specialCompounds):
    del isH, Reaction, time, MetIdent, MetList, EF
    return specialCompounds


def Water(isW, Reaction, time, MetIdent, MetList, EF, specialCompounds):
    del isW, Reaction, time, MetIdent, MetList, EF
    return specialCompounds


def add_extra_compound(new_compound, lib, time, EF, specialCompounds):
    del time, EF
    specialCompounds.append(new_compound)
    return lib, specialCompounds

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
    "balance_equation",
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
