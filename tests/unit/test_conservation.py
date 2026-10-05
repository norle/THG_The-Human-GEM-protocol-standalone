from __future__ import annotations

import json

import cobra
import pytest

from thg_protocol.analysis import conservation
from thg_protocol.workflow.proposals import Decision, ProposalError


def _met(identifier, formula, charge=0, name=None):
    return cobra.Metabolite(
        identifier, formula=formula, charge=charge, compartment="c", name=name
    )


def _reaction(model, identifier, stoichiometry, name=""):
    reaction = cobra.Reaction(identifier, name=name)
    reaction.add_metabolites(
        {
            model.metabolites.get_by_id(key): value
            for key, value in stoichiometry.items()
        }
    )
    model.add_reactions([reaction])
    return reaction


def base_model(*, broken: bool = True, nadp: bool = False) -> cobra.Model:
    """NAD-dependent conversion; ``broken`` drops NAD from R2 (H: -2 residual).

    R5 and R6 tie NADH + H+ to H2, so the missing NAD pair makes H+ and H2
    unconserved.
    """
    model = cobra.Model("toy")
    metabolites = [
        _met("a_c", "C2H6O", name="ethanol"),
        _met("b_c", "C2H4O", name="acetaldehyde"),
        _met("nad_c", "C21H26N7O14P2", -1, "NAD+"),
        _met("nadh_c", "C21H27N7O14P2", -2, "NADH"),
        _met("h_c", "H", 1, "H+"),
        _met("h2_c", "H2", 0, "hydrogen"),
    ]
    if nadp:
        metabolites += [
            _met("nadp_c", "C21H25N7O17P3", -3, "NADP+"),
            _met("nadph_c", "C21H26N7O17P3", -4, "NADPH"),
        ]
    model.add_metabolites(metabolites)
    _reaction(model, "R1", {"a_c": -1, "nad_c": -1, "b_c": 1, "nadh_c": 1, "h_c": 1})
    r2 = {"a_c": -1, "b_c": 1}
    if not broken:
        r2.update({"nad_c": -1, "nadh_c": 1, "h_c": 1})
    _reaction(model, "R2", r2)
    _reaction(model, "R5", {"nadh_c": -1, "h_c": -1, "nad_c": 1, "h2_c": 1})
    _reaction(model, "R6", {"h2_c": -1, "h_c": 2})
    for metabolite in list(model.metabolites):
        model.add_boundary(metabolite, type="sink")
    return model


def detection_for(*ids, excluded=None):
    return {
        "unconserved": [{"id": item} for item in ids],
        "excluded": excluded or {},
    }


def test_exclusions_report_each_rule():
    model = base_model(broken=False)
    biomass = _reaction(model, "BIO", {"a_c": -1, "b_c": 1})
    biomass.annotation["sbo"] = "SBO:0000629"
    pool = _reaction(model, "POOL", {"b_c": -1, "a_c": 1})
    pool.subsystem = "Pool reactions"
    noted = _reaction(model, "NOTED", {"h2_c": -1, "h_c": 1})
    noted.notes[conservation.EXCLUSION_NOTE] = "approved"
    _reaction(model, "CONF", {"nad_c": -1, "nadh_c": 1})
    derived = model.copy()
    derived.reactions.POOL.subsystem = ""
    for group in list(derived.groups):
        derived.remove_groups([group])

    rules = conservation.conservation_exclusions(
        derived, input_model=model, configured=["CONF", "missing"]
    )

    assert rules == {
        "BIO": "sbo-biomass",
        "CONF": "configuration",
        "NOTED": "model-note",
        "POOL": "input-model",
    }
    assert "SK_a_c" not in rules


@pytest.mark.memote
def test_detection_names_unconserved_metabolites():
    pytest.importorskip("memote")
    result = conservation.find_unconserved_metabolites(base_model())
    assert result["consistent"] is False
    assert [item["id"] for item in result["unconserved"]] == ["h2_c", "h_c"]
    assert conservation.find_unconserved_metabolites(base_model(broken=False))[
        "consistent"
    ]


@pytest.mark.memote
def test_detection_ignores_excluded_pool_reaction():
    pytest.importorskip("memote")
    model = base_model(broken=False)
    pool = _reaction(model, "POOL", {"h2_c": -1, "h_c": 1})
    pool.subsystem = "Pool reactions"
    result = conservation.find_unconserved_metabolites(model)
    assert result["consistent"] is True
    assert result["excluded"]["POOL"] == "pseudo-subsystem"
    configured = base_model(broken=False)
    _reaction(configured, "LUMP", {"h2_c": -1, "h_c": 1})
    assert not conservation.find_unconserved_metabolites(configured)["consistent"]
    assert conservation.find_unconserved_metabolites(configured, configured=["LUMP"])[
        "consistent"
    ]


