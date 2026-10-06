from __future__ import annotations

import cobra
import pytest

from thg_protocol.analysis import conservation
from thg_protocol.validation import PROFILES, formula_disagreement, validate_model
from thg_protocol.workflow.proposals import Decision, ProposalError


def _model(*metabolites, reactions=()) -> cobra.Model:
    model = cobra.Model("toy")
    model.add_metabolites(
        [
            cobra.Metabolite(
                identifier, formula=formula, charge=charge, compartment=compartment
            )
            for identifier, formula, charge, compartment in metabolites
        ]
    )
    for identifier, stoichiometry in reactions:
        reaction = cobra.Reaction(identifier)
        reaction.add_metabolites(
            {model.metabolites.get_by_id(k): v for k, v in stoichiometry.items()}
        )
        model.add_reactions([reaction])
    return model


ETHANOL = [
    ("a_c", "C2H6O", 0, "c"),
    ("a_m", "C2H5O", 0, "m"),
    ("a_x", "C2H6O", 0, "x"),
]
TRANSPORT = [("TM", {"a_c": -1, "a_m": 1}), ("TX", {"a_c": -1, "a_x": 1})]


def test_no_profile_blocks_release_on_blocked_reactions():
    for profile in PROFILES.values():
        assert "flux-consistency" not in profile["blocking"]


def test_formula_fix_proposes_the_majority_formula():
    model = _model(*ETHANOL, reactions=TRANSPORT)
    proposals = conservation.formula_fixes(model, formula_disagreement(model))
    assert [(p.operation, p.object_id, p.before, p.after) for p in proposals] == [
        ("set-formula", "a_m", "C2H5O", "C2H6O")
    ]
    balance = proposals[0].metadata["balance"]
    assert (balance["before"]["balanced"], balance["after"]["balanced"]) == (0, 1)
    assert proposals[0].metadata["targets"] == ["TM"]
    assert proposals[0].confidence == "low"
    assert "verify independent chemical annotation" in proposals[0].reason


def test_formula_fix_offers_reference_and_majority_as_alternatives():
    model = _model(*ETHANOL, reactions=TRANSPORT)
    reference = _model(("a_m", "C2H4O", 0, "m"))
    proposals = conservation.formula_fixes(
        model,
        formula_disagreement(model, reference_model=reference),
        reference_model=reference,
    )
    assert sorted((p.after, p.policy) for p in proposals) == [
        ("C2H4O", "formula-disagreement-reference"),
        ("C2H6O", "formula-disagreement-majority"),
    ]
    assert proposals[0].metadata["alternatives"] == [proposals[1].proposal_id]


def test_formula_fix_skips_a_tie_and_proposes_charges():
    model = _model(("b_c", "C2H4O", 0, "c"), ("b_m", "C2H4O", -1, "m"))
    reference = _model(("b_m", "C2H4O", 0, "m"))
    disagreement = formula_disagreement(model, reference_model=reference)
    proposals = conservation.formula_fixes(
        model, disagreement, reference_model=reference
    )
    # One compartment each way is a tie: only the reference value is offered.
    assert [(p.operation, p.object_id, p.after) for p in proposals] == [
        ("set-charge", "b_m", 0)
    ]


def test_formula_fix_requires_a_strict_majority():
    # A, A, B, C: A is the most common value but holds only 2 of 4.
    model = _model(
        ("a_c", "C2H6O", 0, "c"),
        ("a_m", "C2H6O", 0, "m"),
        ("a_x", "C2H5O", 0, "x"),
        ("a_r", "C2H4O", 0, "r"),
    )
    assert conservation.formula_fixes(model, formula_disagreement(model)) == []


@pytest.mark.parametrize("coefficient", ["abc", True, float("nan"), float("inf")])
def test_malformed_replacement_coefficient_is_a_proposal_error(coefficient):
    model = _model(*ETHANOL, reactions=TRANSPORT)
    proposal = conservation._proposal(
        operation="set-stoichiometry",
        object_type="reaction",
        object_id="TM",
        before={"a_c": -1, "a_m": 1},
        after={"a_c": -1, "a_x": 1},
        policy="test",
        confidence="low",
        evidence=[],
        metadata={},
    )
    decision = Decision(
        proposal.proposal_id, "replace", replacement={"a_c": coefficient, "a_m": 1}
    )
    with pytest.raises(ProposalError, match="invalid coefficient"):
        conservation.apply_conservation_fixes(model, [proposal], [decision])


