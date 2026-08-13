from __future__ import annotations

import json

from cobra import Metabolite, Model, Reaction
from cobra.core import Group
from cobra.io import load_json_model, save_json_model

from thg_protocol.curation.beta1 import (
    MetaboliteCandidate,
    apply_cleanup_proposals,
    apply_model_proposals,
    audit_model,
    audit_reaction,
    beta1_release_gate,
    compare_reaction_identity,
    consolidate_model,
    duplicate_reaction_groups,
    generate_balance_proposals,
    generate_cleanup_proposals,
    generate_curation_proposals,
    inventory_model,
    parse_gpr,
    protonation_relation,
    resolve_metabolite_identity,
    run_beta1,
    serialize_gpr,
    serialize_s_gpr,
    with_subunit_stoichiometry,
)
from thg_protocol.workflow.proposals import Decision


def _model() -> Model:
    model = Model("beta1-fixture")
    a = Metabolite("a_c", name="A", formula="C", charge=0, compartment="c")
    b = Metabolite("b_c", name="B", formula="C", charge=0, compartment="c")
    reaction = Reaction("R_A")
    reaction.gene_reaction_rule = "G2 and (G1 or G3)"
    reaction.add_metabolites({a: -1, b: 1})
    model.add_reactions([reaction])
    return model


def test_inventory_and_audit_are_non_mutating_and_explicit_about_scope():
    model = _model()
    before = json.dumps(model.annotation, sort_keys=True)
    report = inventory_model(model)
    audit = audit_reaction(model.reactions.R_A)
    assert report.counts == {"metabolites": 2, "reactions": 1, "genes": 3}
    assert audit.mass_status == "balanced"
    assert audit.charge_status == "balanced"
    assert json.dumps(model.annotation, sort_keys=True) == before


def test_parallel_balance_audit_matches_serial_results():
    model = _model()
    serial = [item.to_dict() for item in audit_model(model)]
    parallel = [item.to_dict() for item in audit_model(model, n_jobs=2)]
    assert parallel == serial


def test_gpr_round_trip_is_canonical_and_identity_ties_remain_unresolved():
    assert serialize_gpr(parse_gpr("G3 or (G1 and G2)")) == "G1 and G2 or G3"
    result = resolve_metabolite_identity(
        [
            {"identity": "CHEBI:1", "namespace": "chebi", "score": 1},
            {"identity": "CHEBI:2", "namespace": "chebi", "score": 1},
        ]
    )
    assert result["status"] == "ambiguous"
    assert result["selected"] is None
    cross_database = resolve_metabolite_identity(
        [
            {"identity": "CHEBI:1", "namespace": "chebi", "score": 1},
            {"identity": "C00001", "namespace": "kegg", "score": 1},
            {"identity": "SBO:0000247", "namespace": "sbo", "score": 1},
        ]
    )
    assert cross_database["status"] == "matched"
    assert cross_database["selected"]["namespace"] == "chebi"
    assert len(cross_database["candidates"]) == 3
    model = _model()
    model.metabolites.a_c.annotation = {"sbo": ["SBO:0000247"]}
    identity_proposals = generate_curation_proposals(
        model, metabolite_identities={"a_c": cross_database}
    )
    identity = next(
        item for item in identity_proposals if item.operation == "annotate-identity"
    )
    assert identity.after["chebi"] == ["1"]
    assert identity.after["kegg"] == ["C00001"]
    assert identity.after["sbo"] == ["SBO:0000247"]
    ranked = resolve_metabolite_identity(
        [
            MetaboliteCandidate(
                "CHEBI:1",
                "chebi",
                structural_identifiers=("InChI=1",),
                name="water",
            ),
            MetaboliteCandidate("CHEBI:2", "chebi", formula="H2O", charge=0),
        ],
        reference_name="water",
        reference_formula="H2O",
        reference_charge=0,
        reference_structural_identifiers=("InChI=1",),
    )
    assert ranked["selected"]["identity"] == "1"
    assert (
        protonation_relation(
            MetaboliteCandidate(
                "A", "x", charge=0, structural_identifiers=("S",), compartment="c"
            ),
            MetaboliteCandidate(
                "B", "x", charge=1, structural_identifiers=("S",), compartment="e"
            ),
        )["relationship"]
        == "protonation-state"
    )


