from __future__ import annotations

import json

import pytest
from cobra import Metabolite, Model, Reaction
from cobra.io import save_json_model

from thg_protocol.curation.beta1 import beta1_release_gate
from thg_protocol.curation.beta2 import beta2_release_gate, release_beta2
from thg_protocol.workflow.runner import get_status, resume, start

ROOT = __import__("pathlib").Path(__file__).resolve().parents[2]


def _config(tmp_path, *, external: bool = True):
    model = Model("beta2-fixture")
    left = Metabolite("left_c", formula="C", charge=0, compartment="c")
    right = Metabolite("right_c", formula="C", charge=0, compartment="c")
    reaction = Reaction("R_EXPAND")
    reaction.add_metabolites({left: -1, right: 1})
    reaction.gene_reaction_rule = "G_A or G_B"
    model.add_reactions([reaction])
    source = tmp_path / "beta1-equivalent.json"
    save_json_model(model, source)
    config = tmp_path / "beta2.json"
    config.write_text(
        json.dumps(
            {
                "workflow": "beta2",
                "run": {"name": "beta2-fixture", "output_dir": str(tmp_path / "run")},
                "beta2": {
                    "n_jobs": 2,
                    "input_model": str(source),
                    "external_beta1_equivalent": external,
                    "gene_locations": {"G_A": ["mitochondrion"], "G_B": ["cytosol"]},
                    "compartments": {"c": "cytosol", "m": "mitochondria"},
                    "run_solver_checks": True,
                },
            }
        ),
        encoding="utf-8",
    )
    return config, tmp_path / "run"


def test_beta2_registered_workflow_exports_bundle_and_resumes(tmp_path):
    config, run_dir = _config(tmp_path)
    start(config)
    status = get_status(run_dir)
    assert status["overall_status"] == "completed"
    assert len(status["steps"]) == 15
    export = status["steps"]["export-beta2"]
    assert {item["role"] for item in export["outputs"]} == {
        "model",
        "sbml",
        "validation",
        "plan",
        "proposals",
        "id-registry",
        "ledger",
        "location-evidence",
        "gene-location-evidence",
        "gpr-evidence",
        "reaction-identity-evidence",
        "reaction-location-evidence",
        "compartment-resolution-evidence",
        "location-reconciliation",
        "go-release",
        "go-compartment-subgraph",
        "evidence-snapshot",
        "diff",
        "unresolved",
        "summary",
        "provenance",
    }
    attempts = {stage: entry["attempt"] for stage, entry in status["steps"].items()}
    resume(run_dir)
    assert {
        stage: entry["attempt"] for stage, entry in get_status(run_dir)["steps"].items()
    } == attempts
    resume(run_dir, force_step="collect-location-evidence")
    rerun = get_status(run_dir)["steps"]
    assert rerun["load-beta1"]["attempt"] == attempts["load-beta1"]
    assert (
        rerun["collect-location-evidence"]["attempt"]
        == attempts["collect-location-evidence"] + 1
    )
    assert rerun["export-beta2"]["attempt"] == attempts["export-beta2"] + 1


def test_beta2_rejects_unlabelled_direct_input(tmp_path):
    config, run_dir = _config(tmp_path, external=False)
    with pytest.raises(RuntimeError, match="stage 'load-beta1' failed"):
        start(config)
    assert get_status(run_dir)["steps"]["load-beta1"]["status"] == "failed"


def test_beta2_consumes_only_verified_beta1_export(tmp_path):
    beta2_config, _ = _config(tmp_path)
    beta1_run = tmp_path / "beta1-run"
    beta1_config = tmp_path / "beta1.json"
    payload = json.loads(beta2_config.read_text(encoding="utf-8"))
    source = payload["beta2"]["input_model"]
    beta1_config.write_text(
        json.dumps(
            {
                "workflow": "beta1",
                "run": {"name": "beta1-fixture", "output_dir": str(beta1_run)},
                "beta1": {"input_model": source, "mode": "apply-all"},
            }
        ),
        encoding="utf-8",
    )
    start(beta1_config)
    payload["run"]["output_dir"] = str(tmp_path / "chained-run")
    payload["beta2"].pop("input_model")
    payload["beta2"].pop("external_beta1_equivalent")
    payload["beta2"]["upstream"] = {
        "run_dir": str(beta1_run),
        "stage_id": "export-beta1",
        "role": "model",
    }
    beta2_config.write_text(json.dumps(payload), encoding="utf-8")
    start(beta2_config)
    assert get_status(tmp_path / "chained-run")["overall_status"] == "completed"


def test_sanctioned_beta1_to_beta2_candidate_passes_gate(tmp_path):
    fixture = ROOT / "tests/fixtures/beta1/sanctioned_human_reference.json"
    beta1_run = tmp_path / "sanctioned-beta1"
    beta1_config = tmp_path / "sanctioned-beta1.json"
    beta1_config.write_text(
        json.dumps(
            {
                "workflow": "beta1",
                "run": {"name": "sanctioned-beta1", "output_dir": str(beta1_run)},
                "beta1": {
                    "input_model": str(fixture),
                    "sanctioned_model": True,
                    "run_solver_checks": True,
                },
            }
        ),
        encoding="utf-8",
    )
    start(beta1_config)
    beta1_status = get_status(beta1_run)
    export = beta1_status["steps"]["export-beta1"]["outputs"][0]
    beta1_bundle = beta1_run / __import__("pathlib").Path(export["path"]).parent
    assert beta1_release_gate(beta1_bundle)["ready"]
    beta2_run = tmp_path / "sanctioned-beta2"
    beta2_config = tmp_path / "sanctioned-beta2.json"
    beta2_config.write_text(
        json.dumps(
            {
                "workflow": "beta2",
                "run": {"name": "sanctioned-beta2", "output_dir": str(beta2_run)},
                "beta2": {
                    "upstream": {
                        "run_dir": str(beta1_run),
                        "stage_id": "export-beta1",
                        "role": "model",
                    },
                    "gene_locations": {
                        "ENSG000001": ["cytosol"],
                        "ENSG000002": ["mitochondria"],
                    },
                    "compartments": {"c": "cytosol", "m": "mitochondria"},
                    "run_solver_checks": True,
                },
            }
        ),
        encoding="utf-8",
    )
    start(beta2_config)
    status = get_status(beta2_run)
    export_dir = (
        beta2_run
        / __import__("pathlib")
        .Path(status["steps"]["export-beta2"]["outputs"][0]["path"])
        .parent
    )
    gate = beta2_release_gate(export_dir)
    assert gate["passed"], gate["reasons"]
    release = release_beta2(export_dir)
    assert __import__("pathlib").Path(release["json"]).name == "thg-beta2.json"
