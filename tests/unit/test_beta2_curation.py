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


def _expansion_fixture():
    model = Model("identity")
    reaction = Reaction("R1")
    reaction.gene_reaction_rule = "G1"
    reaction.add_metabolites(
        {
            Metabolite("a_c", formula="C6H12O6", charge=0, compartment="c"): -1,
            Metabolite("b_c", formula="C6H12O6", charge=0, compartment="c"): 1,
        }
    )
    model.add_reactions([reaction])
    return model


def _plans(model):
    return [
        plan
        for plan in generate_expansion_plan(
            model,
            {"R1": {"Mitochondria": "G1"}},
            compartments={"c": "Cytosol", "m": "Mitochondria"},
        )
        if plan["reaction_id"] == "R1"
    ]


def test_expansion_does_not_conflate_isomers_or_different_bounds():
    model = _expansion_fixture()
    isomers = Reaction("ISOMERS")
    isomers.add_metabolites(
        {
            Metabolite("x_m", formula="C6H12O6", charge=0, compartment="m"): -1,
            Metabolite("y_m", formula="C6H12O6", charge=0, compartment="m"): 1,
        }
    )
    model.add_reactions([isomers])
    assert _plans(model)[0]["action"] == "create"
    equivalent = Reaction("EQUIVALENT", upper_bound=1)
    equivalent.add_metabolites(
        {
            Metabolite("a_m", formula="C6H12O6", charge=0, compartment="m"): -1,
            Metabolite("b_m", formula="C6H12O6", charge=0, compartment="m"): 1,
        }
    )
    model.add_reactions([equivalent])
    assert _plans(model)[0]["action"] == "create"
    equivalent.upper_bound = model.reactions.R1.upper_bound
    assert _plans(model)[0]["equivalent_existing"] == ["EQUIVALENT"]


def test_expansion_provenance_supports_equivalence_and_transport_pairing():
    from thg_protocol.gapfill.core import _as_mapping, _transport_candidates
    from thg_protocol.gapfill.ptr import generate_ptr_candidates, network_components

    model = _expansion_fixture()
    plans = _plans(model)
    expanded, _ = apply_expansion_plan(model, plans)
    assert _plans(expanded)[0]["equivalent_existing"] == [plans[0]["new_reaction_id"]]
    candidates = _transport_candidates(
        _as_mapping(expanded), [("c", "m")], ["A", "B", "C"]
    )
    assert len(candidates) == 2
    assert {frozenset(candidate.metabolites) for candidate in candidates} == {
        frozenset((source, target))
        for source, target in plans[0]["metabolite_ids"].items()
    }
    components = network_components(expanded)
    ptr = generate_ptr_candidates(expanded, [("c", "m")], ["A", "B", "C"], components)
    assert len(ptr) == 2


def test_report_only_ignores_approvals_and_replacement_decisions():
    model = _expansion_fixture()
    plans = _plans(model)
    pid = plans[0]["proposal_id"]
    for decisions in (
        {pid: "approve"},
        {pid: {"action": "replace", "replacement": plans[0]}},
    ):
        expanded, ledger = apply_expansion_plan(
            model, plans, mode="report-only", approved={pid}, decisions=decisions
        )
        assert len(expanded.reactions) == len(model.reactions)
        assert len(expanded.metabolites) == len(model.metabolites)
        assert ledger[0]["status"] == "not-applied"


def test_base_ids_strip_suffix_when_source_parent_was_removed():
    from thg_protocol.workflow.ids import metabolite_base_ids

    bases = metabolite_base_ids(
        {
            "THG_copy_e": {
                "compartment": "e",
                "annotation": {"thg_source_metabolite": "MAM01234c"},
            },
            "MAM01234e": {"compartment": "e"},
        }
    )
    assert bases == {"THG_copy_e": "MAM01234", "MAM01234e": "MAM01234"}