def test_set_charge_and_formula_target_separate_fields():
    model = _model(("b_m", "C2H5O", -1, "m"))

    def proposal(operation, before, after):
        return conservation._proposal(
            operation=operation,
            object_type="metabolite",
            object_id="b_m",
            before=before,
            after=after,
            policy="test",
            confidence="low",
            evidence=[],
            metadata={},
        )

    charge = proposal("set-charge", -1, 0)
    formula = proposal("set-formula", "C2H5O", "C2H4O")
    other = proposal("set-formula", "C2H5O", "C2H6O")
    fixed, applied, _ = conservation.apply_conservation_fixes(
        model,
        [charge, formula, other],
        [
            Decision(charge.proposal_id, "approve"),
            Decision(formula.proposal_id, "approve"),
        ],
    )
    assert len(applied) == 2
    assert (fixed.metabolites.b_m.formula, fixed.metabolites.b_m.charge) == ("C2H4O", 0)
    assert model.metabolites.b_m.charge == -1
    with pytest.raises(ProposalError, match="more than one approved fix"):
        conservation.apply_conservation_fixes(
            model,
            [formula, other],
            [
                Decision(formula.proposal_id, "approve"),
                Decision(other.proposal_id, "approve"),
            ],
        )
    with pytest.raises(ProposalError, match="must be an integer"):
        conservation.apply_conservation_fixes(
            model, [charge], [Decision(charge.proposal_id, "replace", 0.5)]
        )


BASE = [
    ("a_c", "C2H6O", -1, "c"),
    ("b_c", "C2H4O", -1, "c"),
    ("h_c", "H", 1, "c"),
    ("h2_c", "H2", 0, "c"),
]


def test_validation_proposes_fixes_and_merges_checks(monkeypatch):
    reference = _model(*BASE, reactions=[("R2", {"a_c": -1, "b_c": 1, "h2_c": 1})])
    model = _model(
        *BASE,
        reactions=[
            # Element and charge imbalance; solve without restoring the reference.
            ("R2", {"a_c": -2, "b_c": 1, "h2_c": 1}),
            # 1.2 ethanol rounds to the balanced 1.
            ("FR", {"a_c": -1.2, "b_c": 1, "h2_c": 1}),
        ],
    )
    calls = []
    original = conservation.reaction_fixes

    def spy(reaction, *args, **kwargs):
        calls.append(reaction.id)
        return original(reaction, *args, **kwargs)

    monkeypatch.setattr(conservation, "reaction_fixes", spy)
    report = validate_model(
        model, "structural-fast", reference_model=reference, propose_fixes=True
    )
    by_object = {item["object_id"]: item for item in report["proposals"]}
    assert by_object["R2"]["policy"] == "stoichiometry-balance"
    assert sorted(by_object["R2"]["checks"]) == ["charge-balance", "mass-balance"]
    assert by_object["FR"]["policy"] == "integer-stoichiometry"
    assert by_object["FR"]["after"] == {"a_c": -1, "b_c": 1, "h2_c": 1}
    assert "fractional-coefficients" in by_object["FR"]["checks"]
    assert calls.count("R2") == calls.count("FR") == 1
    assert {"mass-balance:R2", "charge-balance:R2"} <= set(by_object["R2"]["evidence"])
    index = report["index"]
    assert {"R2", "FR"} <= set(index["reactions"])
    assert index["metabolites"]["a_c"]["formula"] == "C2H6O"


def test_integer_coefficient_repair_balances_elements_and_charge_without_reference():
    model = _model(
        ("h2_c", "H2", 0, "c"),
        ("o2_c", "O2", 0, "c"),
        ("water_c", "H2O", 0, "c"),
        reactions=[("R1", {"h2_c": -1, "o2_c": -1, "water_c": 1})],
    )
    before = {m.id: (m.formula, m.charge) for m in model.metabolites}
    [proposal] = conservation.reaction_fixes(model.reactions.R1, model)
    assert proposal.policy == "stoichiometry-balance"
    assert proposal.after == {"h2_c": -2, "o2_c": -1, "water_c": 2}
    assert proposal.metadata["search"]["rank"] == [0, 2, 2]
    fixed, _, _ = conservation.apply_conservation_fixes(
        model, [proposal], [Decision(proposal.proposal_id, "approve")]
    )
    assert fixed.reactions.R1.check_mass_balance() == {}
    assert {m.id: (m.formula, m.charge) for m in fixed.metabolites} == before
    assert model.reactions.R1.get_coefficient("h2_c") == -1


