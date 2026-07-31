"""Compatibility boundary for model consistency checks."""

from __future__ import annotations

from thg_protocol.analysis.consistency import (
    blocked_reactions,
    charge_balance,
    dead_end_metabolites,
    metabolites_not_consumed,
    metabolites_not_produced,
    orphan_metabolites,
    reaction_balance,
    stoichiometrically_balanced_cycles,
    unbalanced_reactions_by_charge,
    unbounded_reactions,
    unbalanced_reactions,
)


def test_reaction_balance(eq):
    """Return the historical tuple for a formula equation when balanced."""
    from thg_protocol.model_build.mass_balance import missing_atoms

    imbalance = missing_atoms(eq)
    return ([], [], eq) if imbalance else ([1.0], [1.0], eq)


def imbalance_test(reaction, formulas):
    del formulas
    return reaction_balance(reaction)


def test_stoichiometric_consistency(model):
    return not unbalanced_reactions(model)


def test_unconserved_metabolites(model):
    return dead_end_metabolites(model)


def test_find_orphans(model):
    return orphan_metabolites(model)


def test_find_deadends(model):
    return dead_end_metabolites(model)


def test_inconsistent_min_stoichiometry(model):
    return [[reaction_id] for reaction_id in unbalanced_reactions(model)]


def test_detect_energy_generating_cycles(model, met):
    del met
    return [] if not stoichiometrically_balanced_cycles(model) else stoichiometrically_balanced_cycles(model)


def test_reaction_charge_balance(model):
    return unbalanced_reactions_by_charge(model)


def test_reaction_mass_balance(model):
    return unbalanced_reactions(model)


def test_blocked_reactions(model):
    return blocked_reactions(model)


def test_find_stoichiometrically_balanced_cycles(model):
    return stoichiometrically_balanced_cycles(model)


def test_find_disconnected(model):
    return orphan_metabolites(model)


def test_find_metabolites_not_produced_with_open_bounds(model):
    return metabolites_not_produced(model)


def test_find_metabolites_not_consumed_with_open_bounds(model):
    return metabolites_not_consumed(model)


def test_find_reactions_unbounded_flux_default_condition(model):
    return unbounded_reactions(model)

__all__ = [
    "dead_end_metabolites",
    "imbalance_test",
    "orphan_metabolites",
    "reaction_balance",
    "test_find_deadends",
    "test_find_orphans",
    "test_reaction_balance",
    "test_stoichiometric_consistency",
    "test_unconserved_metabolites",
    "unbalanced_reactions",
    "test_inconsistent_min_stoichiometry",
    "test_detect_energy_generating_cycles",
    "test_reaction_charge_balance",
    "test_reaction_mass_balance",
    "test_blocked_reactions",
    "test_find_stoichiometrically_balanced_cycles",
    "test_find_disconnected",
    "test_find_metabolites_not_produced_with_open_bounds",
    "test_find_metabolites_not_consumed_with_open_bounds",
    "test_find_reactions_unbounded_flux_default_condition",
]
