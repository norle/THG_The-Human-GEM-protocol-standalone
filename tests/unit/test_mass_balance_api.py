from thg_protocol.model_build import (
    atom10,
    formula_atoms,
    missing_atoms,
    reaction_compare,
)


def test_formula_atoms_and_legacy_vector() -> None:
    assert formula_atoms("C6H12O6") == {"C": 6, "H": 12, "O": 6}
    assert atom10("C6H12O6")[:3] == [6, 12, 6]


def test_mass_balance_primitives_are_deterministic() -> None:
    assert missing_atoms("H2 + O2 -> H2O") == [["O", 1, 1]]
    assert reaction_compare("A + B -> C", "A -> C") == (["B"], [-1])