def test_equal_minimal_coefficient_edits_are_reviewable_alternatives():
    model = _model(
        ("a_c", "C", 0, "c"),
        ("b_c", "C", 0, "c"),
        ("c_c", "C3", 0, "c"),
        reactions=[("R1", {"a_c": -2, "b_c": -2, "c_c": 1})],
    )
    proposals = conservation.reaction_fixes(model.reactions.R1, model)
    assert len(proposals) == 2
    assert {tuple(sorted(p.after.items())) for p in proposals} == {
        (("a_c", -1), ("b_c", -2), ("c_c", 1)),
        (("a_c", -2), ("b_c", -1), ("c_c", 1)),
    }
    assert all(
        p.confidence == "low" and p.metadata["search"]["rank"] == [0, 1, 1]
        for p in proposals
    )
    assert proposals[0].metadata["alternatives"] == [proposals[1].proposal_id]


@pytest.mark.parametrize("formula,charge", [(None, 0), ("invalid", 0), ("H2O", None)])
def test_coefficient_search_requires_known_formulas_and_charges(formula, charge):
    model = _model(
        ("a_c", "H2", 0, "c"),
        ("b_c", "O2", 0, "c"),
        ("c_c", formula, charge, "c"),
        reactions=[("R1", {"a_c": -1, "b_c": -1, "c_c": 1})],
    )
    assert conservation.reaction_fixes(model.reactions.R1, model) == []


def test_search_preserves_sides_and_respects_coefficient_bounds():
    model = _model(
        ("a_c", "C13", 0, "c"),
        ("b_c", "C", 0, "c"),
        ("o_c", "O", 0, "c"),
        reactions=[
            ("LIMIT", {"a_c": -1, "b_c": 1}),
            ("DROP", {"b_c": -1, "a_c": 13, "o_c": 1}),
        ],
    )
    assert conservation.coefficient_candidates(model.reactions.LIMIT, model) == []
    assert conservation.coefficient_candidates(model.reactions.DROP, model) == []


def test_balanced_fractional_stoichiometry_is_retained():
    model = _model(
        ("h_c", "H2", 0, "c"),
        ("o_c", "O2", 0, "c"),
        ("w_c", "H2O", 0, "c"),
        reactions=[("R1", {"h_c": -1, "o_c": -0.5, "w_c": 1})],
    )
    assert conservation.reaction_fixes(model.reactions.R1, model) == []


@pytest.mark.parametrize("add_water", [False, True])
def test_repair_preserves_retained_fractional_coefficient_precision(add_water):
    model = _model(
        ("a_c", "C6H6O3" if add_water else "C6", 0, "c"),
        ("b_c", "C2", 0, "c"),
        ("h2_c", "H2", 0, "c"),
        ("h_c", "H", 0, "c"),
        ("w_c", "H2O", 0, "c"),
        reactions=[
            (
                "R1",
                {"a_c": -1 / 3, "b_c": 1}
                | ({} if add_water else {"h2_c": -1, "h_c": 1}),
            )
        ],
    )
    model.metabolites.w_c.name = "H2O"
    [proposal] = conservation.reaction_fixes(model.reactions.R1, model)
    assert proposal.after == {"a_c": -1 / 3, "b_c": 1} | (
        {"w_c": 1} if add_water else {"h2_c": -1, "h_c": 2}
    )
    fixed, _, _ = conservation.apply_conservation_fixes(
        model, [proposal], [Decision(proposal.proposal_id, "approve")]
    )
    assert fixed.reactions.R1.get_coefficient("a_c") == -1 / 3
    assert conservation.element_residual(proposal.after, fixed)["balanced"]
    assert fixed.reactions.R1.check_mass_balance() == {}


