from __future__ import annotations

import json
from pathlib import Path

import pytest

from thg_protocol.workflow.cli import build_parser, main

MODEL = (
    Path(__file__).resolve().parents[1]
    / "fixtures/beta1/sanctioned_human_reference.json"
)


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
    assert parser.parse_args(["beta1", "config.json", "-q"]).quiet
    direct = parser.parse_args(
        ["validate", "model.json", "--profile", "final-standard", "--no-run-solver"]
    )
    assert direct.config_or_model == Path("model.json")
    assert direct.profile == "final-standard"
    assert direct.run_solver is False

    with pytest.raises(SystemExit) as error:
        main(["--help"])
    assert error.value.code == 0
    assert "resumable workflow" in capsys.readouterr().out


def test_verbose_cli_reports_registered_stage_progress(tmp_path, capsys):
    config = tmp_path / "config.json"
    config.write_text(
        json.dumps(
            {
                "workflow": "beta1",
                "run": {"name": "verbose", "output_dir": str(tmp_path / "run")},
                "beta1": {"input_model": str(MODEL)},
            }
        ),
        encoding="utf-8",
    )

    assert main(["beta1", str(config), "--verbose"]) == 0
    captured = capsys.readouterr()
    assert "beta1 workflow" in captured.err
    assert "starting attempt 1" in captured.err
    assert "workflow completed" in captured.err
    log = (tmp_path / "run" / "logs" / "run.log").read_text(encoding="utf-8")
    assert "beta1 workflow" in log
    assert "starting attempt 1" in log
    assert "workflow completed" in log


def test_default_cli_reports_compact_progress_and_keeps_stage_details_in_log(
    tmp_path, capsys
):
    config = tmp_path / "config.json"
    config.write_text(
        json.dumps(
            {
                "workflow": "beta1",
                "run": {"name": "compact", "output_dir": str(tmp_path / "run")},
                "beta1": {"input_model": str(MODEL)},
            }
        ),
        encoding="utf-8",
    )

    assert main(["beta1", str(config)]) == 0
    captured = capsys.readouterr()
    assert "completed in" in captured.err
    assert "starting attempt" not in captured.err
    assert "fingerprint" not in captured.err
    log = (tmp_path / "run" / "logs" / "run.log").read_text(encoding="utf-8")
    assert "starting attempt" in log


def test_quiet_cli_suppresses_progress(tmp_path, capsys):
    config = tmp_path / "config.json"
    config.write_text(
        json.dumps(
            {
                "workflow": "beta1",
                "run": {"name": "quiet", "output_dir": str(tmp_path / "run")},
                "beta1": {"input_model": str(MODEL)},
            }
        ),
        encoding="utf-8",
    )

    assert main(["beta1", str(config), "--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    assert "run started/resumed:" in captured.out


def test_status_json_is_read_only_and_parseable(tmp_path, capsys):
    from thg_protocol.runtime.manifest import new_manifest, write_manifest_atomic
    from thg_protocol.workflow.config import RunSettings, WorkflowConfig
    from thg_protocol.workflow.registry import get_workflow

    config = WorkflowConfig("beta1", RunSettings("status-run", tmp_path), {})
    write_manifest_atomic(
        tmp_path,
        new_manifest(
            workflow_id=config.workflow,
            run_id=config.run.name,
            config_sha256="test",
            stages=get_workflow("beta1").stages,
        ),
    )
    before = (tmp_path / "manifest.json").read_text(encoding="utf-8")
    assert main(["status", str(tmp_path), "--json"]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["overall_status"] == "pending"
    assert (tmp_path / "manifest.json").read_text(encoding="utf-8") == before


def test_direct_validation_accepts_model_path_and_cli_defaults(tmp_path, capsys):
    import cobra
    from cobra.io import save_json_model

    source = cobra.Metabolite("source_c", formula="H2O", charge=0, compartment="c")
    product = cobra.Metabolite("product_c", formula="H2O", charge=0, compartment="c")
    reaction = cobra.Reaction("convert")
    reaction.add_metabolites({source: -1, product: 1})
    model = cobra.Model("direct-validation")
    model.add_reactions([reaction])
    path = tmp_path / "model.json"
    save_json_model(model, str(path))

    assert main(["validate", str(path), "--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["profile"] == "structural-fast"
    assert report["passed"] is True


def test_configured_validation_uses_config_path(tmp_path, monkeypatch, capsys):
    config = tmp_path / "validation.json"
    config.write_text(
        json.dumps(
            {
                "workflow": "validate",
                "run": {"name": "validation", "output_dir": str(tmp_path / "run")},
                "validation": {"input_model": str(MODEL)},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("thg_protocol.workflow.cli.start", lambda path: path)

    assert main(["validate", str(config)]) == 0
    assert str(config) in capsys.readouterr().out
