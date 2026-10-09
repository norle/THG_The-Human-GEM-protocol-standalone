"""Putative-transport (sink-MILP) gapfill phases on small COBRApy models."""

import math
import random
import re

import cobra
import pytest

from thg_protocol.gapfill import apply_gapfill_plan, generate_gapfill_plan
from thg_protocol.gapfill.ptr import (
    ComponentCoverage,
    PtrCandidate,
    compute_coverage,
    generate_ptr_candidates,
    network_components,
    run_sink_milp,
    select_connectors,
    select_unblockers,
    unblockable,
)


def build(reactions, *, reversible=(), compartments=None, unused=()):
    """Build a model from ``{reaction_id: {metabolite_id: coefficient}}``.

    Compartments come from the trailing lowercase suffix unless overridden.
    """
    compartments = compartments or {}
    model = cobra.Model("ptr")
    metabolites = {}
    for metabolite_id in [
        *{mid for stoich in reactions.values() for mid in stoich},
        *unused,
    ]:
        if metabolite_id not in metabolites:
            suffix = re.search(r"[a-z]+$", metabolite_id)
            metabolites[metabolite_id] = cobra.Metabolite(
                metabolite_id,
                compartment=compartments.get(
                    metabolite_id, suffix.group(0) if suffix else ""
                ),
            )
    model.add_metabolites(sorted(metabolites.values(), key=lambda met: met.id))
    for reaction_id, stoich in reactions.items():
        reaction = cobra.Reaction(
            reaction_id,
            lower_bound=-1000.0 if reaction_id in reversible else 0.0,
            upper_bound=1000.0,
        )
        model.add_reactions([reaction])
        reaction.add_metabolites(
            {model.metabolites.get_by_id(mid): value for mid, value in stoich.items()}
        )
    return model


def candidates_of(model, connections=(("c", "e"),), types=("A", "B", "C")):
    return generate_ptr_candidates(
        model, list(connections), list(types), network_components(model)
    )


def two_islands():
    """Main island Xc/Yc cycle, small island Xe/We cycle: no dead ends."""
    return build(
        {
            "R1": {"Xc": -1, "Yc": 1},
            "R2": {"Yc": -1, "Xc": 1},
            "R3": {"Xe": -1, "We": 1},
            "R4": {"We": -1, "Xe": 1},
            "R5": {"Yc": -1, "Zc": 1},
        }
    )


def main_with_dead_ends():
    """One island with c and e metabolites: Ac substrate, Ae product dead end."""
    return build(
        {
            "R1": {"Ac": -1, "Bc": 1},
            "R2": {"Bc": -1, "Cc": 1},
            "R3": {"Cc": -1, "Bc": 1},
            "R4": {"Bc": -1, "Ce": 1},
            "R5": {"Ce": -1, "Bc": 1},
            "R6": {"Ce": -1, "Ae": 1},
        }
    )


def test_components_number_main_first():
    model = two_islands()
    model.add_metabolites([cobra.Metabolite("Qc", compartment="c")])
    components = network_components(model)
    assert components.of["Xc"] == components.of["R5"] == 1
    assert components.of["Xe"] == components.of["R3"] == 2
    assert "Qc" not in components.of
    assert components.sizes == {1: 6, 2: 4}


def test_cross_component_pair_is_a_candidate_of_any_type():
    (candidate,) = candidates_of(two_islands())
    assert candidate == PtrCandidate(
        met1="Xc",
        met2="Xe",
        base="X",
        compartments=("c", "e"),
        components=(1, 2),
        type="C",
        reaction_id="GAPFILL_PTR_Xc_Xe",
    )
    assert PtrCandidate.from_dict(candidate.to_dict()) == candidate


def test_main_component_pair_needs_a_dead_end():
    candidates = candidates_of(main_with_dead_ends())
    assert [(item.met1, item.met2, item.type) for item in candidates] == [
        ("Ac", "Ae", "A")
    ]
    assert candidates[0].components == (1, 1)


def test_pairs_outside_allowed_connections_are_dropped():
    assert candidates_of(two_islands(), connections=[("c", "m")]) == []


def test_existing_transport_suppresses_candidate():
    model = main_with_dead_ends()
    reaction = cobra.Reaction("T", lower_bound=-1000.0, upper_bound=1000.0)
    model.add_reactions([reaction])
    reaction.add_metabolites({model.metabolites.Ac: -1, model.metabolites.Ae: 1})
    (candidate,) = candidates_of(model)
    assert candidate.present


