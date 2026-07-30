"""Compatibility boundary for model consistency checks."""

from __future__ import annotations

from thg_protocol.analysis.consistency import (
    dead_end_metabolites,
    orphan_metabolites,
    reaction_balance,
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


def _deferred(*_args, **_kwargs):
    raise NotImplementedError(
        "solver-backed MEMOTE consistency checks are deferred; use "
        "thg_protocol.analysis consistency APIs"
    )


test_inconsistent_min_stoichiometry = _deferred
test_detect_energy_generating_cycles = _deferred
test_reaction_charge_balance = _deferred
test_reaction_mass_balance = _deferred
test_blocked_reactions = _deferred
test_find_stoichiometrically_balanced_cycles = _deferred
test_find_disconnected = _deferred
test_find_metabolites_not_produced_with_open_bounds = _deferred
test_find_metabolites_not_consumed_with_open_bounds = _deferred
test_find_reactions_unbounded_flux_default_condition = _deferred

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
]
