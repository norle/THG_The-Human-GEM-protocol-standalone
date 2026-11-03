import cobra

from thg_protocol.analysis.consistency import (
    charge_balance,
    dead_end_metabolites,
    metabolites_not_consumed,
    metabolites_not_produced,
    orphan_metabolites,
    reaction_balance,
    stoichiometrically_balanced_cycles,
    unassessable_reactions,
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
    assert unbalanced_reactions(model) == ["R_unbalanced"]
    assert charge_balance(missing) == {"charge": 0.0, "missing": ["missing_c"]}
    assert unbalanced_reactions_by_charge(model) == ["R_missing_charge"]
    assert orphan_metabolites(model) == ["orphan_c"]
    assert dead_end_metabolites(model) == ["a_c", "c_c"]
    assert metabolites_not_produced(model) == ["a_c"]
    assert metabolites_not_consumed(model) == ["c_c"]


def _chain(bounds):
    """EX_a <-> a <-> b <-> EX_b with the given (R1, EX_a, EX_b) bounds."""
    model = cobra.Model("chain")
    a = cobra.Metabolite("a_c", formula="C", charge=0, compartment="c")
    b = cobra.Metabolite("b_c", formula="C", charge=0, compartment="c")
    r1, ex_a, ex_b = (
        cobra.Reaction(name, lower_bound=lo, upper_bound=hi)
        for name, (lo, hi) in zip(("R1", "EX_a", "EX_b"), bounds, strict=True)
    )
    r1.add_metabolites({a: -1, b: 1})
    ex_a.add_metabolites({a: -1})
    ex_b.add_metabolites({b: -1})
    model.add_reactions([ex_a, r1, ex_b])
    return model


def test_reversible_reactions_make_and_use_their_metabolites():
    model = _chain([(-10, 10), (-10, 10), (-10, 10)])
    assert dead_end_metabolites(model) == []
    assert metabolites_not_produced(model) == []
    assert metabolites_not_consumed(model) == []


def test_directionality_still_creates_dead_ends():
    # a can only be consumed (EX_a is secretion-only, R1 forward-only).
    model = _chain([(0, 10), (0, 10), (-10, 10)])
    assert dead_end_metabolites(model) == ["a_c"]
    assert metabolites_not_produced(model) == ["a_c"]


def test_reaction_run_backwards_counts_as_reversed():
    # R1 only runs b -> a (bounds <= 0), so a is produced, never consumed by it.
    model = _chain([(-10, 0), (0, 10), (0, 10)])
    assert metabolites_not_consumed(model) == []
    assert dead_end_metabolites(model) == ["b_c"]


def test_boundary_reactions_are_not_reported_as_unbalanced():
    model = _chain([(-10, 10), (-10, 10), (-10, 10)])
    assert unbalanced_reactions(model) == []


def test_reactions_with_missing_formulas_are_unassessable_not_unbalanced():
    model = _chain([(-10, 10), (-10, 10), (-10, 10)])
    model.metabolites.b_c.formula = ""
    assert unbalanced_reactions(model) == []
    assert unassessable_reactions(model) == ["R1"]


def test_forced_flux_reaction_does_not_make_cycle_check_infeasible():
    model = _chain([(1, 10), (-10, 10), (-10, 10)])
    assert stoichiometrically_balanced_cycles(model) == []


def test_closed_boundary_cycle_is_still_reported():
    model = _chain([(0, 10), (-10, 10), (-10, 10)])
    back = cobra.Reaction("R2", lower_bound=0, upper_bound=10)
    back.add_metabolites({model.metabolites.b_c: -1, model.metabolites.a_c: 1})
    model.add_reactions([back])
    assert stoichiometrically_balanced_cycles(model) == ["R1", "R2"]


def test_cycle_check_respects_reaction_direction_and_leaves_model_unchanged():
    model = _chain([(-10, 0), (-10, 10), (-10, 10)])
    back = cobra.Reaction("R2", lower_bound=0, upper_bound=10)
    back.add_metabolites({model.metabolites.b_c: -1, model.metabolites.a_c: 1})
    model.add_reactions([back])
    # R1 runs b -> a only and R2 runs b -> a only: no cycle.
    assert stoichiometrically_balanced_cycles(model) == []
    assert model.reactions.EX_a.bounds == (-10, 10)
    assert model.reactions.R1.bounds == (-10, 0)