def test_metabolite_without_suffix_uses_compartment_attribute():
    model = build(
        {
            "R1": {"GLC1": -1, "Yc": 1},
            "R2": {"Yc": -1, "GLC1": 1},
            "R3": {"GLC1e": -1, "We": 1},
            "R4": {"We": -1, "GLC1e": 1},
        },
        compartments={"GLC1": "c"},
    )
    (candidate,) = candidates_of(model)
    assert (candidate.met1, candidate.met2) == ("GLC1", "GLC1e")
    assert candidate.base == "GLC1"
    assert candidate.compartments == ("c", "e")


@pytest.mark.parametrize("types", [["A", "B"], ["C"]])
def test_candidate_types_filter(types):
    found = candidates_of(two_islands(), types=types)
    assert [item.type for item in found] == [t for t in ["C"] if t in types]


def ptr(base, components, kind, compartments=("c", "e")):
    met1, met2 = (f"{base}{compartment}" for compartment in compartments)
    return PtrCandidate(
        met1,
        met2,
        base,
        compartments,
        components,
        kind,
        f"GAPFILL_PTR_{met1}_{met2}",
    )


def test_connectors_join_every_component_once():
    candidates = [
        ptr("X", (1, 2), "C"),
        ptr("Y", (1, 2), "A"),
        ptr("Z", (2, 3), "B"),
        ptr("W", (1, 3), "C"),
    ]
    assert [item.base for item in select_connectors(candidates)] == ["Y", "Z"]


def test_connector_prefers_type_a_then_base():
    candidates = [
        ptr("Q", (1, 2), "B"),
        ptr("N", (1, 2), "A"),
        ptr("M", (1, 2), "A", ("c", "m")),
        ptr("M", (1, 2), "A"),
    ]
    (connector,) = select_connectors(candidates)
    assert (connector.met1, connector.met2) == ("Mc", "Me")


def test_main_only_candidates_are_never_connectors():
    assert select_connectors([ptr("A", (1, 1), "A")]) == []


def _fva_unblocked(model, epsilon):
    """Oracle: cobra's FVA, counting a reaction that reaches epsilon either way.

    Forcing a bound to epsilon is not used: GLPK accepts lb = 1e-4 on
    reactions whose maximum flux is exactly 0.
    """
    from cobra.flux_analysis import flux_variability_analysis

    ranges = flux_variability_analysis(model, fraction_of_optimum=0)
    threshold = 0.99 * epsilon
    return {
        rid
        for rid, row in ranges.iterrows()
        if row["maximum"] >= threshold or row["minimum"] <= -threshold
    }


@pytest.mark.parametrize("seed", range(12))
def test_unblockable_matches_per_reaction_fba(seed):
    rng = random.Random(seed)
    metabolites = [f"M{index}c" for index in range(7)]
    reactions = {}
    for index in range(12):
        chosen = rng.sample(metabolites, rng.choice([1, 2, 2, 3]))
        reactions[f"R{index}"] = {mid: rng.choice([-2, -1, 1, 1, 2]) for mid in chosen}
    model = build(
        reactions, reversible={rid for rid in reactions if rng.random() < 0.4}
    )
    epsilon = 1e-4
    expected = _fva_unblocked(model, epsilon)
    assert unblockable(model, set(reactions), epsilon) == expected


def surplus_island():
    """Main exports Ac; the island cycle Ae -> Be -> 2 Ae only runs with a drain.

    The island has no dead ends, so temporary sinks cannot unblock it.
    """
    return build(
        {
            "EXA": {"Ac": -1},
            "R1": {"Ac": -1, "Dc": 1},
            "EXD": {"Dc": -1},
            "I1": {"Ae": -1, "Be": 1},
            "I2": {"Be": -1, "Ae": 2},
        },
        reversible={"EXA"},
    )


def coverage_of(model, **kwargs):
    components = network_components(model)
    candidates = generate_ptr_candidates(
        model, [("c", "e")], ["A", "B", "C"], components
    )
    return candidates, compute_coverage(model, candidates, components, **kwargs)


def by_component(coverages):
    return {item.component: item for item in coverages}


