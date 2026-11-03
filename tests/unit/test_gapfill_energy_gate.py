"""Gap-filled transports that close an energy-generating cycle are rejected."""

import cobra
import pytest

from thg_protocol.gapfill import gapfill_model
from thg_protocol.gapfill.gate import apply_energy_cycle_gate
from thg_protocol.gapfill.ptr import PtrCandidate, run_sink_milp

pytest.importorskip("memote")

PTR_ID = "GAPFILL_PTR_x_c_x_e"


def egc_model(*, with_transport: bool) -> cobra.Model:
    """ATP is made from ADP + Pi when x_c is converted to y_c.

    y_c can only get back to x_c through the extracellular compartment and the
    transport PTR, so PTR closes a cycle that charges ATP from nothing.
    """
    model = cobra.Model("egc")
    model.compartments = {"c": "cytosol", "e": "extracellular space"}

    def metabolite(identifier, mnx=None, compartment="c"):
        item = cobra.Metabolite(identifier, compartment=compartment)
        if mnx:
            item.annotation = {"metanetx.chemical": mnx}
        return item

    atp = metabolite("atp_c", "MNXM3")
    adp = metabolite("adp_c", "MNXM7")
    phosphate = metabolite("pi_c", "MNXM9")
    proton = metabolite("h_c", "MNXM1")
    water = metabolite("h2o_c", "MNXM2")
    x_c, y_c = metabolite("x_c"), metabolite("y_c")
    x_e, y_e = metabolite("x_e", compartment="e"), metabolite("y_e", compartment="e")

    def add(identifier, stoichiometry, lower=0, upper=1000):
        reaction = cobra.Reaction(identifier, lower_bound=lower, upper_bound=upper)
        model.add_reactions([reaction])
        reaction.add_metabolites(stoichiometry)

    add(
        "R_down",
        {x_c: -1, adp: -1, phosphate: -1, proton: -1, y_c: 1, atp: 1, water: 1},
    )
    add("R_t1", {y_c: -1, y_e: 1})
    add("R_t2", {y_e: -1, x_e: 1})
    if with_transport:
        add(PTR_ID, {x_e: -1, x_c: 1})
    return model


def transport_candidate() -> PtrCandidate:
    # x_e is only produced, x_c only consumed: x_e must drain into x_c.
    return PtrCandidate(
        "x_c", "x_e", "x", ("c", "e"), (1, 1), "A", PTR_ID, direction=-1
    )


def test_gate_rejects_an_added_reaction_that_closes_an_energy_cycle():
    model = egc_model(with_transport=True)
    report = apply_energy_cycle_gate(model, [PTR_ID])
    assert report["status"] == "checked"
    assert report["rejected"] == {PTR_ID: ["atp_c"]}
    assert PTR_ID not in model.reactions


def test_gate_passes_a_model_without_energy_cycles():
    model = egc_model(with_transport=False)
    report = apply_energy_cycle_gate(model, ["R_t1"])
    assert report["status"] == "checked" and report["rejected"] == {}
    assert "R_t1" in model.reactions


def test_gate_never_removes_reactions_it_was_not_asked_about():
    model = egc_model(with_transport=True)
    report = apply_energy_cycle_gate(model, [PTR_ID])
    assert {"R_down", "R_t1", "R_t2"} <= {r.id for r in model.reactions}
    assert set(report["rejected"]) == {PTR_ID}


def test_gate_is_skipped_when_energy_metabolites_cannot_be_identified():
    model = cobra.Model("plain")
    model.compartments = {"c": "cytosol"}
    first = cobra.Metabolite("alpha_c", compartment="c")
    second = cobra.Metabolite("beta_c", compartment="c")
    reaction = cobra.Reaction("R1")
    model.add_reactions([reaction])
    reaction.add_metabolites({first: -1, second: 1})
    report = apply_energy_cycle_gate(model, ["R1"])
    assert report["status"] == "skipped" and report["rejected"] == {}
    assert "R1" in model.reactions


def test_gate_with_nothing_added_does_nothing():
    assert apply_energy_cycle_gate(egc_model(with_transport=False), [])["status"] == (
        "skipped"
    )


def test_sink_milp_drops_a_connector_that_creates_an_energy_cycle():
    candidate = transport_candidate()
    parameters = {"allowed_connections": [["c", "e"]], "max_additions": 10}
    result = run_sink_milp(
        egc_model(with_transport=False),
        parameters,
        candidates=[candidate],
        connectors=[candidate],
        coverage=[],
    )
    assert result.selected == []
    assert PTR_ID not in result.model.reactions
    assert result.status == "partial"
    assert result.stop_reason == "energy-cycle-gate"
    assert result.candidate_coverage[PTR_ID] == "rejected-energy-cycle"
    assert result.solver["energy_cycle_gate"]["rejected"] == {PTR_ID: ["atp_c"]}


def test_sink_milp_keeps_the_connector_when_the_gate_is_off():
    candidate = transport_candidate()
    parameters = {
        "allowed_connections": [["c", "e"]],
        "max_additions": 10,
        "energy_cycle_gate": False,
    }
    result = run_sink_milp(
        egc_model(with_transport=False),
        parameters,
        candidates=[candidate],
        connectors=[candidate],
        coverage=[],
    )
    assert result.selected == [PTR_ID]
    assert result.solver["energy_cycle_gate"]["status"] == "disabled"


def test_greedy_gapfill_is_gated_too():
    # x_c/x_e carry no cofactor annotation, so only the gate can stop the cycle.
    parameters = {"allowed_connections": [["c", "e"]], "candidate_types": ["A"]}
    gated = gapfill_model(
        egc_model(with_transport=False), method="greedy", parameters=parameters
    )
    assert gated.selected == []
    assert gated.solver["energy_cycle_gate"]["rejected"] == {
        "GAPFILL_x_c_x_e": ["atp_c"]
    }
    ungated = gapfill_model(
        egc_model(with_transport=False),
        method="greedy",
        parameters={**parameters, "energy_cycle_gate": False},
    )
    assert ungated.selected == ["GAPFILL_x_c_x_e"]