def test_balance_proposals_are_separate_from_application():
    model = _model()
    proposals = generate_balance_proposals(model, corrections={"R_A": {"a_c": 1}})
    assert len(proposals) == 1
    assert model.reactions.R_A.metabolites[model.metabolites.a_c] == -1
    assert proposals[0].metadata["imbalance_before"]["reaction_id"] == "R_A"


def test_proton_water_strategy_only_proposes_a_verified_local_repair():
    model = Model("proton-water")
    water = Metabolite("h2o_c", formula="H2O", charge=0, compartment="c")
    proton = Metabolite("h_c", formula="H", charge=1, compartment="c")
    reaction = Reaction("R_RESIDUAL")
    reaction.add_metabolites({water: -1, proton: 1})
    model.add_reactions([reaction])

    proposals = generate_balance_proposals(model)

    assert len(proposals) == 1
    assert proposals[0].policy == "proton-water"
    assert proposals[0].metadata["imbalance_after"]["mass_status"] == "balanced"
    assert proposals[0].metadata["imbalance_after"]["charge_status"] == "balanced"


def test_reaction_identity_supports_reversal_and_explicit_proton_water_policy():
    model = _model()
    reaction = model.reactions.R_A
    reversed_result = compare_reaction_identity(reaction, {"a_c": 1, "b_c": -1})
    assert reversed_result.status == "equivalent-reversed"
    assert reversed_result.normalization_policy == "strict"


def test_balance_audit_distinguishes_missing_and_generic_formula_cases():
    model = Model("audit-fixture")
    missing = Metabolite("missing_c", charge=0, compartment="c")
    generic = Metabolite("generic_c", formula="C1R", charge=0, compartment="c")
    product = Metabolite("product_c", formula="C", charge=0, compartment="c")
    reaction = Reaction("R_MISSING")
    reaction.add_metabolites({missing: -1, product: 1})
    generic_reaction = Reaction("R_GENERIC")
    generic_reaction.add_metabolites({generic: -1, product: 1})
    model.add_reactions([reaction, generic_reaction])
    assert audit_reaction(reaction).mass_status == "not-evaluable-missing-formula"
    assert audit_reaction(generic_reaction).mass_status == "excluded-generic-formula"
    assert (
        audit_reaction(generic_reaction, formula_policy={}).mass_status
        == "not-evaluable-generic-formula"
    )


def test_generic_formula_policy_can_explicitly_exclude_generic_species():
    model = Model("generic-policy")
    generic = Metabolite(
        "glycan_c",
        name="generic glycan polymer",
        formula="C1R",
        charge=0,
        compartment="c",
    )
    product = Metabolite("product_c", formula="C", charge=0, compartment="c")
    reaction = Reaction("R_GENERIC_POLICY")
    reaction.add_metabolites({generic: -1, product: 1})
    model.add_reactions([reaction])
    policy = {"glycan": "exclude", "r-group": "exclude"}
    audit = audit_reaction(reaction, formula_policy=policy)
    assert audit.mass_status == "excluded-generic-formula"
    assert audit.formula_classes == ("glycan", "r-group")
    assert audit.to_dict()["formula_policy"] == policy


def test_inventory_records_identifier_and_gpr_coverage():
    model = _model()
    model.metabolites.a_c.annotation = {"chebi": ["CHEBI:1"], "kegg": "C00001"}
    model.reactions.R_A.gene_reaction_rule = ""
    report = inventory_model(model)
    assert report.identifier_coverage == {"chebi": 1, "kegg": 1}
    assert report.missing_gpr == ("R_A",)
    assert report.invalid_references == ()


