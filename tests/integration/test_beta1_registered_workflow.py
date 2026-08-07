from __future__ import annotations

import json
from pathlib import Path

from cobra import Metabolite, Model, Reaction
from cobra.io import save_json_model

from thg_protocol.curation.beta1 import beta1_release_gate, release_beta1
from thg_protocol.workflow.manifest import load_workflow_manifest
from thg_protocol.workflow.registry import REGISTRY
from thg_protocol.workflow.runner import get_status, resume, start

ROOT = Path(__file__).resolve().parents[2]


def test_configured_beta1_workflow_produces_candidate_and_resumes(tmp_path):
    model = Model("configured-beta1")
    left = Metabolite("left_c", formula="C", charge=0, compartment="c")
    right = Metabolite("right_c", formula="C", charge=0, compartment="c")
    left.annotation = {"chebi": "1"}
    reaction = Reaction("R_COPY")
    reaction.add_metabolites({left: -1, right: 1})
    model.add_reactions([reaction])
    input_model = tmp_path / "input.json"
    save_json_model(model, input_model)
    run_dir = tmp_path / "run"
    config = tmp_path / "config.json"
    config.write_text(
        json.dumps(
            {
                "format_version": 2,
                "workflow": "beta1",
                "run": {"name": "configured", "output_dir": str(run_dir)},
                "beta1": {
                    "input_model": "input.json",
                    "mode": "apply-all",
                    "balance_strategy": "explicit-only",
                },
            }
        ),
        encoding="utf-8",
    )
    start(config)
    status = get_status(run_dir)
    assert status["overall_status"] == "completed"
    assert len(status["steps"]) == 16
    assert REGISTRY.get("beta1").scientific_stage_ids[-1] == "export-beta1"
    for stage_id in REGISTRY.get("beta1").scientific_stage_ids:
        assert REGISTRY.contracts.get(stage_id).workflow == "beta1"
    export = status["steps"]["export-beta1"]["outputs"]
    assert export[0]["role"] == "model"
    assert (run_dir / export[0]["path"]).is_file()
    assert "candidate" in export[0]["path"]
    evidence = status["steps"]["collect-metabolite-evidence"]["outputs"][0]
    evidence_payload = json.loads(
        (run_dir / evidence["path"]).read_text(encoding="utf-8")
    )
    assert evidence_payload["records"]["left_c"]["candidates"][0]["identity"] == "1"
    reaction_identity = status["steps"]["resolve-reaction-identities"]["outputs"][0]
    reaction_payload = json.loads(
        (run_dir / reaction_identity["path"]).read_text(encoding="utf-8")
    )
    assert reaction_payload["resolutions"]["R_COPY"]["status"] == "not-evaluated"
    attempts = status["steps"]["generate-curation-proposals"]["attempt"]
    resume(run_dir)
    assert (
        get_status(run_dir)["steps"]["generate-curation-proposals"]["attempt"]
        == attempts
    )
    assert load_workflow_manifest(run_dir)["workflow"] == "beta1"


def test_reaction_identity_stage_uses_resolved_metabolite_identities(tmp_path):
    model = Model("identity-wiring")
    left = Metabolite("left_c", formula="C", charge=0, compartment="c")
    right = Metabolite("right_c", formula="C", charge=0, compartment="c")
    reaction = Reaction("R_IDENTITY")
    reaction.add_metabolites({left: -1, right: 1})
    model.add_reactions([reaction])
    input_model = tmp_path / "input.json"
    save_json_model(model, input_model)
    run_dir = tmp_path / "run"
    config = tmp_path / "config.json"
    config.write_text(
        json.dumps(
            {
                "format_version": 2,
                "workflow": "beta1",
                "run": {"name": "identity-wiring", "output_dir": str(run_dir)},
                "beta1": {
                    "input_model": str(input_model),
                    "metabolite_evidence": {
                        "left_c": {
                            "candidates": [
                                {"namespace": "test", "identity": "A", "score": 1}
                            ]
                        },
                        "right_c": {
                            "candidates": [
                                {"namespace": "test", "identity": "B", "score": 1}
                            ]
                        },
                    },
                    "reaction_evidence": {
                        "R_IDENTITY": {"stoichiometry": {"A": -1, "B": 1}}
                    },
                },
            }
        ),
        encoding="utf-8",
    )

    start(config)
    manifest = load_workflow_manifest(run_dir)
    output = manifest["steps"]["resolve-reaction-identities"]["outputs"][0]
    payload = json.loads((run_dir / output["path"]).read_text(encoding="utf-8"))

    assert payload["resolutions"]["R_IDENTITY"]["status"] == "exact"