def test_nad_hydrolysis_can_add_water_when_nadh_is_available():
    model = _model(
        ("nad_c", "C21H26N7O14P2", -1, "c"),
        ("nadh_c", "C21H27N7O14P2", -2, "c"),
        ("adpr_c", "C15H21N5O14P2", -2, "c"),
        ("nam_c", "C6H6N2O", 0, "c"),
        ("h_c", "H", 1, "c"),
        ("w_c", "H2O", 0, "c"),
        reactions=[("R1", {"nad_c": -1, "adpr_c": 1, "nam_c": 1, "h_c": 1})],
    )
    names = {"nad_c": "NAD+", "nadh_c": "NADH", "h_c": "H+", "w_c": "H2O"}
    for key, name in names.items():
        model.metabolites.get_by_id(key).name = name
    [proposal] = conservation.reaction_fixes(model.reactions.R1, model)
    assert proposal.after == {
        "nad_c": -1,
        "adpr_c": 1,
        "nam_c": 1,
        "h_c": 1,
        "w_c": -1,
    }
    fixed, _, _ = conservation.apply_conservation_fixes(
        model, [proposal], [Decision(proposal.proposal_id, "approve")]
    )
    assert fixed.reactions.R1.check_mass_balance() == {}


def test_missing_nad_partner_is_added_with_a_balanced_pair():
    model = _model(
        ("a_c", "C2H6O", 0, "c"),
        ("b_c", "C2H4O", 0, "c"),
        ("nad_c", "C21H26N7O14P2", -1, "c"),
        ("nadh_c", "C21H27N7O14P2", -2, "c"),
        ("h_c", "H", 1, "c"),
        reactions=[("R1", {"a_c": -1, "b_c": 1, "nad_c": -1, "h_c": 1})],
    )
    for key, name in {"nad_c": "NAD+", "nadh_c": "NADH", "h_c": "H+"}.items():
        model.metabolites.get_by_id(key).name = name
    [proposal] = conservation.reaction_fixes(model.reactions.R1, model)
    assert proposal.after == {
        "a_c": -1,
        "b_c": 1,
        "nad_c": -1,
        "nadh_c": 1,
        "h_c": 1,
    }


def test_cofactor_search_combines_water_protons_and_coefficient_changes():
    model = _model(
        ("a_c", "C2H8O4", 0, "c"),
        ("b_c", "CHO", -1, "c"),
        ("h_c", "H", 1, "c"),
        ("w_c", "H2O", 0, "c"),
        reactions=[("R1", {"a_c": -1, "b_c": 1})],
    )
    model.metabolites.h_c.name = "H+"
    model.metabolites.w_c.name = "H2O"
    [proposal] = conservation.reaction_fixes(model.reactions.R1, model)
    assert proposal.policy == "cofactor-pair"
    assert proposal.after == {"a_c": -1, "b_c": 2, "h_c": 2, "w_c": 2}
    assert proposal.metadata["search"]["rank"] == [2, 1, 5]
    assert proposal.metadata["reaction"]["after"]["elements"]["balanced"]
    assert proposal.metadata["reaction"]["after"]["charge"]["balanced"]
    model.metabolites.w_c.compartment = "m"
    assert conservation.reaction_fixes(model.reactions.R1, model) == []


def test_cofactor_additions_are_bounded():
    model = _model(
        ("a_c", "C2H12O6", 0, "c"),
        ("b_c", "C2HO", -1, "c"),
        ("h_c", "H", 1, "c"),
        ("w_c", "H2O", 0, "c"),
        reactions=[("R1", {"a_c": -1, "b_c": 1})],
    )
    model.metabolites.h_c.name = "H+"
    model.metabolites.w_c.name = "H2O"
    assert conservation.reaction_fixes(model.reactions.R1, model) == []


def test_search_does_not_use_nonoptimal_solver_results(monkeypatch):
    import scipy.optimize

    model = _model(*BASE, reactions=[("R1", {"a_c": -2, "b_c": 1, "h2_c": 1})])
    monkeypatch.setattr(
        scipy.optimize,
        "milp",
        lambda *a, **k: scipy.optimize.OptimizeResult(success=False, status=1),
    )
    assert conservation.coefficient_candidates(model.reactions.R1, model) == []


