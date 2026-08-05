from __future__ import annotations

import json

import pytest

from thg_protocol.workflow.config import ConfigError
from thg_protocol.workflow.runner import start


def _config(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "format_version": 1,
                "run": {"name": "runner-test", "output_dir": str(tmp_path / "run")},
                "reference": {
                    "mode": "prebuilt",
                    "input_model": str(tmp_path / "model.json"),
                },
                "database": {"records": str(tmp_path / "records.json")},
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "model.json").write_text("{}", encoding="utf-8")
    (tmp_path / "records.json").write_text("[]", encoding="utf-8")
    return config_path


def test_start_rejects_a_file_as_run_output_path(tmp_path):
    config_path = _config(tmp_path)
    run_path = tmp_path / "run"
    run_path.write_text("keep me", encoding="utf-8")

    with pytest.raises(ConfigError, match="not a directory"):
        start(config_path)


def test_start_requires_resume_for_a_manifest_directory(tmp_path):
    config_path = _config(tmp_path)
    run_path = tmp_path / "run"
    run_path.mkdir()
    (run_path / "manifest.json").write_text("{}", encoding="utf-8")

    with pytest.raises(ConfigError, match="use resume"):
        start(config_path)
