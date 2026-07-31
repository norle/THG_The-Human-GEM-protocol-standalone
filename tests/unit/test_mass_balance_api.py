import numpy as np

from thg_protocol.model_build import (
    atom10,
    formula_atoms,
    missing_atoms,
    reaction_compare,
)
from thg_protocol.model_build.mass_balance import (
    balance_equation,
    eq2mat,
    equation_matrix,
    inarray,
    inv,
    maximumGCD,
    nullity,
    reformulate_glycan_equation,
)
from thg_protocol.services.kegg import StaticKeggClient


def test_formula_atoms_and_legacy_vector() -> None:
    assert formula_atoms("C6H12O6") == {"C": 6, "H": 12, "O": 6}
    assert atom10("C6H12O6")[:3] == [6, 12, 6]


def test_mass_balance_primitives_are_deterministic() -> None:
    assert missing_atoms("H2 + O2 -> H2O") == [["O", 1, 1]]
    assert reaction_compare("A + B -> C", "A -> C") == (["B"], [-1])


def test_package_balancer_returns_smallest_positive_coefficients() -> None:
    assert balance_equation("H2 + O2 -> H2O") == ([2.0, 1.0], [2.0])


def test_reformulate_glycan_equation_assigns_symbols_by_element() -> None:
    client = StaticKeggClient(
        pages={
            "https://www.genome.jp/dbget-bin/www_bget?gl:G00001": "C00001",
            "https://www.genome.jp/entry/C00001": "C00001H2O",
        }
    )
    assert reformulate_glycan_equation(
        "G00001 -> G00001", client=client
    ) == "A1B2C1 -> A1B2C1"


def test_legacy_numeric_mass_balance_helpers_are_package_owned() -> None:
    assert inarray([1, 2, 0], [3, 6, 0]) == 3
    assert inarray([1, 2], [3, 5]) == ""

    matrix = equation_matrix("2 H2 + O2 -> 2 H2O")
    assert matrix.shape == (2, 3)
    assert matrix.tolist() == [[4.0, 0.0, -4.0], [0.0, 2.0, -2.0]]
    assert np.array_equal(
        eq2mat("H2 + O2 -> H2O"), equation_matrix("H2 + O2 -> H2O")
    )


def test_nullity_preserves_independent_rows() -> None:
    completed, independent = nullity([[1, 0], [2, 0]])
    assert independent.shape == (1, 2)
    assert completed.shape == (2, 2)


def test_inverse_and_gcd_helpers_are_available_without_solver() -> None:
    assert np.allclose(inv([[2.0, 0.0], [0.0, 4.0]]), [[0.5, 0.0], [0.0, 0.25]])
    assert maximumGCD(["2*K", "4*K", "6*K"], "K", 3) == 6