def test_reversed_identity_is_a_flagging_proposal_and_not_a_stoichiometric_mutation():
    model = _model()
    result = compare_reaction_identity(model.reactions.R_A, {"a_c": 1, "b_c": -1})
    proposals = generate_curation_proposals(
        model,
        reaction_identities={"R_A": result.__dict__},
    )
    assert proposals[0].operation == "flag-reaction-directionality"
    curated, ledger = apply_model_proposals(model, proposals)
    assert {
        metabolite.id: coefficient
        for metabolite, coefficient in curated.reactions.R_A.metabolites.items()
    } == {
        metabolite.id: coefficient
        for metabolite, coefficient in model.reactions.R_A.metabolites.items()
    }
    assert curated.reactions.R_A.annotation["thg_directionality"]["reversed"] is True
    assert ledger[0]["status"] == "applied"


def test_identity_conflicts_and_s_gpr_metadata_are_explicit_proposals():
    model = _model()
    proposals = generate_curation_proposals(
        model,
        reaction_identities={
            "R_A": {
                "status": "conflict",
                "reason": "reference coefficients conflict",
                "normalization_policy": "strict",
            }
        },
        subunit_stoichiometry={"R_A": {"G2": 2, "G1": 1}},
    )
    assert {item.operation for item in proposals} == {
        "flag-reaction-identity",
        "annotate-s-gpr",
    }
    curated, _ = apply_model_proposals(model, proposals)
    assert curated.reactions.R_A.annotation["thg_identity"]["status"] == "conflict"
    assert curated.reactions.R_A.annotation["thg_s_gpr"]["gpr"] == ("G2 and (G1 or G3)")
    assert with_subunit_stoichiometry("G2 and G1", {"G2": 2}).to_dict() == {
        "and": [
            {"gene": "G1"},
            {"gene": "G2", "subunit_stoichiometry": {"G2": 2.0}},
        ]
    }
    assert serialize_s_gpr("G2 and G1", {"G2": 2})["gpr"] == "G1 and G2"


def test_duplicate_cleanup_is_deterministic_and_merges_annotations():
    model = Model("duplicates")
    first = Metabolite("z_c", name="Z", formula="C", charge=0, compartment="c")
    second = Metabolite("a_c", name="A", formula="C", charge=0, compartment="c")
    first.annotation = {"chebi": "1"}
    second.annotation = {"chebi": "1", "kegg": "C00001"}
    model.add_metabolites([first, second])
    r1 = Reaction("R_Z")
    r2 = Reaction("R_A")
    r1.add_metabolites({first: -1})
    r2.add_metabolites({first: -1})
    model.add_reactions([r1, r2])
    assert duplicate_reaction_groups(model) == (("R_A", "R_Z"),)
    cleaned, report = consolidate_model(model)
    assert [item.id for item in cleaned.metabolites] == ["a_c"]
    assert cleaned.metabolites.a_c.annotation == {
        "chebi": ["1"],
        "kegg": "C00001",
    }
    assert report["retained_metabolites"] == {"z_c": "a_c"}


def test_run_beta1_writes_reproducible_candidate_bundle_without_overwriting_input(
    tmp_path,
):
    source = tmp_path / "input.json"
    original = _model()
    save_json_model(original, source)
    source_bytes = source.read_bytes()
    result = run_beta1(source, tmp_path / "run")
    outputs = result["outputs"]
    assert {
        "json",
        "sbml",
        "signature",
        "proposals",
        "ledger",
        "validation",
        "unresolved",
        "inventory",
        "summary",
    } <= set(outputs)
    reloaded = load_json_model(outputs["json"])
    assert reloaded.id == original.id
    assert source.read_bytes() == source_bytes
    assert json.loads((tmp_path / "run" / "beta1-validation.json").read_text())[
        "all_ids_unique"
    ]
    gate = beta1_release_gate(tmp_path / "run")
    assert not gate["ready"]
    assert "sanctioned human-model run" in " ".join(gate["reasons"])


def test_report_only_and_user_approved_modes_do_not_run_implicit_cleanup(tmp_path):
    model = Model("mode-fixture")
    first = Metabolite("z_c", formula="C", charge=0, compartment="c")
    second = Metabolite("a_c", formula="C", charge=0, compartment="c")
    first.annotation = {"chebi": "1"}
    second.annotation = {"chebi": "1"}
    reaction = Reaction("R_MODE")
    reaction.add_metabolites({first: -1, second: 1})
    model.add_reactions([reaction])
    source = tmp_path / "mode-input.json"
    save_json_model(model, source)

    for mode in ("report-only", "user-approved-only"):
        result = run_beta1(source, tmp_path / mode, mode=mode)
        assert len(result["model"].metabolites) == 2
        assert result["cleanup"]["removed_metabolites"] == []


