"""KEGG-backed glycan formula parsing for mass-balance workflows."""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import TypeAlias

from thg_protocol.services.kegg import KeggClientProtocol

AtomGroup: TypeAlias = list[list[str | int]]


def parse_formula(formula: str) -> list[AtomGroup]:
    """Convert a molecular formula to the legacy atom-group contract.

    The legacy reformulation code consumes each element as
    ``group[0][0]`` (symbol) and ``group[0][1]`` (count). Keeping that shape
    here allows both old mass-balance copies to use one tested parser.
    """
    atoms: list[AtomGroup] = []
    consumed = ""
    for match in re.finditer(r"([A-Z][a-z]?)(\d*)", formula):
        symbol, count = match.groups()
        atoms.append([[symbol, int(count) if count else 1]])
        consumed += match.group(0)
    if not atoms or consumed != formula:
        return []
    return atoms


def resolve_glycan_atoms(
    glycan_id: str,
    client: KeggClientProtocol,
) -> tuple[str, str, list[AtomGroup]]:
    """Resolve a KEGG glycan ID to its primary compound and atom groups."""
    glycan_page = client.get_page(
        "https://www.genome.jp/dbget-bin/www_bget?gl:" + glycan_id
    )
    compound_match = re.search(r"\b(C\d+)\b", str(glycan_page))
    if compound_match is None:
        return "", "", []
    compound_id = compound_match.group(1)
    compound_page = client.get_page("https://www.genome.jp/entry/" + compound_id)
    formula_match = re.search(
        r"\b(C(?:\d+)?(?:[A-Z][a-z]?\d*)+)\b", str(compound_page)
    )
    if formula_match is None:
        return compound_id, "", []
    formula = formula_match.group(1)
    return compound_id, formula, parse_formula(formula)


def normalize_identifiers(value: str | Sequence[str]) -> list[str]:
    """Normalize one or more glycan IDs without treating a string as iterable."""
    if isinstance(value, str):
        return [value.strip()]
    return [str(identifier).strip() for identifier in value]
