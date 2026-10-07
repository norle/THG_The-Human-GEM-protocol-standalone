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
    annotation_conflict,
    formula_disagreement,
    fractional_coefficients,
    minimal_inconsistent_sets,
    stoichiometric_consistency,
    unusual_protons,
    validate_model,
)
from thg_protocol.workflow.runner import start


def model():
    result = cobra.Model("validation")
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


@pytest.mark.memote
def test_stoichiometric_consistency_uses_memote():
    pytest.importorskip("memote")
    result = stoichiometric_consistency(model())
    assert result["passed"] is True
    assert result["unconserved"] == []


def test_stoichiometric_consistency_without_memote_is_not_evaluated(monkeypatch):
    monkeypatch.setitem(__import__("sys").modules, "memote.support.consistency", None)
    check = next(
        item
        for item in validate_model(model())["checks"]
        if item["id"] == "stoichiometric-consistency"
    )
    assert check["status"] == "not-evaluated"
    assert check["passed"] is None


def test_topology_checks_report_failures_when_findings_exist():
    report = validate_model(model(), "structural-fast")
    checks = {item["id"]: item for item in report["checks"]}
    assert checks["dead-end-topology"]["details"]["metabolites"]
    assert checks["dead-end-topology"]["passed"] is False


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


@pytest.mark.memote
def test_stoichiometric_inconsistency_is_a_nonblocking_warning(monkeypatch):
    pytest.importorskip("memote")
    source = model()
    inconsistent = cobra.Reaction("inconsistent")
    inconsistent.add_metabolites(
        {source.metabolites.source_c: -1, source.metabolites.product_c: 2}
    )
    source.add_reactions([inconsistent])
    result = stoichiometric_consistency(source)
    assert result["passed"] is False
    assert {item["id"] for item in result["unconserved"]} == {"source_c", "product_c"}
    # Isolate the conservation warning from the separate chemical-balance gate.
    for check in ("_mass_balance", "_charge_balance"):
        monkeypatch.setattr(
            f"thg_protocol.validation.{check}", lambda m, pseudo: {"passed": True}
        )
    report = validate_model(source, "release-full", run_solver=False)
    check = next(c for c in report["checks"] if c["id"] == "stoichiometric-consistency")
    assert check["status"] == "failed"
    assert check["release_blocking"] is False
    # Without solver checks only the LP runs; MEMOTE's MILP names nothing.
    assert check["details"]["unconserved"] is None
    assert report["passed"] is True


def test_tasks_copy_model_and_classify_solver_status(tmp_path):
    source = model()
    before = [tuple(reaction.bounds) for reaction in source.reactions]
    report = run_task(source, MetabolicTask("core-convert", bounds={"convert": (0, 0)}))
    assert report["status"] == "passed"
    assert report["solver_status"] == "optimal"
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
    assert run_task(model(), loaded.tasks[0])["status"] == "passed"


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


def chemistry_model():
    result = cobra.Model("chemistry")
    a_c = cobra.Metabolite("a_c", formula="C2H4O2", charge=0, compartment="c")
    a_m = cobra.Metabolite("a_m", formula="C2H4O3", charge=-1, compartment="m")
    b_c = cobra.Metabolite("MAM1c", formula="CHO2", charge=0, compartment="c")
    b_m = cobra.Metabolite("MAM1m", formula="CH1O2", charge=0, compartment="m")
    o2 = cobra.Metabolite("o2_c", formula="O2", charge=0, compartment="c")
    fitted = cobra.Reaction("FIT")
    fitted.add_metabolites({a_c: -1, o2: -1.2, b_c: 1.5})
    transport = cobra.Reaction("T")
    transport.add_metabolites({a_c: -1, a_m: 1})
    pool = cobra.Reaction("POOL", subsystem="Pool reactions")
    pool.add_metabolites({b_c: -0.5, b_m: 1})
    exchange = cobra.Reaction("EX_o2")
    exchange.add_metabolites({o2: -1})
    result.add_reactions([fitted, transport, pool, exchange])
    return result


def test_fractional_coefficients_flag_fitted_reactions_but_not_pseudo_reactions():
    result = fractional_coefficients(chemistry_model())
    assert result["passed"] is False
    assert result["reactions"]["FIT"]["coefficients"] == {"MAM1c": 1.5, "o2_c": -1.2}
    assert "POOL" not in result["reactions"]
    assert fractional_coefficients(model())["passed"] is True


def test_formula_disagreement_across_compartments_and_against_reference():
    checked = chemistry_model()
    result = formula_disagreement(checked)
    assert result["across_compartments"]["a"]["differs"] == ["formula", "charge"]
    # CHO2 and CH1O2 are the same element counts.
    assert "MAM1" not in result["across_compartments"]
    assert result["against_reference"] == {}

    reference = chemistry_model()
    reference.metabolites.MAM1c.formula = "C2HO2"
    result = formula_disagreement(checked, reference_model=reference)
    assert result["against_reference"]["MAM1c"]["reference"]["formula"] == "C2HO2"
    assert result["reference"] == "chemistry"
    assert result["passed"] is False


def naming_model(name="2-naphthol"):
    """Human-GEM-like pair: MAM00668 is 2-naphthol, MAM01784 is EPA."""
    result = cobra.Model("naming")
    naphthol = cobra.Metabolite(
        "MAM00668c", name=name, formula="C10H8O", compartment="c"
    )
    naphthol.annotation["kegg.compound"] = "C11713"
    epa = cobra.Metabolite(
        "MAM01784c",
        name="(5Z,8Z,11Z,14Z,17Z)-icosapentaenoic acid",
        formula="C20H29O2",
        compartment="c",
    )
    epa.annotation["kegg.compound"] = "C06428"
    epa_m = epa.copy()
    epa_m.id, epa_m.compartment = "MAM01784m", "m"
    result.add_metabolites([naphthol, epa, epa_m])
    return result


