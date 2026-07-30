"""Dependency-light mass-balance primitives."""

from __future__ import annotations

import math
import re
from collections import defaultdict
from typing import Any

from thg_protocol.glycan import resolve_glycan_atoms
from thg_protocol.services.kegg import KeggClientProtocol


def gcd(left: int, right: int) -> int:
    """Return the greatest common divisor of two integers."""
    return math.gcd(int(left), int(right))


def formula_atoms(formula: str) -> dict[str, int]:
    """Parse an elemental formula into an element/count mapping."""
    if not isinstance(formula, str) or not formula:
        return {}
    atoms: dict[str, int] = defaultdict(int)
    consumed = ""
    for symbol, count in re.findall(r"([A-Z][a-z]?)(\d*)", formula):
        consumed += symbol + count
        atoms[symbol] += int(count) if count else 1
    return dict(atoms) if consumed == formula else {}


def atom10(formula: str) -> list[int]:
    """Return legacy C/H/O/N/P/S/K/Ca/Na/Fe/X/R counts."""
    atoms = formula_atoms(formula)
    return [
        atoms.get(symbol, 0)
        for symbol in ("C", "H", "O", "N", "P", "S", "K", "Ca", "Na", "Fe", "X", "R")
    ]


def missing_atoms(equation: str) -> list[list[Any]]:
    """Report net elemental differences in ``substrates -> products``."""
    sides = equation.split("->")
    if len(sides) != 2:
        raise ValueError("equation must contain exactly one '->'")
    totals: dict[str, int] = defaultdict(int)
    for sign, side in ((1, sides[0]), (-1, sides[1])):
        for formula in (part.strip() for part in side.split("+") if part.strip()):
            for element, count in formula_atoms(formula).items():
                totals[element] += sign * count
    return [[element, value, value] for element, value in totals.items() if value]


def reaction_compare(first: str, second: str) -> tuple[list[str], list[int]]:
    """Return species newly present in ``first`` relative to ``second``."""
    def sides(equation: str) -> tuple[list[str], list[str]]:
        left, right = equation.replace(" ", "").split("->", 1)
        return left.split("+") if left else [], right.split("+") if right else []

    first_sides, second_sides = sides(first), sides(second)
    new_left = [value for value in first_sides[0] if value not in second_sides[0]]
    new_right = [value for value in first_sides[1] if value not in second_sides[1]]
    return new_left + new_right, [-1] * len(new_left) + [1] * len(new_right)


def reformulate_glycan_equation(
    equation: str,
    *,
    client: KeggClientProtocol,
) -> str:
    """Replace glycan IDs in an equation with symbolic formula letters."""
    if equation.count("->") != 1:
        raise ValueError("equation must contain exactly one '->'")
    identifiers: list[str] = []
    formulas: dict[str, list[list[list[str | int]]]] = {}
    for side in equation.split("->"):
        for token in (part.strip() for part in side.split("+") if part.strip()):
            if token in formulas:
                continue
            _, _, atoms = resolve_glycan_atoms(token, client)
            if not atoms:
                raise ValueError(f"could not resolve glycan formula: {token}")
            identifiers.append(token)
            formulas[token] = atoms
    letters = {
        identifier: chr(ord("A") + index)
        for index, identifier in enumerate(dict.fromkeys(identifiers))
    }

    def render(side: str) -> str:
        values = []
        for token in side.split("+"):
            token = token.strip()
            values.append(
                "".join(f"{letters[token]}{group[0][1]}" for group in formulas[token])
            )
        return " + ".join(values)

    left, right = equation.split("->", 1)
    return f"{render(left)} -> {render(right)}"


__all__ = [
    "atom10",
    "formula_atoms",
    "gcd",
    "missing_atoms",
    "reaction_compare",
    "reformulate_glycan_equation",
]