def blamed_for(model, *reaction_ids, input_model=None):
    """A localization blaming exactly ``reaction_ids``, bypassing the LP."""
    return {
        "blamed": [
            conservation._blamed_row(
                model.reactions.get_by_id(key), 1, model, input_model, set()
            )
            for key in reaction_ids
        ]
    }


def test_blame_lp_blames_the_planted_reaction_and_removal_restores_consistency():
    model = base_model()
    # R1, R2 and R5 break the loop at equal cost; the tie-break prefers R2
    # (element imbalance). R6 (H2 -> 2 H+) is charge-unbalanced in the toy.
    assert conservation.chemically_suspect(model, {}) == {"R2", "R6"}
    blame = conservation.blame_reactions(model, exclusions={}, prefer={"R2"})
    assert list(blame["reactions"]) == ["R2"]
    after = conservation.blame_reactions(
        model, exclusions={"R2": "blamed"}, prefer=set()
    )
    assert after["reactions"] == {}
    assert after["objective"] == 0
    assert (
        conservation.blame_reactions(base_model(broken=False), exclusions={})[
            "reactions"
        ]
        == {}
    )


def test_tie_break_only_decides_between_equally_cheap_reactions():
    model = base_model()
    blame = conservation.blame_reactions(model, exclusions={}, prefer={"R5"})
    assert list(blame["reactions"]) == ["R5"]


def test_blamed_rows_carry_origin_and_chemical_flags():
    model = base_model()
    model.reactions.R1.add_metabolites({model.metabolites.b_c: 0.5})
    result = conservation.localize(
        model, detection_for("h2_c", "h_c"), input_model=base_model(broken=False)
    )
    rows = {row["id"]: row for row in result["blamed"]}
    assert rows and set(rows) <= {"R1", "R2", "R6"}
    assert all(row["flags"] for row in rows.values())
    assert rows.get("R6", {}).get("origin", "unchanged") == "unchanged"
    for key in {"R1", "R2"} & set(rows):
        assert rows[key]["origin"] == "changed"
        assert "unbalanced-elements" in rows[key]["flags"]
    if "R1" in rows:
        assert rows["R1"]["fractional"] == {"b_c": 1.5}
        assert "fractional-coefficients" in rows["R1"]["flags"]


def test_blamed_reaction_with_a_shared_name_is_flagged_as_possibly_mislabelled():
    model = base_model()
    # b_c takes the name of another compound with a conflicting formula.
    model.add_metabolites([_met("x_c", "C10H8O", name="acetaldehyde")])
    result = conservation.localize(model, detection_for("h2_c", "h_c"))
    row = next(row for row in result["blamed"] if row["id"] == "R2")
    assert row["mislabelled"] == ["b_c"]
    assert "possibly-mislabelled" in row["flags"]


def test_integer_candidates_round_fitted_coefficients_to_a_balanced_reaction():
    model = base_model(broken=False)
    fitted = _reaction(model, "FIT", {"a_c": -1, "b_c": 1, "h2_c": 1.5})
    assert conservation.integer_candidates(fitted, model) == [
        {"a_c": -1, "b_c": 1, "h2_c": 1}
    ]
    proposals = conservation.propose_fixes(
        model, blamed_for(model, "FIT"), exclusions={}
    )
    assert [(item.policy, item.after) for item in proposals] == [
        ("integer-stoichiometry", {"a_c": -1, "b_c": 1, "h2_c": 1})
    ]
    assert proposals[0].confidence == "medium"
    assert proposals[0].metadata["targets"] == ["FIT"]


def test_localize_splits_new_from_inherited():
    model = base_model()
    result = conservation.localize(
        model,
        detection_for("h2_c", "h_c"),
        input_model=model,
        input_detection=detection_for("h_c"),
    )
    assert result["new"] == ["h2_c"]
    assert result["inherited"] == ["h_c"]


def _proposals(model, input_model=None, detection=None):
    detection = detection or detection_for("h2_c", "h_c")
    localization = conservation.localize(model, detection, input_model=input_model)
    return conservation.propose_fixes(
        model, localization, exclusions={}, input_model=input_model
    )


