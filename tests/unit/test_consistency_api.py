import cobra

from thg_protocol.analysis.consistency import (
    charge_balance,
    dead_end_metabolites,
    metabolites_not_consumed,
    metabolites_not_produced,
    orphan_metabolites,
    reaction_balance,
    unbalanced_reactions,
    unbalanced_reactions_by_charge,
)


def test_reaction_balance_uses_formula_stoichiometry() -> None:
    water = type("Metabolite", (), {"formula": "H2O"})()
    reaction = type("Reaction", (), {"metabolites": {water: -1}})()
    assert reaction_balance(reaction) == {"H": -2.0, "O": -1.0}


def test_consistency_reports_use_explicit_structural_semantics() -> None:
    model = cobra.Model("consistency")
    a = cobra.Metabolite("a_c", formula="H2", charge=0, compartment="c")
    b = cobra.Metabolite("b_c", formula="H2", charge=0, compartment="c")
    c = cobra.Metabolite("c_c", formula="O2", charge=0, compartment="c")
    missing_charge = cobra.Metabolite("missing_c", formula="H2", compartment="c")
    orphan = cobra.Metabolite("orphan_c", formula="H2", compartment="c")
    balanced = cobra.Reaction("R_balanced")
    balanced.add_metabolites({a: -1, b: 1})
    unbalanced = cobra.Reaction("R_unbalanced")
    unbalanced.add_metabolites({a: -1, c: 1})
    missing = cobra.Reaction("R_missing_charge")
    missing.add_metabolites({b: -1, missing_charge: 1})
    boundary = cobra.Reaction("EX_missing_c", lower_bound=-1000, upper_bound=1000)
    boundary.add_metabolites({missing_charge: -1})
    model.add_reactions([balanced, unbalanced, missing, boundary])
    model.add_metabolites([orphan])

    assert reaction_balance(balanced) == {}
    assert unbalanced_reactions(model) == ["EX_missing_c", "R_unbalanced"]
    assert charge_balance(missing) == {"charge": 0.0, "missing": ["missing_c"]}
    assert unbalanced_reactions_by_charge(model) == ["R_missing_charge"]
    assert orphan_metabolites(model) == ["orphan_c"]
    assert dead_end_metabolites(model) == ["a_c", "c_c"]
    assert metabolites_not_produced(model) == ["a_c"]
    assert metabolites_not_consumed(model) == ["c_c"]