def test_reaction_identity_stage_accepts_reaction_identities_configuration(tmp_path):
    model = Model("identity-config")
    left = Metabolite("left_c", formula="C", charge=0, compartment="c")
    right = Metabolite("right_c", formula="C", charge=0, compartment="c")
    reaction = Reaction("R_CONFIG")
    reaction.add_metabolites({left: -1, right: 1})
    model.add_reactions([reaction])
    input_model = tmp_path / "input.json"
    save_json_model(model, input_model)
    run_dir = tmp_path / "run"
    config = tmp_path / "config.json"
    config.write_text(
        json.dumps(
            {
                "format_version": 2,
                "workflow": "beta1",
                "run": {"name": "identity-config", "output_dir": str(run_dir)},
                "beta1": {
                    "input_model": str(input_model),
                    "metabolite_identities": {
                        "left_c": {
                            "candidates": [
                                {"namespace": "test", "identity": "A", "score": 1}
                            ]
                        },
                        "right_c": {
                            "candidates": [
                                {"namespace": "test", "identity": "B", "score": 1}
                            ]
                        },
                    },
                    "reaction_identities": {
                        "R_CONFIG": {"stoichiometry": {"A": -1, "B": 1}}
                    },
                },
            }
        ),
        encoding="utf-8",
    )

    start(config)
    manifest = load_workflow_manifest(run_dir)
    output = manifest["steps"]["resolve-reaction-identities"]["outputs"][0]
    payload = json.loads((run_dir / output["path"]).read_text(encoding="utf-8"))

    assert payload["resolutions"]["R_CONFIG"]["status"] == "exact"


def test_recorded_service_failure_is_preserved_as_evidence_and_resumes_offline(
    tmp_path,
):
    model = Model("recorded-evidence")
    metabolite = Metabolite("a_c", formula="C", charge=0, compartment="c")
    product = Metabolite("b_c", formula="C", charge=0, compartment="c")
    reaction = Reaction("R_EVIDENCE")
    reaction.add_metabolites({metabolite: -1, product: 1})
    model.add_reactions([reaction])
    input_model = tmp_path / "input.json"
    save_json_model(model, input_model)
    run_dir = tmp_path / "run"
    config = tmp_path / "config.json"
    config.write_text(
        json.dumps(
            {
                "format_version": 2,
                "workflow": "beta1",
                "run": {"name": "recorded-evidence", "output_dir": str(run_dir)},
                "beta1": {
                    "input_model": str(input_model),
                    "metabolite_evidence": {
                        "a_c": {
                            "candidates": [],
                            "errors": ["service timeout"],
                            "retry_history": [{"attempt": 1, "status": "timeout"}],
                        }
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    start(config)
    status = get_status(run_dir)
    evidence_path = status["steps"]["collect-metabolite-evidence"]["outputs"][0]["path"]
    evidence = json.loads((run_dir / evidence_path).read_text(encoding="utf-8"))[
        "records"
    ]["a_c"]
    assert evidence["schema_version"] == 1
    assert evidence["normalized_result_sha256"]
    assert evidence["retry_history"] == [{"attempt": 1, "status": "timeout"}]
    identity_path = status["steps"]["resolve-metabolite-identities"]["outputs"][0][
        "path"
    ]
    identity = json.loads((run_dir / identity_path).read_text(encoding="utf-8"))[
        "resolutions"
    ]["a_c"]
    assert identity["status"] == "service-failure"
    attempt = status["steps"]["resolve-metabolite-identities"]["attempt"]
    resume(run_dir)
    assert (
        get_status(run_dir)["steps"]["resolve-metabolite-identities"]["attempt"]
        == attempt
    )


def test_sanctioned_fixture_passes_candidate_release_gate(tmp_path):
    fixture = ROOT / "tests/fixtures/beta1/sanctioned_human_reference.json"
    run_dir = tmp_path / "sanctioned-run"
    config = tmp_path / "sanctioned-config.json"
    config.write_text(
        json.dumps(
            {
                "format_version": 2,
                "workflow": "beta1",
                "run": {"name": "sanctioned", "output_dir": str(run_dir)},
                "beta1": {
                    "input_model": str(fixture),
                    "sanctioned_model": True,
                    "run_solver_checks": True,
                },
            }
        ),
        encoding="utf-8",
    )
    start(config)
    manifest = load_workflow_manifest(run_dir)
    export = manifest["steps"]["export-beta1"]
    bundle = run_dir / Path(export["outputs"][0]["path"]).parent
    gate = beta1_release_gate(bundle)
    assert gate["ready"]
    assert gate["label"] == "THGβ1"
    release = release_beta1(bundle, tmp_path / "released")
    assert Path(release["json"]).name == "thg-beta1.json"
    assert Path(release["sbml"]).name == "thg-beta1.xml"


def test_detailed_beta1_force_rerun_invalidates_only_descendants(tmp_path):
    fixture = ROOT / "tests/fixtures/beta1/sanctioned_human_reference.json"
    run_dir = tmp_path / "rerun"
    config = tmp_path / "rerun-config.json"
    config.write_text(
        json.dumps(
            {
                "format_version": 2,
                "workflow": "beta1",
                "run": {"name": "rerun", "output_dir": str(run_dir)},
                "beta1": {"input_model": str(fixture)},
            }
        ),
        encoding="utf-8",
    )
    start(config)
    before = get_status(run_dir)
    attempts = {stage: entry["attempt"] for stage, entry in before["steps"].items()}
    resume(run_dir, force_step="balance-audit")
    after = get_status(run_dir)
    assert (
        after["steps"]["collect-reaction-evidence"]["attempt"]
        == attempts["collect-reaction-evidence"]
    )
    assert after["steps"]["balance-audit"]["attempt"] == attempts["balance-audit"] + 1
    assert after["steps"]["export-beta1"]["attempt"] == attempts["export-beta1"] + 1