def test_candidate_covers_reactions_it_unblocks():
    (candidate,), coverages = coverage_of(surplus_island())
    island = by_component(coverages)[2]
    assert island.targets == ["I1", "I2"]
    assert island.sink_only == []
    assert island.coverage == {candidate.reaction_id: ["I1", "I2"]}


def test_sink_only_unblocked_reactions_are_not_credited():
    model = build(
        {
            "EXA": {"Ac": -1},
            "R1": {"Ac": -1, "Dc": 1},
            "EXD": {"Dc": -1},
            "I1": {"Ae": -1, "Be": 1},
            "I2": {"Be": -1, "Ce": 1},
        },
        reversible={"EXA"},
    )
    _, coverages = coverage_of(model)
    island = by_component(coverages)[2]
    assert island.targets == island.sink_only == ["I1", "I2"]
    assert island.coverage == {}


def test_temporary_sinks_do_not_leak_into_model():
    model = surplus_island()
    before = sorted(reaction.id for reaction in model.reactions)
    objective = str(model.objective.expression)
    coverage_of(model)
    assert sorted(reaction.id for reaction in model.reactions) == before
    assert str(model.objective.expression) == objective


def test_done_components_are_not_recomputed():
    finished = ComponentCoverage(2, ["I1"], [], {"X": ["I1"]})
    seen = []
    _, coverages = coverage_of(
        surplus_island(), done={2: finished}, on_component=seen.append
    )
    assert [item.component for item in seen] == [1]
    assert by_component(coverages)[2] == finished
    assert ComponentCoverage.from_dict(finished.to_dict()) == finished


def test_small_components_are_skipped():
    _, coverages = coverage_of(surplus_island(), min_component_size=5)
    assert [item.component for item in coverages] == [1]


def overlapping_coverage():
    return [
        ComponentCoverage(
            2,
            ["a", "b", "c", "d"],
            [],
            {"P1": ["a", "b"], "P2": ["b", "c"], "P3": ["c", "d"]},
        )
    ]


INTERFACE = cobra.Model("solver").solver.interface


def test_milp_picks_fewest_candidates_for_full_coverage():
    selection = select_unblockers(
        overlapping_coverage(), tradeoff_lambda=0.01, budget=10, interface=INTERFACE
    )
    assert selection.status == "solved"
    assert selection.selected == ["P1", "P3"]
    assert selection.covered == ["a", "b", "c", "d"]


def test_lambda_drops_candidates_worth_less_than_their_cost():
    coverage = [
        ComponentCoverage(2, ["a", "b", "c"], [], {"P1": ["a", "b"], "P2": ["c"]})
    ]
    selection = select_unblockers(
        coverage, tradeoff_lambda=1.5, budget=10, interface=INTERFACE
    )
    assert selection.status == "solved"
    assert selection.selected == ["P1"]


def test_budget_binding_gives_partial():
    selection = select_unblockers(
        overlapping_coverage(), tradeoff_lambda=0.01, budget=1, interface=INTERFACE
    )
    assert selection.status == "partial"
    assert len(selection.selected) == 1
    assert len(selection.covered) == 2


def test_empty_coverage_is_solved_with_no_selection():
    selection = select_unblockers(
        [ComponentCoverage(2, ["a"], [], {})],
        tradeoff_lambda=0.01,
        budget=10,
        interface=INTERFACE,
    )
    assert (selection.status, selection.selected) == ("solved", [])


def test_solver_failure_is_reported(monkeypatch):
    monkeypatch.setattr(INTERFACE.Model, "optimize", lambda self: "infeasible")
    selection = select_unblockers(
        overlapping_coverage(), tradeoff_lambda=0.01, budget=10, interface=INTERFACE
    )
    assert selection.status == "failed"
    assert selection.selected == []
    assert "infeasible" in selection.failure


def three_components():
    """Main (c), island e (Ae surplus cycle), island m (Ym surplus cycle).

    Kruskal joins e-m through the type-A pair Ke/Km and main-e through Ac/Ae.
    Ke -> Km only feeds island m, so its Ym surplus stays blocked until phase
    3 adds Yc/Ym.
    """
    return build(
        {
            "EXA": {"Ac": -1},
            "R1": {"Ac": -1, "Dc": 1},
            "EXD": {"Dc": -1},
            "EXY": {"Yc": -1},
            "R2": {"Yc": -1, "Dc": 1},
            "I1": {"Ae": -1, "Be": 1},
            "I2": {"Be": -1, "Ae": 2},
            "I3": {"Be": -1, "Ke": 1},
            "J1": {"Ym": -1, "Wm": 1},
            "J2": {"Wm": -1, "Ym": 2},
            "J3": {"Km": -1, "Wm": 1},
        },
        reversible={"EXA", "EXY"},
    )


