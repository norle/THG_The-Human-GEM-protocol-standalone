"""Dependency-light mass-balance primitives."""

from __future__ import annotations

import ast
import math
import re
from collections import defaultdict
from fractions import Fraction
from typing import Any

try:  # Keep package and CLI help imports safe in a no-dependencies wheel check.
    import numpy as np
except ImportError:  # pragma: no cover - exercised by clean-wheel smoke tests
    np = None  # type: ignore[assignment]

from thg_protocol.glycan import resolve_glycan_atoms
from thg_protocol.services.kegg import KeggClientProtocol


def _numpy():
    if np is None:
        raise RuntimeError(
            "numeric mass-balance helpers require the 'numpy' dependency"
        )
    return np


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


def inarray(first: Any, second: Any) -> int | str:
    """Return the common integer multiplier between two vectors.

    This is the dependency-free portion of the historical mass-balance API.
    Zero entries in ``first`` must also be zero in ``second``; an empty or
    non-integral result returns the historical empty-string sentinel.
    """
    numpy = _numpy()
    left = numpy.asarray(first, dtype=float)
    right = numpy.asarray(second, dtype=float)
    if left.shape != right.shape:
        return ""
    mask = ~np.isclose(left, 0)
    if np.any(~mask & ~np.isclose(right, 0)) or not np.any(mask):
        return ""
    ratios = right[mask] / left[mask]
    if not np.allclose(ratios, ratios[0]) or ratios[0] <= 0:
        return ""
    value = float(ratios[0])
    return int(round(value)) if value.is_integer() else ""


def equation_matrix(equation: str) -> np.ndarray:
    """Build an elemental composition matrix for an equation.

    Columns are compounds in left-to-right equation order and rows are the
    elements encountered in those compounds. Stoichiometric coefficients are
    included in the matrix and products have negative signs.
    """
    if equation.count("->") != 1:
        raise ValueError("equation must contain exactly one '->'")
    terms: list[tuple[int, str]] = []
    for side, sign in zip(equation.split("->"), (1, -1), strict=True):
        for raw in side.split("+"):
            token = raw.strip()
            if not token:
                continue
            match = re.fullmatch(r"(?:(\d+(?:\.\d+)?)\s*)?(.+)", token)
            if not match:
                raise ValueError(f"invalid equation term: {token}")
            coefficient = float(match.group(1) or 1) * sign
            terms.append((coefficient, match.group(2)))
    parsed = [formula_atoms(formula) for _, formula in terms]
    if any(not atoms for atoms in parsed):
        raise ValueError("equation contains an invalid formula")
    elements = sorted({element for atoms in parsed for element in atoms})
    numpy = _numpy()
    return numpy.array(
        [
            [coefficient * atoms.get(element, 0)
             for (coefficient, _), atoms in zip(terms, parsed, strict=True)]
            for element in elements
        ],
        dtype=float,
    )