def test_gene_mapping_cleanup_removes_rewritten_aliases(tmp_path):
    source = tmp_path / "gene-input.json"
    save_json_model(_model(), source)

    result = run_beta1(source, tmp_path / "gene-run", gene_mapping={"G1": "G2"})

    assert "G1" not in {gene.id for gene in result["model"].genes}
    assert result["model"].reactions.R_A.gene_reaction_rule == "G2 and (G2 or G3)"
    assert result["cleanup"]["removed_genes"] == ["G1"]


def test_cleanup_is_a_decisionable_proposal_and_rejection_preserves_duplicates():
    model = Model("cleanup-proposal")
    first = Metabolite("z_c", formula="C", charge=0, compartment="c")
    second = Metabolite("a_c", formula="C", charge=0, compartment="c")
    first.annotation = {"chebi": "1"}
    second.annotation = {"chebi": "1"}
    reaction = Reaction("R_CLEANUP")
    reaction.add_metabolites({first: -1, second: 1})
    model.add_reactions([reaction])

    proposals, _ = generate_cleanup_proposals(model)
    assert len(proposals) == 1
    cleaned, ledger, report = apply_cleanup_proposals(
        model,
        proposals,
        mode="user-approved-only",
    )
    assert len(cleaned.metabolites) == 2
    assert report["removed_metabolites"] == []
    assert ledger[0]["status"] == "unresolved"

    rejected, rejected_ledger, rejected_report = apply_cleanup_proposals(
        model,
        proposals,
        mode="apply-all",
        decisions=(
            Decision(
                proposal_id=proposals[0].proposal_id,
                action="reject",
                reason="retain both records for review",
            ),
        ),
    )
    assert len(rejected.metabolites) == 2
    assert rejected_report["removed_metabolites"] == []
    assert rejected_ledger[0]["status"] == "rejected"


def test_metabolite_cleanup_remaps_group_members():
    model = Model("group-fixture")
    first = Metabolite("z_c", formula="C", charge=0, compartment="c")
    second = Metabolite("a_c", formula="C", charge=0, compartment="c")
    first.annotation = {"chebi": "1"}
    second.annotation = {"chebi": "1"}
    reaction = Reaction("R_GROUP")
    reaction.add_metabolites({first: -1, second: 1})
    model.add_reactions([reaction])
    group = Group("group")
    group.add_members([first, second])
    model.add_groups([group])

    cleaned, report = consolidate_model(model)

    assert report["removed_metabolites"] == ["z_c"]
    assert [member.id for member in cleaned.groups.group.members] == ["a_c"]


def test_missing_formula_blocks_beta1_release_gate(tmp_path):
    model = Model("missing-formula")
    missing = Metabolite("missing_c", charge=0, compartment="c")
    present = Metabolite("present_c", formula="C", charge=0, compartment="c")
    reaction = Reaction("R_MISSING")
    reaction.add_metabolites({missing: -1, present: 1})
    model.add_reactions([reaction])
    source = tmp_path / "missing-input.json"
    save_json_model(model, source)

    run_beta1(source, tmp_path / "missing-run", sanctioned_model=True)
    gate = beta1_release_gate(tmp_path / "missing-run")

    assert not gate["ready"]
    assert "unresolved validation exceptions" in " ".join(gate["reasons"])


def test_release_gate_rejects_self_declared_sanctioned_input(tmp_path):
    source = tmp_path / "valid-but-unapproved.json"
    model = _model()
    save_json_model(model, source)

    run_beta1(source, tmp_path / "unapproved-run", sanctioned_model=True)
    gate = beta1_release_gate(tmp_path / "unapproved-run")

    assert not gate["ready"]
    assert "maintained sanctioned β1 fixture" in " ".join(gate["reasons"])