def test_annotation_conflict_finds_shared_names_and_renames_to_other_compounds():
    reference = naming_model()
    assert annotation_conflict(reference)["passed"] is True  # compartments only
    renamed = naming_model(name="(5Z,8Z,11Z,14Z,17Z)-Icosapentaenoic acid")
    result = annotation_conflict(renamed, reference_model=reference)
    group = result["within_model"]["(5z,8z,11z,14z,17z)-icosapentaenoic acid"]
    assert group["conflicts"] == ["formula", "kegg.compound"]
    assert set(group["metabolites"]) == {"MAM00668c", "MAM01784c", "MAM01784m"}
    entry = result["renamed_from_reference"]["MAM00668c"]
    assert entry["reference_name"] == "2-naphthol"
    assert set(entry["name_belongs_to"]) == {"MAM01784c", "MAM01784m"}
    # A plain spelling change is not reported.
    respelled = naming_model(name="2-Naphthol")
    assert annotation_conflict(respelled, reference_model=reference)["passed"]


def test_unusual_protons_reports_new_proton_heavy_reactions_only():
    def model(protons):
        result = cobra.Model("protons")
        acyl = cobra.Metabolite("acyl_c", formula="C41H60N7O17P3S", compartment="c")
        acid = cobra.Metabolite("acid_c", formula="C10H8O", compartment="c")
        proton = cobra.Metabolite("h_c", formula="H", charge=1, compartment="c")
        reaction = cobra.Reaction("R08179_c")
        reaction.add_metabolites({acyl: -1, acid: 2, proton: protons})
        result.add_reactions([reaction])
        return result

    flagged = unusual_protons(model(14))
    assert flagged["reactions"]["R08179_c"]["protons"] == {"h_c": 14.0}
    assert unusual_protons(model(1))["passed"] is True
    assert unusual_protons(model(14), reference_model=model(14))["passed"] is True
    assert unusual_protons(model(14), reference_model=model(1))["passed"] is False


def test_new_chemistry_checks_are_diagnostic_in_every_profile():
    for profile in ("structural-fast", "release-full"):
        checks = {
            item["id"]: item
            for item in validate_model(chemistry_model(), profile, run_solver=False)[
                "checks"
            ]
        }
        for check_id in ("fractional-coefficients", "formula-disagreement"):
            assert checks[check_id]["status"] == "failed"
        for check_id in (
            "fractional-coefficients",
            "formula-disagreement",
            "annotation-conflict",
            "unusual-protons",
        ):
            assert checks[check_id]["release_blocking"] is False


def test_registered_validation_workflow_compares_with_reference_model(tmp_path):
    from cobra.io import save_json_model

    source, reference = tmp_path / "model.json", tmp_path / "reference.json"
    save_json_model(chemistry_model(), str(source))
    changed = chemistry_model()
    changed.metabolites.o2_c.formula = "O3"
    save_json_model(changed, str(reference))
    config = tmp_path / "config.json"
    config.write_text(
        json.dumps(
            {
                "workflow": "validate",
                "run": {"name": "reference", "output_dir": str(tmp_path / "run")},
                "validation": {
                    "input_model": str(source),
                    "reference_model": str(reference),
                    "profile": "structural-fast",
                },
            }
        ),
        encoding="utf-8",
    )
    run = start(config)
    validation = json.loads(
        next(
            (run / "artifacts" / "validate-checks").rglob("validation.json")
        ).read_text()
    )
    check = next(
        item for item in validation["checks"] if item["id"] == "formula-disagreement"
    )
    assert set(check["details"]["against_reference"]) == {"o2_c"}


def test_validation_fingerprint_tracks_reference_model_contents(tmp_path):
    from types import SimpleNamespace

    from thg_protocol.workflow.validation import ValidationScientificStage

    reference = tmp_path / "reference.json"
    reference.write_text("{}", encoding="utf-8")
    context = SimpleNamespace(
        config=SimpleNamespace(
            sections={"validation": {"reference_model": str(reference)}}
        )
    )
    stage = ValidationScientificStage("validate-checks", ("validate-input",))
    before = stage.fingerprint_data(context)
    reference.write_text('{"id": "edited"}', encoding="utf-8")
    assert stage.fingerprint_data(context) != before


def test_registered_validation_workflow_writes_check_and_memote_artifacts(tmp_path):
    from cobra.io import save_json_model

    source = tmp_path / "model.json"
    save_json_model(model(), str(source))
    config = tmp_path / "config.json"
    config.write_text(
        json.dumps(
            {
                "workflow": "validate",
                "run": {"name": "validation", "output_dir": str(tmp_path / "run")},
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


def test_model_metrics_reuse_the_validation_fva_and_report_failures(monkeypatch):
    from thg_protocol.analysis import consistency
    from thg_protocol.workflow._scientific import _model_metrics

    calls = []

    def blocked(model):
        calls.append(model.id)
        return ["R1"]

    monkeypatch.setattr(consistency, "blocked_reactions", blocked)
    metrics = _model_metrics(model(), profile="cell-specific-standard")
    assert metrics["blocked_reactions"] == ["R1"]
    assert len(calls) == 1

    def broken(model):
        raise RuntimeError("solver down")

    monkeypatch.setattr(consistency, "blocked_reactions", broken)
    metrics = _model_metrics(model(), profile="structural-fast")
    assert metrics["blocked_reactions"] is None
    assert metrics["blocked_reactions_error"] == "RuntimeError: solver down"
