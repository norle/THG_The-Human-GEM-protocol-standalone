from __future__ import annotations

import json

import pytest

from thg_protocol.workflow.cli import build_parser, main


def test_cli_parser_exposes_all_commands_and_help(capsys):
    parser = build_parser()
    assert parser.parse_args(["start", "config.json"]).command == "start"
    assert (
        parser.parse_args(["resume", "run", "--force-step", "validation"]).force_step
        == "validation"
    )
    assert parser.parse_args(["status", "run", "--json"]).as_json
    assert parser.parse_args(["unlock", "run", "--force"]).force
    assert parser.parse_args(["beta1", "config.json", "-v"]).verbose == 1
    assert parser.parse_args(["-v", "beta1", "config.json"]).verbose == 1
    assert parser.parse_args(["resume", "run", "-vv"]).verbose == 2

    with pytest.raises(SystemExit) as error:
        main(["--help"])
    assert error.value.code == 0
    assert "resumable workflow" in capsys.readouterr().out


def test_verbose_cli_reports_registered_stage_progress(tmp_path, capsys):
    config = tmp_path / "config.json"
    config.write_text(
        json.dumps(
            {
                "format_version": 2,
                "workflow": "beta1",
                "run": {"name": "verbose", "output_dir": str(tmp_path / "run")},
            }
        ),
        encoding="utf-8",
    )

    assert main(["beta1", str(config), "--verbose"]) == 0
    captured = capsys.readouterr()
    assert "beta1 workflow" in captured.err
    assert "starting attempt 1" in captured.err
    assert "workflow completed" in captured.err


def test_status_json_is_read_only_and_parseable(tmp_path, capsys):
    from thg_protocol.workflow.config import RunSettings, WorkflowConfig
    from thg_protocol.workflow.manifest import (
        new_workflow_manifest,
        write_manifest_atomic,
    )
    from thg_protocol.workflow.registry import get_workflow

    config = WorkflowConfig(2, "beta1", RunSettings("status-run", tmp_path), {})
    write_manifest_atomic(
        tmp_path, new_workflow_manifest(config, get_workflow("beta1").stages)
    )
    before = (tmp_path / "manifest.json").read_text(encoding="utf-8")
    assert main(["status", str(tmp_path), "--json"]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["overall_status"] == "pending"
    assert (tmp_path / "manifest.json").read_text(encoding="utf-8") == before
