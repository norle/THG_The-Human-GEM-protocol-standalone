from __future__ import annotations

import json

import cobra
import pytest

from thg_protocol.memote import run_memote
from thg_protocol.tasks import (
    MetabolicTask,
    TaskSuite,
    load_task_suite,
    run_task,
    run_task_suite,
)
from thg_protocol.validation import (
    minimal_inconsistent_sets,
    stoichiometric_consistency,
    validate_model,
)
from thg_protocol.workflow.runner import start


def model():
    result = cobra.Model("phase3")
    source = cobra.Metabolite("source_c", formula="H2O", charge=0, compartment="c")
    product = cobra.Metabolite("product_c", formula="H2O", charge=0, compartment="c")
    reaction = cobra.Reaction("convert")
    reaction.add_metabolites({source: -1, product: 1})
    result.add_reactions([reaction])
    return result


def test_validation_profiles_return_separate_structural_and_solver_checks():
    report = validate_model(model(), "structural-fast")
    assert report["profile"] == "structural-fast"
    assert {item["family"] for item in report["checks"]} >= {"structural", "chemical"}
    assert not any(item["family"] == "solver" for item in report["checks"])
    assert stoichiometric_consistency(model())["passed"] is True


def test_topology_checks_report_failures_when_findings_exist():
    report = validate_model(model(), "structural-fast")
    checks = {item["id"]: item for item in report["checks"]}
    assert checks["dead-end-topology"]["details"]["metabolites"]
    assert checks["dead-end-topology"]["passed"] is False
    assert checks["unconserved-metabolites"]["passed"] is False


def test_solver_profile_reports_singleton_inconsistent_sets():
    report = minimal_inconsistent_sets(model())
    assert report["method"] == "blocked-reaction-singletons"
    assert report["complete"] is True


def test_validation_preserves_infrastructure_error(monkeypatch):
    monkeypatch.setattr(
        "thg_protocol.validation.stoichiometric_consistency",
        lambda model: {"status": "infrastructure-error", "passed": None},
    )
    check = next(
        item
        for item in validate_model(model())["checks"]
        if item["id"] == "stoichiometric-consistency"
    )
    assert check["status"] == "infrastructure-error"
    assert check["passed"] is None


def test_release_full_applies_stricter_profile_policy():
    checks = {
        item["id"]: item for item in validate_model(model(), "release-full")["checks"]
    }
    assert checks["mass-balance"]["release_blocking"] is True
    assert checks["stoichiometric-consistency"]["release_blocking"] is False


def test_stoichiometric_consistency_excludes_boundary_reactions():
    source = model()
    uptake = cobra.Reaction("uptake")
    uptake.add_metabolites({source.metabolites.source_c: 1})
    sink = cobra.Reaction("sink")
    sink.add_metabolites({source.metabolites.product_c: -1})
    source.add_reactions([uptake, sink])
    source.objective = "sink"
    assert validate_model(source, "release-full")["passed"] is True


def test_stoichiometric_inconsistency_is_a_nonblocking_warning(monkeypatch):
    source = model()
    inconsistent = cobra.Reaction("inconsistent")
    inconsistent.add_metabolites(
        {source.metabolites.source_c: -1, source.metabolites.product_c: 2}
    )
    source.add_reactions([inconsistent])
    assert stoichiometric_consistency(source)["passed"] is False
    # Isolate the conservation warning from the separate chemical-balance gate.
    for check in ("_mass_balance", "_charge_balance"):
        monkeypatch.setattr(
            f"thg_protocol.validation.{check}", lambda m: {"passed": True}
        )
    report = validate_model(source, "release-full", run_solver=False)
    check = next(c for c in report["checks"] if c["id"] == "stoichiometric-consistency")
    assert check["status"] == "failed"
    assert check["release_blocking"] is False
    assert report["passed"] is True


def test_tasks_copy_model_and_classify_solver_status(tmp_path):
    source = model()
    before = [tuple(reaction.bounds) for reaction in source.reactions]
    report = run_task(source, MetabolicTask("core-convert", bounds={"convert": (0, 0)}))
    assert report["status"] == "optimal"
    assert [tuple(reaction.bounds) for reaction in source.reactions] == before
    suite = TaskSuite("core", "1", (MetabolicTask("task", expected=False),))
    assert run_task_suite(source, suite)["suite_version"] == "1"
    suite_path = tmp_path / "suite.json"
    suite_path.write_text(json.dumps(suite.to_dict()), encoding="utf-8")
    assert load_task_suite(suite_path).id == "core"


def test_task_temporary_reactions_round_trip_and_execute(tmp_path):
    temporary = cobra.Reaction("temporary")
    temporary.add_metabolites(
        {
            cobra.Metabolite("source_c", compartment="c"): -1,
            cobra.Metabolite("product_c", compartment="c"): 1,
        }
    )
    task = MetabolicTask("temporary", temporary_reactions=(temporary,))
    suite_path = tmp_path / "temporary-suite.json"
    suite_path.write_text(
        json.dumps(TaskSuite("temporary", "1", (task,)).to_dict()),
        encoding="utf-8",
    )
    loaded = load_task_suite(suite_path)
    assert len(loaded.tasks[0].temporary_reactions) == 1
    assert run_task(model(), loaded.tasks[0])["status"] == "optimal"


def test_memote_adapter_records_command_failure_and_artifact_manifest(
    tmp_path, monkeypatch
):
    class Completed:
        returncode = 127
        stdout = ""
        stderr = "memote unavailable"

    monkeypatch.setattr(
        "thg_protocol.memote.subprocess.run", lambda *args, **kwargs: Completed()
    )
    report = run_memote("model.xml", tmp_path)
    assert report["status"] == "command-failed"
    assert json.loads((tmp_path / "memote-run.json").read_text())["returncode"] == 127


def test_registered_validation_workflow_writes_check_and_memote_artifacts(tmp_path):
    from cobra.io import save_json_model

    source = tmp_path / "model.json"
    save_json_model(model(), str(source))
    config = tmp_path / "config.json"
    config.write_text(
        json.dumps(
            {
                "workflow": "validate",
                "run": {"name": "phase3", "output_dir": str(tmp_path / "run")},
                "validation": {
                    "input_model": str(source),
                    "profile": "structural-fast",
                },
            }
        ),
        encoding="utf-8",
    )
    run = start(config)
    manifest = json.loads((run / "manifest.json").read_text())
    assert set(manifest["steps"]) == {
        "validate-input",
        "validate-checks",
        "validate-memote",
        "assemble-validation-report",
    }
    assert manifest["overall_status"] == "completed"
    outputs = manifest["steps"]["assemble-validation-report"]["outputs"]
    assert {item["role"] for item in outputs} == {
        "validation",
        "validation-html",
        "validation-summary",
    }


@pytest.mark.memote
def test_real_memote_smoke_when_optional_dependency_is_installed(tmp_path):
    if not __import__("shutil").which("memote"):
        pytest.skip("optional memote executable is not installed")
    from cobra.io import write_sbml_model

    source = tmp_path / "model.xml"
    write_sbml_model(model(), str(source))
    report = run_memote(source, tmp_path / "memote")
    assert report["status"] == "completed"
    assert {"memote-result.json", "memote-report.html"} <= set(report["artifacts"])
    assert report["report_returncode"] == 0