def test_missing_cofactor_proposes_the_nad_pair_with_balances():
    proposals = _proposals(base_model())
    cofactor = [item for item in proposals if item.policy == "cofactor-pair"]
    assert len(cofactor) == 1
    proposal = cofactor[0]
    assert proposal.object_id == "R2"
    assert proposal.after == {"a_c": -1, "b_c": 1, "h_c": 1, "nad_c": -1, "nadh_c": 1}
    assert proposal.confidence == "medium"
    reaction = proposal.metadata["reaction"]
    assert reaction["before"]["elements"]["residual"] == {"H": -2}
    assert reaction["after"]["elements"]["balanced"] is True
    assert reaction["after"]["charge"]["balanced"] is True
    assert "NAD+" in reaction["after"]["equation_names"]
    assert proposal.metadata["targets"] == ["R2"]
    assert proposal.evidence[0].startswith("blamed:R2 (imbalance -")


def test_ambiguous_cofactors_are_all_listed_as_alternatives():
    proposals = [
        item for item in _proposals(base_model(nadp=True)) if item.object_id == "R2"
    ]
    assert {item.metadata["cofactor"] for item in proposals} == {
        "NAD+/NADH",
        "NADP+/NADPH",
    }
    assert {item.confidence for item in proposals} == {"low"}
    first, second = proposals
    assert first.metadata["alternatives"] == [second.proposal_id]


def test_changed_stoichiometry_is_restored_from_the_input_model():
    reference = base_model(broken=False)
    proposals = _proposals(base_model(), input_model=reference)
    restore = [
        item for item in proposals if item.policy == "restore-input-stoichiometry"
    ]
    assert [item.object_id for item in restore] == ["R2"]
    assert restore[0].confidence == "high"
    assert restore[0].metadata["origin"] == "changed"
    assert restore[0].metadata["input_model"]["present"] is True
    assert not any(item.policy == "cofactor-pair" for item in proposals)


def test_missing_formula_is_inferred_for_added_metabolites():
    model = base_model(broken=False)
    model.add_metabolites([_met("x_c", "", name="new")])
    model.metabolites.x_c.formula = None
    _reaction(model, "RX", {"a_c": -1, "x_c": 1, "h2_c": 1})
    _reaction(model, "RY", {"x_c": -1, "h2_c": -1, "b_c": 1, "h_c": 2})
    assert conservation.infer_formula(model, "x_c", exclusions={}) == "C2H4O"
    localization = blamed_for(model, "RX", input_model=base_model(broken=False))
    proposals = conservation.propose_fixes(
        model, localization, exclusions={}, input_model=base_model(broken=False)
    )
    formula = [item for item in proposals if item.policy == "infer-formula"]
    assert [(item.object_id, item.after) for item in formula] == [("x_c", "C2H4O")]
    assert {item["id"] for item in formula[0].metadata["reactions"]} == {"RX", "RY"}
    assert formula[0].confidence == "medium"  # charge stays unbalanced in RY
    assert "after-unbalanced-charge" in formula[0].metadata["flags"]


def test_inconsistent_formula_inference_returns_none():
    model = base_model(broken=False)
    model.add_metabolites([_met("x_c", None, name="new")])
    _reaction(model, "RX", {"a_c": -1, "x_c": 1})
    _reaction(model, "RY", {"b_c": -1, "x_c": 1})
    assert conservation.infer_formula(model, "x_c", exclusions={}) is None


def test_pool_reaction_is_proposed_for_exclusion_and_others_are_unresolved():
    model = base_model(broken=False)
    _reaction(model, "biomass_pool", {"a_c": -1, "b_c": 2})
    _reaction(model, "ODD", {"nad_c": -1, "nadh_c": 2})
    proposals = conservation.propose_fixes(
        model, blamed_for(model, "biomass_pool", "ODD"), exclusions={}
    )
    by_policy = {item.policy: item for item in proposals}
    assert by_policy["exclude-pseudo-reaction"].object_id == "biomass_pool"
    unresolved = by_policy["unresolved"]
    assert unresolved.object_id == "ODD"
    assert unresolved.status == "unresolved"
    assert unresolved.operation == "remove-reaction"


def test_apply_only_approved_fixes_to_a_copy_and_recheck():
    model = base_model()
    proposals = _proposals(model)
    fix = next(item for item in proposals if item.policy == "cofactor-pair")

    unchanged, applied, ledger = conservation.apply_conservation_fixes(model, proposals)
    assert applied == ()
    assert {entry["status"] for entry in ledger} == {"unresolved"}
    assert len(unchanged.reactions.R2.metabolites) == 2

    fixed, applied, ledger = conservation.apply_conservation_fixes(
        model, proposals, [Decision(fix.proposal_id, "approve")]
    )
    assert [item.proposal_id for item in applied] == [fix.proposal_id]
    assert {m.id for m in fixed.reactions.R2.metabolites} == set(fix.after)
    assert len(model.reactions.R2.metabolites) == 2  # input untouched
    report = conservation.compare_detections(
        detection_for("h2_c", "h_c"), detection_for(), applied
    )
    assert report["resolved"] == ["h2_c", "h_c"]
    assert report["ineffective_fixes"] == []
    flagged = conservation.compare_detections(
        detection_for("h_c"), detection_for("h_c"), applied, still_blamed=["R2"]
    )
    assert flagged["ineffective_fixes"] == [fix.proposal_id]