def test_edited_stoichiometry_must_still_balance_and_preserve_sides():
    model = _model(*BASE, reactions=[("R1", {"a_c": -2, "b_c": 1, "h2_c": 1})])
    [proposal] = conservation.reaction_fixes(model.reactions.R1, model)
    for replacement in (
        {"a_c": -1, "b_c": 1, "h2_c": 2},
        {"a_c": 1, "b_c": -1, "h2_c": -1},
    ):
        with pytest.raises(ProposalError, match="balance elements.*preserve"):
            conservation.apply_conservation_fixes(
                model,
                [proposal],
                [Decision(proposal.proposal_id, "replace", replacement)],
            )


def test_validation_omits_proposals_unless_asked():
    model = _model(*BASE, reactions=[("R2", {"a_c": -1, "b_c": 1})])
    assert "proposals" not in validate_model(model, "structural-fast")


def test_balance_checks_list_pool_reactions_apart_from_real_ones():
    model = _model(
        ("a_c", "C2H6O", 0, "c"),
        ("b_c", "C2H4O", -1, "c"),
        reactions=[
            ("R_real", {"a_c": -1, "b_c": 1}),
            ("R_pool", {"a_c": -1, "b_c": 2}),
        ],
    )
    model.reactions.R_pool.name = "fatty acid pool"
    checks = {c["id"]: c for c in validate_model(model, "structural-fast")["checks"]}
    for check_id in ("mass-balance", "charge-balance"):
        details = checks[check_id]["details"]
        assert details["unbalanced"] == ["R_real"]
        assert details["unbalanced_by_design"] == {"R_pool": "pseudo-name"}
        assert set(details["imbalance"]) == {"R_real", "R_pool"}
    assert checks["mass-balance"]["details"]["imbalance"]["R_real"] == {"H": -2.0}
    assert checks["charge-balance"]["details"]["imbalance"]["R_real"] == -1.0


def test_pool_reactions_alone_pass_the_balance_checks():
    model = _model(
        ("a_c", "C2H6O", 0, "c"),
        ("b_c", "C2H4O", -1, "c"),
        reactions=[("R_pool", {"a_c": -1, "b_c": 2})],
    )
    model.reactions.R_pool.name = "fatty acid pool"
    checks = {c["id"]: c for c in validate_model(model, "structural-fast")["checks"]}
    assert checks["mass-balance"]["passed"] is True
    assert checks["charge-balance"]["passed"] is True


REDOX = [
    ("hete_c", "C20H31O3", -1, "c"),
    ("ltb4_c", "C20H31O4", -1, "c"),
    ("o2_c", "O2", 0, "c"),
    ("h2o_c", "H2O", 0, "c"),
    ("h_c", "H", 1, "c"),
    ("nadp_c", "C21H25N7O17P3", -3, "c"),
    ("nadph_c", "C21H26N7O17P3", -4, "c"),
]


def _redox_model() -> cobra.Model:
    model = _model(
        *REDOX,
        reactions=[
            # A P450 hydroxylation written with 2 H+ instead of NADPH + H+.
            ("P450", {"hete_c": -1, "o2_c": -1, "h_c": -2, "ltb4_c": 1, "h2o_c": 1})
        ],
    )
    names = {"h_c": "H+", "nadp_c": "NADP+", "nadph_c": "NADPH"}
    for metabolite in model.metabolites:
        metabolite.name = names.get(metabolite.id, metabolite.id)
    return model


def test_redox_candidate_fixes_a_charge_only_imbalance():
    model = _redox_model()
    [candidate] = conservation.redox_candidates(model.reactions.P450, model)
    assert candidate["label"] == "NADPH → NADP+"
    after = candidate["after"]
    assert after == {
        "hete_c": -1,
        "o2_c": -1,
        "h_c": -1,
        "nadph_c": -1,
        "ltb4_c": 1,
        "h2o_c": 1,
        "nadp_c": 1,
    }
    assert conservation.element_residual(after, model)["balanced"]
    assert conservation.charge_residual(after, model)["balanced"]
    [proposal] = conservation.reaction_fixes(model.reactions.P450, model)
    assert proposal.policy == "redox-cofactor"


@pytest.mark.parametrize("metabolite_id", ["nadp_c", "nadph_c", "h_c"])
def test_redox_candidates_require_all_cofactor_charges(metabolite_id):
    model = _redox_model()
    model.metabolites.get_by_id(metabolite_id).charge = None
    assert conservation.redox_candidates(model.reactions.P450, model) == []
    assert conservation.reaction_fixes(model.reactions.P450, model) == []