SINK_MILP = {
    "allowed_connections": [["c", "e"], ["c", "m"], ["e", "m"]],
    "max_additions": 10,
}


def test_sink_milp_end_to_end_adds_connector_and_unblocker():
    model = three_components()
    plan = generate_gapfill_plan(model, method="sink-milp", parameters=SINK_MILP)
    assert plan["header"]["status"] == "solved"
    phases = {item["reaction_id"]: item["phase"] for item in plan["proposals"]}
    assert phases == {
        "GAPFILL_PTR_Ac_Ae": 2,
        "GAPFILL_PTR_Ke_Km": 2,
        "GAPFILL_PTR_Yc_Ym": 3,
    }
    assert all("transport" in item for item in plan["proposals"])
    verification = plan["header"]["solver"]["verification"]
    assert {"J1", "J2", "J3"} <= set(verification["verified_unblocked"])
    assert verification["inactive_connectors"] == []
    result = plan["result"]["candidate_coverage"]
    assert result["GAPFILL_PTR_Ke_Km"] == "connector"
    assert result["GAPFILL_PTR_Yc_Ym"] == "selected"
    applied, ledger = apply_gapfill_plan(model, plan)
    added = {reaction.id for reaction in applied.reactions} - {
        reaction.id for reaction in model.reactions
    }
    assert added == set(phases)
    assert len(ledger) == 3


def test_verification_reports_inactive_connectors():
    result = run_sink_milp(
        three_components(),
        {**SINK_MILP, "allowed_connections": [("c", "e"), ("e", "m")]},
    )
    assert result.status == "solved"
    assert result.selected == ["GAPFILL_PTR_Ke_Km", "GAPFILL_PTR_Ac_Ae"]
    assert result.solver["verification"]["inactive_connectors"] == ["GAPFILL_PTR_Ke_Km"]


def test_already_present_component_gets_no_proposal():
    model = main_with_dead_ends()
    reaction = cobra.Reaction("T", lower_bound=-1000.0, upper_bound=1000.0)
    model.add_reactions([reaction])
    reaction.add_metabolites({model.metabolites.Ac: -1, model.metabolites.Ae: 1})
    result = run_sink_milp(model, {**SINK_MILP, "allowed_connections": [("c", "e")]})
    assert result.status == "solved"
    assert result.selected == []
    assert result.candidate_coverage == {"GAPFILL_PTR_Ac_Ae": "already-present"}


def test_no_candidates_is_solved_with_no_proposals():
    result = run_sink_milp(
        main_with_dead_ends(), {**SINK_MILP, "allowed_connections": [("c", "m")]}
    )
    assert (result.status, result.selected) == ("solved", [])


def test_ids_without_a_base_never_pair():
    model = build(
        {
            "R1": {"atp": -1, "Yc": 1},
            "R2": {"Yc": -1, "atp": 1},
            "R3": {"coa": -1, "We": 1},
            "R4": {"We": -1, "coa": 1},
        },
        compartments={"atp": "c", "coa": "e"},
    )
    assert candidates_of(model) == []


def test_unblockable_fails_loudly_on_unbounded_lp():
    model = build(
        {
            "EX": {"Ac": 1},
            "S": {"Ac": -1},
            "F": {"Ac": -1, "Bc": 1},
            "G": {"Bc": -1, "Ac": 1},
        },
        reversible={"F", "G"},
    )
    for reaction_id in ("F", "G"):
        model.reactions.get_by_id(reaction_id).bounds = (-math.inf, math.inf)
    with pytest.raises(RuntimeError, match="unbounded"):
        unblockable(model, {"F", "G"}, 1e-4)


def test_components_reject_ids_shared_by_reaction_and_metabolite():
    model = build({"Xc": {"Xc": -1, "Yc": 1}})
    with pytest.raises(ValueError, match="Xc"):
        network_components(model)
