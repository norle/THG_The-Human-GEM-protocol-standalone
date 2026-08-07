from cobra import Metabolite, Model, Reaction

from thg_protocol.curation.beta2 import (
    apply_expansion_plan,
    generate_expansion_plan,
    resolve_gpr_locations,
)


def test_gpr_location_union_and_complex_intersection():
    assert resolve_gpr_locations(
        "A or B", {"A": {"Mitochondria"}, "B": {"Cytosol"}}
    ).rules == {
        "Cytosol": "B",
        "Mitochondria": "A",
    }
    result = resolve_gpr_locations(
        "A and B", {"A": {"Cytosol", "Mitochondria"}, "B": {"Mitochondria"}}
    )
    assert result.rules == {"Mitochondria": "(A and B)"}
    mixed = resolve_gpr_locations(
        "(A and B) or C",
        {"A": {"Mitochondria"}, "B": {"Mitochondria"}, "C": {"Cytosol"}},
    )
    assert mixed.rules == {"Cytosol": "C", "Mitochondria": "(A and B)"}
    unresolved = resolve_gpr_locations("A and Missing", {"A": {"Cytosol"}})
    assert unresolved.unresolved == ("Missing",)
    fallback = resolve_gpr_locations("Missing", {}, fallback_location="cytosol")
    assert fallback.rules == {"Cytosol": "Missing"}
    conflict = resolve_gpr_locations(
        "A and B", {"A": {"Cytosol"}, "B": {"Mitochondria"}}
    )
    assert {item["status"] for item in conflict.evidence} == {"rejected"}


def test_expansion_is_proposal_first_and_deterministic():
    model = Model("beta2")
    a = Metabolite("a_c", formula="C", charge=0, compartment="c")
    b = Metabolite("b_c", formula="C", charge=0, compartment="c")
    reaction = Reaction("R1")
    reaction.add_metabolites({a: -1, b: 1})
    reaction.gene_reaction_rule = "G1"
    model.add_reactions([reaction])
    plans = generate_expansion_plan(
        model,
        {"R1": {"Mitochondria": "G1"}},
        compartments={"c": "Cytosol", "m": "Mitochondria"},
    )
    assert len(plans) == 1
    assert len(model.reactions) == 1
    expanded, ledger = apply_expansion_plan(model, plans)
    assert len(expanded.reactions) == 2
    assert ledger[0]["status"] == "applied"
    assert (
        generate_expansion_plan(
            model,
            {"R1": {"Mitochondria": "G1"}},
            compartments={"c": "Cytosol", "m": "Mitochondria"},
        )
        == plans
    )


def test_expansion_rejects_decisions_for_unknown_proposals():
    model = Model("beta2")
    a = Metabolite("a_c", formula="C", charge=0, compartment="c")
    b = Metabolite("b_c", formula="C", charge=0, compartment="c")
    reaction = Reaction("R1")
    reaction.add_metabolites({a: -1, b: 1})
    reaction.gene_reaction_rule = "G1"
    model.add_reactions([reaction])
    plans = generate_expansion_plan(
        model,
        {"R1": {"Mitochondria": "G1"}},
        compartments={"c": "Cytosol", "m": "Mitochondria"},
    )
    try:
        apply_expansion_plan(model, plans, decisions={"unknown": "approve"})
    except ValueError as error:
        assert "unknown proposals" in str(error)
    else:
        raise AssertionError("unknown β2 decisions must be rejected")