def test_charge_fix_changes_one_metabolite_by_one():
    model = _model(
        ("a_c", "C2H6O", 0, "c"),
        ("b_c", "C2H6O", -1, "c"),
        reactions=[("R1", {"a_c": -1, "b_c": 1})],
    )
    [proposal] = [
        item
        for item in conservation.charge_fixes(model, ["R1"])
        if item.object_id == "b_c"
    ]
    assert (proposal.operation, proposal.before, proposal.after) == (
        "set-charge",
        -1,
        0,
    )
    assert proposal.metadata["targets"] == ["R1"]


def test_apply_rejects_charge_fixes_that_overcorrect_the_same_reaction():
    model = _model(
        ("a_c", "C2H6O", 0, "c"),
        ("b_c", "C2H6O", -1, "c"),
        reactions=[("R1", {"a_c": -1, "b_c": 1})],
    )
    proposals = conservation.charge_fixes(model, ["R1"])
    assert len(proposals) == 2
    for proposal in proposals:
        fixed, _, _ = conservation.apply_conservation_fixes(
            model, proposals, [Decision(proposal.proposal_id, "approve")]
        )
        assert fixed.reactions.R1.check_mass_balance() == {}
    for batch in (proposals, list(reversed(proposals))):
        with pytest.raises(ProposalError, match="conflicting charge fixes.*R1"):
            conservation.apply_conservation_fixes(
                model, batch, [Decision(p.proposal_id, "approve") for p in batch]
            )
    assert (model.metabolites.a_c.charge, model.metabolites.b_c.charge) == (0, -1)


def test_apply_allows_independent_charge_fixes():
    model = _model(
        ("a_c", "C2H6O", 0, "c"),
        ("b_c", "C2H6O", -1, "c"),
        ("d_c", "C2H6O", 0, "c"),
        ("e_c", "C2H6O", -1, "c"),
        reactions=[("R1", {"a_c": -1, "b_c": 1}), ("R2", {"d_c": -1, "e_c": 1})],
    )
    proposals = [
        p
        for p in conservation.charge_fixes(model, ["R1", "R2"])
        if p.object_id in {"b_c", "e_c"}
    ]
    fixed, applied, _ = conservation.apply_conservation_fixes(
        model, proposals, [Decision(p.proposal_id, "approve") for p in proposals]
    )
    assert len(applied) == 2
    assert all(not reaction.check_mass_balance() for reaction in fixed.reactions)


def test_charge_fix_keeps_reactions_that_balance_now():
    model = _model(
        ("a_c", "C2H6O", 0, "c"),
        ("b_c", "C2H6O", -1, "c"),
        ("c_c", "C2H6O", -1, "c"),
        reactions=[("R1", {"a_c": -1, "b_c": 1}), ("R2", {"b_c": -1, "c_c": 1})],
    )
    # b_c -> 0 balances R1 but breaks R2; only a_c -> -1 is safe.
    proposals = conservation.charge_fixes(model, ["R1"])
    assert [(p.object_id, p.after) for p in proposals] == [("a_c", -1)]


def test_topology_and_blocked_checks_group_by_compartment():
    model = _model(*ETHANOL, reactions=TRANSPORT)
    report = validate_model(model, "structural-fast")
    checks = {c["id"]: c for c in report["checks"]}
    assert checks["dead-end-topology"]["details"]["by_compartment"] == {
        "c": ["a_c"],
        "m": ["a_m"],
        "x": ["a_x"],
    }
    assert report["compartments"]["reactions"] == {"c+m": 1, "c+x": 1}
    assert "blocked-reaction-singletons" not in checks


def test_reactions_of_a_pool_metabolite_are_unbalanced_by_design():
    model = _model(
        ("a_c", "C2H6O", 0, "c"),
        ("pool_c", "C2H4O", 0, "c"),
        reactions=[("R1", {"pool_c": -1, "a_c": 1})],
    )
    model.metabolites.pool_c.name = "NEFA blood pool in"
    details = next(
        c["details"]
        for c in validate_model(model, "structural-fast")["checks"]
        if c["id"] == "mass-balance"
    )
    assert details["unbalanced_by_design"] == {"R1": "pool-metabolite"}
