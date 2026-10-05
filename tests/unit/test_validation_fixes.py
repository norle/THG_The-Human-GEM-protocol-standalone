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


def test_malformed_replacement_coefficient_is_a_proposal_error():
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
        proposal.proposal_id, "replace", replacement={"a_c": "abc", "a_m": 1}
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
    ("a_c", "C2H6O", 0, "c"),
    ("b_c", "C2H4O", 0, "c"),
    ("h_c", "H", 1, "c"),
    ("h2_c", "H2", 0, "c"),
]


def test_validation_proposes_fixes_and_merges_checks():
    reference = _model(*BASE, reactions=[("R2", {"a_c": -1, "b_c": 1, "h2_c": 1})])
    model = _model(
        *BASE,
        reactions=[
            # Element and charge imbalance; the reference has it balanced.
            ("R2", {"a_c": -1, "b_c": 1, "h_c": 1}),
            # 1.2 ethanol rounds to the balanced 1.
            ("FR", {"a_c": -1.2, "b_c": 1, "h2_c": 1}),
        ],
    )
    report = validate_model(
        model, "structural-fast", reference_model=reference, propose_fixes=True
    )
    by_object = {item["object_id"]: item for item in report["proposals"]}
    assert by_object["R2"]["policy"] == "restore-input-stoichiometry"
    assert sorted(by_object["R2"]["checks"]) == ["charge-balance", "mass-balance"]
    assert by_object["FR"]["policy"] == "integer-stoichiometry"
    assert by_object["FR"]["after"] == {"a_c": -1, "b_c": 1, "h2_c": 1}
    assert "fractional-coefficients" in by_object["FR"]["checks"]
    index = report["index"]
    assert {"R2", "FR"} <= set(index["reactions"])
    assert index["metabolites"]["a_c"]["formula"] == "C2H6O"


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