def test_apply_rejects_two_alternatives_for_one_reaction():
    model = base_model(nadp=True)
    proposals = [item for item in _proposals(model) if item.object_id == "R2"]
    with pytest.raises(ProposalError, match="more than one approved fix"):
        conservation.apply_conservation_fixes(
            model,
            proposals,
            [Decision(item.proposal_id, "approve") for item in proposals],
        )


def test_replace_formula_and_exclusion_decisions():
    model = base_model(broken=False)
    model.add_metabolites([_met("x_c", None, name="new")])
    _reaction(model, "biomass_pool", {"a_c": -1, "x_c": 1})
    from thg_protocol.analysis.conservation import _proposal

    exclude = _proposal(
        operation="exclude-reaction",
        object_type="reaction",
        object_id="biomass_pool",
        before={"excluded": False},
        after={"excluded": True},
        policy="exclude-pseudo-reaction",
        confidence="medium",
        evidence=[],
        metadata={},
    )
    formula = _proposal(
        operation="set-formula",
        object_type="metabolite",
        object_id="x_c",
        before="",
        after="C2H6O",
        policy="infer-formula",
        confidence="high",
        evidence=[],
        metadata={},
    )
    restore = _proposal(
        operation="set-stoichiometry",
        object_type="reaction",
        object_id="R2",
        before={},
        after={"a_c": -1, "b_c": 1},
        policy="cofactor-pair",
        confidence="low",
        evidence=[],
        metadata={},
    )
    fixed, applied, _ = conservation.apply_conservation_fixes(
        model,
        [exclude, formula, restore],
        [
            Decision(exclude.proposal_id, "approve"),
            Decision(formula.proposal_id, "replace", "C2H4O"),
            Decision(restore.proposal_id, "reject"),
        ],
    )
    assert len(applied) == 2
    assert fixed.metabolites.x_c.formula == "C2H4O"
    assert conservation.conservation_exclusions(fixed)["biomass_pool"] == "model-note"
    assert len(fixed.reactions.R2.metabolites) == 5


@pytest.mark.memote
def test_conservation_workflow_proposes_then_applies_decisions(tmp_path):
    pytest.importorskip("memote")
    from thg_protocol.io.models import load_model
    from thg_protocol.workflow.runner import start

    source = tmp_path / "model.json"
    cobra.io.save_json_model(base_model(), str(source))
    decisions = tmp_path / "decisions.jsonl"
    config = tmp_path / "conservation.json"
    config.write_text(
        json.dumps(
            {
                "workflow": "conservation",
                "run": {"name": "toy", "output_dir": "run"},
                "conservation": {
                    "input_model": "model.json",
                    "decisions_file": "decisions.jsonl",
                },
            }
        ),
        encoding="utf-8",
    )
    run = start(config)
    proposals = sorted(
        (run / "artifacts" / "conservation-propose").glob("*/proposals.jsonl")
    )
    records = [json.loads(line) for line in proposals[-1].read_text().splitlines()]
    fix = next(item for item in records if item["policy"] == "cofactor-pair")
    recheck = sorted(
        (run / "artifacts" / "conservation-recheck").glob("*/recheck.json")
    )
    assert json.loads(recheck[-1].read_text())["comparison"]["after"] == ["h2_c", "h_c"]

    decisions.write_text(
        json.dumps({"proposal_id": fix["proposal_id"], "action": "approve"}) + "\n",
        encoding="utf-8",
    )
    start(config)
    recheck = sorted(
        (run / "artifacts" / "conservation-recheck").glob("*/recheck.json")
    )
    comparison = json.loads(recheck[-1].read_text())["comparison"]
    assert comparison["after"] == []
    assert comparison["resolved"] == ["h2_c", "h_c"]
    applied = sorted(
        (run / "artifacts" / "conservation-apply").glob("*/model-fixed.json")
    )
    assert len(load_model(applied[-1]).reactions.R2.metabolites) == 5
    ledger = sorted(
        (run / "artifacts" / "conservation-apply").glob("*/change-ledger.jsonl")
    )
    statuses = [
        json.loads(line)["status"] for line in ledger[-1].read_text().splitlines()
    ]
    assert statuses.count("applied") == 1
    assert len(load_model(source).reactions.R2.metabolites) == 2