def balance_equation(equation: str) -> tuple[list[float], list[float]]:
    """Return the smallest positive elemental-balance coefficients.

    The equation syntax is the same as
    [`equation_matrix`][thg_protocol.model_build.mass_balance.equation_matrix]; coefficients
    already present in the input are treated as part of the formula token and
    are therefore best supplied as ``2 H2`` rather than ``H2`` with a
    separately fixed coefficient.  A positive null-space vector is required:
    equations that cannot be balanced without adding compounds return two
    empty lists instead of silently changing their chemistry.
    """
    matrix = equation_matrix(equation)
    if matrix.shape[1] == 0:
        return [], []
    numpy = _numpy()
    _, _, vh = numpy.linalg.svd(matrix)
    vector = vh[-1]
    if numpy.all(vector < 0):
        vector = -vector
    if numpy.any(vector <= 1e-10) or not numpy.allclose(
        matrix @ vector, 0, atol=1e-8
    ):
        return [], []

    fractions = [Fraction(float(value)).limit_denominator(10000) for value in vector]
    denominator = math.lcm(*(fraction.denominator for fraction in fractions))
    integers = [
        fraction.numerator * denominator // fraction.denominator
        for fraction in fractions
    ]
    divisor = math.gcd(*[abs(value) for value in integers if value])
    if not divisor:
        return [], []
    values = [float(value // divisor) for value in integers]
    left_count = len(equation.split("->", 1)[0].split("+"))
    return values[:left_count], values[left_count:]


def count_atoms(
    equation: str, add_h: int = 0, water: int = 0, reaction_id: Any = None
) -> tuple[list[float], list[float], str]:
    """Compatibility implementation of the historical ``CountAtom`` helper."""
    del add_h, water, reaction_id
    left, right = balance_equation(equation)
    return left, right, equation


def balance_reaction(equation: str, reaction_id: Any = None) -> tuple[Any, ...]:
    """Return the historical eleven-field reaction-balance result.

    This dependency-free implementation reports an unbalanced equation when
    no positive elemental solution exists.  It does not invent proton or
    water terms; callers that need that chemistry must add them explicitly.
    """
    del reaction_id
    left, right = balance_equation(equation)
    terms = equation.split("->", 1)
    left_ids = [term.strip().split()[-1] for term in terms[0].split("+")]
    right_ids = [term.strip().split()[-1] for term in terms[1].split("+")]
    balanced = bool(left and right)
    if not balanced:
        left = [1.0] * len(left_ids)
        right = [1.0] * len(right_ids)
    return (
        left,
        right,
        0,
        0,
        [],
        [],
        left_ids,
        right_ids,
        equation,
        equation,
        1 if balanced else 2,
    )


# Historical name retained as a small, pure compatibility alias.
eq2mat = equation_matrix


def nullity(matrix: Any) -> tuple[np.ndarray, np.ndarray]:
    """Return a row-independent matrix and its nullity-completion matrix."""
    numpy = _numpy()
    values = numpy.asarray(matrix, dtype=float)
    if values.ndim != 2:
        raise ValueError("matrix must be two-dimensional")
    rank = numpy.linalg.matrix_rank(values)
    independent: list[np.ndarray] = []
    current_rank = 0
    for row in values:
        candidate = (
            numpy.vstack(independent + [row]) if independent else row[None, :]
        )
        new_rank = numpy.linalg.matrix_rank(candidate)
        if new_rank > current_rank:
            independent.append(row)
            current_rank = new_rank
    independent_matrix = numpy.asarray(independent, dtype=float)
    if independent_matrix.size == 0:
        independent_matrix = numpy.empty((0, values.shape[1]))
    completion = numpy.zeros((max(values.shape[1] - rank, 0), values.shape[1]))
    for index in range(completion.shape[0]):
        completion[index, -(index + 1)] = 1
    return (
        np.vstack([independent_matrix, completion]),
        independent_matrix,
    )


def inv(matrix: Any) -> np.ndarray:
    """Return the inverse of a square numeric matrix."""
    numpy = _numpy()
    values = numpy.asarray(matrix, dtype=float)
    if values.ndim != 2 or values.shape[0] != values.shape[1]:
        raise ValueError("matrix must be square")
    return numpy.linalg.inv(values)


def maximum_gcd(values: Any, variable: str, value: Any) -> int:
    """Return the GCD of integer expressions after substituting ``variable``."""
    evaluated: list[int] = []

    def calculate(expression: str) -> float:
        operators = {
            ast.Add: lambda left, right: left + right,
            ast.Sub: lambda left, right: left - right,
            ast.Mult: lambda left, right: left * right,
            ast.Div: lambda left, right: left / right,
        }

        def visit(node: ast.AST) -> float:
            if isinstance(node, ast.Expression):
                return visit(node.body)
            if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
                return float(node.value)
            if isinstance(node, ast.UnaryOp) and isinstance(
                node.op, (ast.UAdd, ast.USub)
            ):
                result = visit(node.operand)
                return result if isinstance(node.op, ast.UAdd) else -result
            if isinstance(node, ast.BinOp) and type(node.op) in operators:
                return operators[type(node.op)](visit(node.left), visit(node.right))
            raise ValueError("unsupported expression")

        return visit(ast.parse(expression, mode="eval"))

    for expression in values:
        text = str(expression).replace(variable, str(value))
        try:
            evaluated.append(int(round(calculate(text))))
        except (SyntaxError, ValueError, TypeError) as error:
            raise ValueError(f"invalid integer expression: {expression}") from error
    if not evaluated:
        return 0
    return math.gcd(*evaluated)


maximumGCD = maximum_gcd


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
    elements = dict.fromkeys(
        group[0][0]
        for identifier in identifiers
        for group in formulas[identifier]
    )
    letters = {
        element: chr(ord("A") + index)
        for index, element in enumerate(elements)
    }

    def render(side: str) -> str:
        values = []
        for token in side.split("+"):
            token = token.strip()
            values.append(
                "".join(
                    f"{letters[group[0][0]]}{group[0][1]}"
                    for group in formulas[token]
                )
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
    "inarray",
    "equation_matrix",
    "balance_equation",
    "count_atoms",
    "balance_reaction",
    "eq2mat",
    "nullity",
    "inv",
    "maximum_gcd",
    "maximumGCD",
]
