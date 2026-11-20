"""Gap-filling solver choice and the HiGHS (optlang ``hybrid``) path."""

import cobra
import pytest
from cobra.util.solver import solvers

from thg_protocol.gapfill import solvers as solver_module
from thg_protocol.gapfill.ptr import (
    ComponentCoverage,
    compute_coverage,
    generate_ptr_candidates,
    network_components,
    select_unblockers,
)
from thg_protocol.gapfill.solvers import default_solver, resolve_solver

needs_highs = pytest.mark.skipif(
    "hybrid" not in solvers, reason="HiGHS (highspy and osqp) not installed"
)


@pytest.fixture
def gurobi(monkeypatch):
    """Pretend Gurobi is or is not usable."""

    def set_usable(usable):
        monkeypatch.setattr(solver_module, "gurobi_usable", lambda: usable)

    return set_usable


def test_unset_solver_keeps_cobras_default():
    from cobra.util.solver import interface_to_str

    assert resolve_solver(None) == interface_to_str(cobra.Configuration().solver)


@needs_highs
def test_auto_falls_back_to_highs_without_gurobi(gurobi):
    gurobi(False)
    assert resolve_solver("auto") == "hybrid"


def test_auto_prefers_gurobi_when_usable(gurobi, monkeypatch):
    gurobi(True)
    monkeypatch.setitem(solvers, "gurobi", object())
    assert resolve_solver("auto") == "gurobi"


def test_explicit_gurobi_never_falls_back(gurobi, monkeypatch):
    gurobi(False)
    monkeypatch.setitem(solvers, "gurobi", object())
    with pytest.raises(ValueError, match="license"):
        resolve_solver("gurobi")


@needs_highs
def test_highs_maps_to_the_hybrid_interface():
    assert resolve_solver("highs") == "hybrid"


def test_unknown_solver_is_rejected():
    with pytest.raises(ValueError, match="unknown gapfill solver"):
        resolve_solver("cplex")


@needs_highs
def test_default_solver_applies_inside_the_block_only():
    before = cobra.Configuration().solver
    with default_solver("hybrid"):
        assert cobra.Model("m").solver.interface.__name__ == "optlang.hybrid_interface"
    assert cobra.Configuration().solver is before


def overlapping_coverage():
    return [
        ComponentCoverage(
            2,
            ["a", "b", "c", "d"],
            [],
            {"P1": ["a", "b"], "P2": ["b", "c"], "P3": ["c", "d"]},
        )
    ]


@needs_highs
def test_highs_milp_is_exact_and_recorded():
    from optlang import hybrid_interface

    selection = select_unblockers(
        overlapping_coverage(),
        tradeoff_lambda=0.01,
        budget=10,
        interface=hybrid_interface,
    )
    assert selection.status == "solved"
    assert selection.selected == ["P1", "P3"]
    assert selection.solver["mip_gap"] == 0.0
    assert selection.solver["interface"] == "hybrid_interface"


@needs_highs
def test_highs_tie_break_prefers_lower_rank_then_id():
    from optlang import hybrid_interface

    coverage = [ComponentCoverage(2, ["a"], [], {"P2": ["a"], "P1": ["a"]})]
    by_id = select_unblockers(
        coverage, tradeoff_lambda=0.01, budget=10, interface=hybrid_interface
    )
    by_rank = select_unblockers(
        coverage,
        tradeoff_lambda=0.01,
        budget=10,
        interface=hybrid_interface,
        ranks={"P1": 1, "P2": 0},
    )
    assert by_id.selected == ["P1"]
    assert by_rank.selected == ["P2"]


def linked_islands():
    """Island e makes surplus Ae, island m lacks Am: either transport runs both."""
    model = cobra.Model("linked")
    stoichiometry = {
        "I1": {"Ae": -1, "Be": 1},
        "I2": {"Be": -1, "Ae": 2},
        "J1": {"Am": -1, "Bm": 1},
        "J2": {"Bm": -2, "Am": 1},
    }
    metabolites = {
        mid: cobra.Metabolite(mid, compartment=mid[-1])
        for stoich in stoichiometry.values()
        for mid in stoich
    }
    model.add_metabolites(list(metabolites.values()))
    for rid, stoich in stoichiometry.items():
        reaction = cobra.Reaction(rid, lower_bound=0.0, upper_bound=1000.0)
        model.add_reactions([reaction])
        reaction.add_metabolites({metabolites[mid]: v for mid, v in stoich.items()})
    return model


@needs_highs
@pytest.mark.parametrize("workers", [1, 2])
def test_highs_coverage_runs_in_workers_without_the_default_solver(workers):
    with default_solver("hybrid"):
        model = linked_islands()
    components = network_components(model)
    candidates = generate_ptr_candidates(
        model, [("e", "m")], ["A", "B", "C"], components
    )
    coverage = compute_coverage(model, candidates, components, workers=workers)
    assert [item.coverage for item in coverage] == [
        {"GAPFILL_PTR_Ae_Am": ["I1", "I2"], "GAPFILL_PTR_Be_Bm": ["I1", "I2"]},
        {"GAPFILL_PTR_Ae_Am": ["J1", "J2"], "GAPFILL_PTR_Be_Bm": ["J1", "J2"]},
    ]
