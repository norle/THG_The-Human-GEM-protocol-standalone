from __future__ import annotations

import json

import pytest

from thg_protocol.workflow.manifest import load_workflow_manifest
from thg_protocol.workflow.registered_runner import RegisteredWorkflowError
from thg_protocol.workflow.runner import get_status, resume, start


def _config(path, workflow, output, section=None):
    payload = {
        "format_version": 2,
        "workflow": workflow,
        "run": {"name": workflow, "output_dir": str(output)},
    }
    if section is not None:
        payload[workflow] = section
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_registered_dags_resume_force_and_upstream_chaining(tmp_path):
    beta1 = start(_config(tmp_path / "beta1.json", "beta1", tmp_path / "beta1-run"))
    beta1_manifest = load_workflow_manifest(beta1)
    beta1_export = beta1_manifest["steps"]["beta1-export"]["outputs"][0]
    beta2 = start(
        _config(
            tmp_path / "beta2.json",
            "beta2",
            tmp_path / "beta2-run",
            {
                "upstream": [
                    {
                        "run_dir": str(beta1),
                        "stage_id": "beta1-export",
                        "role": "model",
                        "sha256": beta1_export["sha256"],
                    }
                ]
            },
        )
    )
    status = get_status(beta2)
    assert status["overall_status"] == "completed"
    input_path = beta2 / status["steps"]["beta2-input"]["outputs"][0]["path"]
    input_payload = json.loads(input_path.read_text(encoding="utf-8"))
    assert (
        input_payload["provenance"]["upstream"]["artifacts"][0]["stage_id"]
        == "beta1-export"
    )
    first_attempts = {
        stage: entry["attempt"] for stage, entry in status["steps"].items()
    }
    resume(beta2, force_step="beta2-proposals")
    rerun = get_status(beta2)
    assert (
        rerun["steps"]["beta2-evidence"]["attempt"] == first_attempts["beta2-evidence"]
    )
    assert (
        rerun["steps"]["beta2-proposals"]["attempt"]
        == first_attempts["beta2-proposals"] + 1
    )
    assert (
        rerun["steps"]["beta2-export"]["attempt"] == first_attempts["beta2-export"] + 1
    )

    beta1_export_path = beta1 / beta1_export["path"]
    beta1_export_path.write_text("corrupted\n", encoding="utf-8")
    with pytest.raises(RegisteredWorkflowError, match="changed"):
        start(
            _config(
                tmp_path / "beta2-corrupt.json",
                "beta2",
                tmp_path / "beta2-corrupt-run",
                {
                    "upstream": [
                        {
                            "run_dir": str(beta1),
                            "stage_id": "beta1-export",
                            "role": "model",
                        }
                    ]
                },
            )
        )


def test_registered_config_snapshot_is_self_contained_and_cli_aliases_exist(tmp_path):
    config = _config(tmp_path / "config.json", "beta1", tmp_path / "run")
    run = start(config)
    config.unlink()
    assert resume(run) == run
    assert load_workflow_manifest(run)["workflow"] == "beta1"

    wrong = _config(tmp_path / "wrong.json", "beta2", tmp_path / "wrong-run")
    from thg_protocol.workflow.cli import main

    assert main(["beta1", str(wrong)]) == 2


def test_decision_file_change_invalidates_application_and_descendants(tmp_path):
    decisions = tmp_path / "decisions.jsonl"
    run = start(
        _config(
            tmp_path / "decision-config.json",
            "beta1",
            tmp_path / "decision-run",
            {"decisions_file": str(decisions)},
        )
    )
    before = get_status(run)
    attempts = {stage: entry["attempt"] for stage, entry in before["steps"].items()}
    decisions.write_text('{"proposal_id":"p1","action":"approve"}\n', encoding="utf-8")
    resume(run)
    after = get_status(run)
    assert after["steps"]["beta1-evidence"]["attempt"] == attempts["beta1-evidence"]
    assert (
        after["steps"]["beta1-proposals"]["attempt"] == attempts["beta1-proposals"] + 1
    )
    assert after["steps"]["beta1-export"]["attempt"] == attempts["beta1-export"] + 1
