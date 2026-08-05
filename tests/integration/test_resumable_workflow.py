from __future__ import annotations

import json
from pathlib import Path

import pytest

from thg_protocol.workflow.config import ConfigError
from thg_protocol.workflow.manifest import load_manifest, write_manifest_atomic
from thg_protocol.workflow.runner import resume, start

ROOT = Path(__file__).parents[2]


def _configuration(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "format_version": 1,
                "run": {"name": "offline-run", "output_dir": str(tmp_path / "run")},
                "reference": {
                    "mode": "prebuilt",
                    "input_model": str(ROOT / "docs/examples/quickstart_model.json"),
                },
                "database": {"records": str(ROOT / "docs/examples/records.json")},
                "validation": {"run_memote": False},
            }
        ),
        encoding="utf-8",
    )
    return config_path


def test_offline_run_resumes_by_checksums_and_marks_crashed_stage_interrupted(tmp_path):
    run_dir = start(_configuration(tmp_path))
    first = load_manifest(run_dir)
    assert first["overall_status"] == "completed"
    assert all(
        first["steps"][stage]["status"] in {"completed", "skipped"}
        for stage in first["steps"]
    )
    attempts = {stage: first["steps"][stage]["attempt"] for stage in first["steps"]}

    resume(run_dir)
    second = load_manifest(run_dir)
    assert {
        stage: second["steps"][stage]["attempt"] for stage in second["steps"]
    } == attempts

    consistency = run_dir / second["steps"]["validation"]["outputs"][1]["path"]
    consistency.unlink()
    resume(run_dir)
    third = load_manifest(run_dir)
    assert third["steps"]["validation"]["attempt"] == attempts["validation"] + 1
    assert third["steps"]["merge"]["attempt"] == attempts["merge"]

    crashed = dict(third)
    crashed["steps"] = {stage: dict(entry) for stage, entry in third["steps"].items()}
    crashed["steps"]["merge"] = dict(crashed["steps"]["merge"])
    crashed["steps"]["merge"]["status"] = "running"
    write_manifest_atomic(run_dir, crashed)
    resume(run_dir)
    final = load_manifest(run_dir)
    assert final["steps"]["merge"]["attempt"] == attempts["merge"] + 1
    assert (
        final["steps"]["validation"]["attempt"]
        == third["steps"]["validation"]["attempt"] + 1
    )


def test_start_refuses_an_unrelated_nonempty_output_directory(tmp_path):
    config_path = _configuration(tmp_path)
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "unrelated.txt").write_text("keep me", encoding="utf-8")

    with pytest.raises(ConfigError, match="nonempty without a manifest"):
        start(config_path)
