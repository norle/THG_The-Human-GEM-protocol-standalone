from __future__ import annotations

import json
from pathlib import Path

import pytest

from thg_protocol.runtime.manifest import load_manifest
from thg_protocol.workflow.config import ConfigError
from thg_protocol.workflow.runner import WorkflowError, get_status, resume, start

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODEL = ROOT / "tests/fixtures/beta1/sanctioned_human_reference.json"


def _config(path, workflow, output, section=None):
    payload = {
        "workflow": workflow,
        "run": {"name": workflow, "output_dir": str(output)},
    }
    section = dict(section or {})
    if workflow in {"beta1", "beta2"} and not {
        "input_model",
        "upstream",
    } & section.keys():
        section["input_model"] = str(DEFAULT_MODEL)
    if section:
        payload[workflow] = section
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_registered_dags_resume_force_and_upstream_chaining(tmp_path):
    beta1 = start(_config(tmp_path / "beta1.json", "beta1", tmp_path / "beta1-run"))
    beta1_manifest = load_manifest(beta1)
    beta1_export = beta1_manifest["steps"]["export-beta1"]["outputs"][0]
    beta2 = start(
        _config(
            tmp_path / "beta2.json",
            "beta2",
            tmp_path / "beta2-run",
            {
                "upstream": {
                    "run_dir": str(beta1),
                    "stage_id": "export-beta1",
                    "role": "model",
                    "sha256": beta1_export["sha256"],
                }
            },
        )
    )
    status = get_status(beta2)
    assert status["overall_status"] == "completed"
    input_gate = status["steps"]["load-beta1"]["outputs"][1]
    input_payload = json.loads((beta2 / input_gate["path"]).read_text(encoding="utf-8"))
    assert input_payload["passed"] is True
    assert input_payload["external_beta1_equivalent"] is False
    first_attempts = {
        stage: entry["attempt"] for stage, entry in status["steps"].items()
    }
    resume(beta2, force_step="generate-expansion-plan")
    rerun = get_status(beta2)
    assert (
        rerun["steps"]["collect-catalysis-evidence"]["attempt"]
        == first_attempts["collect-catalysis-evidence"]
    )
    assert (
        rerun["steps"]["generate-expansion-plan"]["attempt"]
        == first_attempts["generate-expansion-plan"] + 1
    )
    assert (
        rerun["steps"]["export-beta2"]["attempt"] == first_attempts["export-beta2"] + 1
    )

    beta1_export_path = beta1 / beta1_export["path"]
    beta1_export_path.write_text("corrupted\n", encoding="utf-8")
    with pytest.raises(WorkflowError, match="changed"):
        start(
            _config(
                tmp_path / "beta2-corrupt.json",
                "beta2",
                tmp_path / "beta2-corrupt-run",
                {
                    "upstream": {
                        "run_dir": str(beta1),
                        "stage_id": "export-beta1",
                        "role": "model",
                    }
                },
            )
        )


def test_registered_config_snapshot_is_self_contained_and_cli_aliases_exist(tmp_path):
    config = _config(tmp_path / "config.json", "beta1", tmp_path / "run")
    run = start(config)
    config.unlink()
    assert resume(run) == run
    assert load_manifest(run)["workflow"] == "beta1"

    wrong = _config(tmp_path / "wrong.json", "beta2", tmp_path / "wrong-run")
    from thg_protocol.workflow.cli import main

    assert main(["beta1", str(wrong)]) == 2


def test_start_resumes_matching_run_and_allows_worker_count_change(tmp_path):
    config = _config(
        tmp_path / "config.json",
        "beta1",
        tmp_path / "run",
        {"n_jobs": 1},
    )
    run = start(config)
    before = get_status(run)
    config.write_text(
        json.dumps(
            {
                "workflow": "beta1",
                "run": {"name": "beta1", "output_dir": str(run)},
                "beta1": {"n_jobs": 2, "input_model": str(DEFAULT_MODEL)},
            }
        ),
        encoding="utf-8",
    )

    assert start(config) == run
    after = get_status(run)
    assert after["config_sha256"] != before["config_sha256"]
    assert all(
        after["steps"][stage]["attempt"] == before["steps"][stage]["attempt"]
        for stage in before["steps"]
    )
    assert (
        json.loads((run / "config.snapshot.json").read_text())["beta1"]["n_jobs"]
        == 2
    )


def test_registered_resume_rejects_snapshot_for_a_different_run_directory(tmp_path):
    run = start(_config(tmp_path / "config.json", "beta1", tmp_path / "run"))
    snapshot = run / "config.snapshot.json"
    payload = json.loads(snapshot.read_text(encoding="utf-8"))
    payload["run"]["output_dir"] = str(tmp_path / "other-run")
    snapshot.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ConfigError, match="output_dir does not match"):
        resume(run)


def test_registered_resume_invalidates_changed_upstream_artifact(tmp_path):
    beta1 = start(_config(tmp_path / "beta1.json", "beta1", tmp_path / "beta1-run"))
    beta1_export = get_status(beta1)["steps"]["export-beta1"]["outputs"][0]
    beta2 = start(
        _config(
            tmp_path / "beta2.json",
            "beta2",
            tmp_path / "beta2-run",
            {
                "upstream": {
                    "run_dir": str(beta1),
                    "stage_id": "export-beta1",
                    "role": "model",
                }
            },
        )
    )
    before = get_status(beta2)
    (beta1 / beta1_export["path"]).write_text("changed\n", encoding="utf-8")

    with pytest.raises(WorkflowError, match="stage 'load-beta1' failed"):
        resume(beta2)

    after = get_status(beta2)
    assert after["steps"]["load-beta1"]["attempt"] == 2
    assert after["steps"]["load-beta1"]["status"] == "failed"
    assert before["steps"]["load-beta1"]["attempt"] == 1


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
    decisions.write_text("", encoding="utf-8")
    resume(run)
    after = get_status(run)
    assert (
        after["steps"]["collect-metabolite-evidence"]["attempt"]
        == attempts["collect-metabolite-evidence"]
    )
    assert (
        after["steps"]["generate-curation-proposals"]["attempt"]
        == attempts["generate-curation-proposals"]
    )
    assert (
        after["steps"]["apply-curation"]["attempt"]
        == attempts["apply-curation"] + 1
    )
    assert after["steps"]["export-beta1"]["attempt"] == attempts["export-beta1"] + 1
