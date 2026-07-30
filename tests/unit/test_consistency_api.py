from thg_protocol.analysis import reaction_balance


def test_reaction_balance_uses_formula_stoichiometry() -> None:
    water = type("Metabolite", (), {"formula": "H2O"})()
    reaction = type("Reaction", (), {"metabolites": {water: -1}})()
    assert reaction_balance(reaction) == {"H": -2.0, "O": -1.0}
