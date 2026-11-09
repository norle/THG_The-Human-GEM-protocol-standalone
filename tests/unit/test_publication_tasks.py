"""Publication task exports preserve diagnostics and enforce VerifyModel first."""

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import cobra
import pytest


@pytest.mark.parametrize("gate_passed", [True, False])
def test_publication_task_export(tmp_path, monkeypatch, gate_passed):
    script = Path(__file__).resolve().parents[2] / "publication/scripts/run_tasks.py"
    spec = importlib.util.spec_from_file_location("publication_tasks", script)
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    model_path = tmp_path / "model.json"
    model_path.write_text("{}")
    model = cobra.Model("publication-test")
    model.solver = "glpk"
    monkeypatch.setattr(cobra.io, "load_json_model", lambda _: model)
    monkeypatch.setenv("THG_SOLVER", "glpk")
    monkeypatch.delenv("THG_BLOCK", raising=False)
    monkeypatch.setattr(
        "sys.argv", [str(script), str(model_path), "test", str(tmp_path)]
    )
    calls = []

    def imported(path, *_args, **_kwargs):
        calls.append(path.name)
        return SimpleNamespace(suite=SimpleNamespace(tasks=[]))

    monkeypatch.setattr(runner, "import_raven_tasks", imported)
    diagnostics = {
        "max_bound_violation": 3e-7,
        "max_constraint_violation": 0,
        "numerical_reliability": "unreliable",
    }
    monkeypatch.setattr(
        runner,
        "run_task_suite",
        lambda *_: {
            "passed": gate_passed,
            "counts": {},
            "tasks": [
                {
                    "id": "21",
                    "expected_outcome": "failure",
                    "actual_outcome": None,
                    "solver_status": "optimal",
                    "status": "error",
                    "diagnostics": diagnostics,
                }
            ],
        },
    )
    runner.main()
    assert len(calls) == (3 if gate_passed else 1)
    exported = json.loads((tmp_path / "task_results_test.json").read_text())
    assert exported["reports"]["VerifyModel"]["tasks"][0]["diagnostics"] == diagnostics
    assert exported["solver"] == "glpk"
    assert "unreliable" in (tmp_path / "task_results_test.csv").read_text()


def test_pin_models_hashes_and_missing_files(tmp_path, monkeypatch):
    import hashlib

    script = Path(__file__).resolve().parents[2] / "publication/scripts/pin_models.py"
    spec = importlib.util.spec_from_file_location("publication_models", script)
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    (tmp_path / "model.xml").write_bytes(b"model bytes")
    row = runner.pin("baseline", "model.xml", "test")
    assert row["sha256"] == hashlib.sha256(b"model bytes").hexdigest()
    assert row["status"] == "present"
    row = runner.pin("pending", "missing.xml", "test")
    assert row["sha256"] is None
    assert row["status"] == "missing"


def test_publication_task_mapping_checksum_is_enforced(tmp_path, monkeypatch):
    script = Path(__file__).resolve().parents[2] / "publication/scripts/run_tasks.py"
    spec = importlib.util.spec_from_file_location("publication_tasks", script)
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    changed_mapping = tmp_path / "mapping.json"
    changed_mapping.write_text("{}")
    monkeypatch.setattr(runner, "MAPPING", changed_mapping)
    monkeypatch.setattr("sys.argv", [str(script), "unused.xml", "test", str(tmp_path)])
    with pytest.raises(ValueError, match="mapping checksum differs"):
        runner.main()


def test_correctness_measurement_distinguishes_inherited_chemistry_and_identity():
    script = (
        Path(__file__).resolve().parents[2]
        / "publication/scripts/measure_correctness.py"
    )
    spec = importlib.util.spec_from_file_location("publication_correctness", script)
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    model = {
        "metabolites": [
            {
                "id": "a",
                "formula": "CH2",
                "charge": 0,
                "annotation": {"inchikey": "shared", "bigg.metabolite": "a"},
            },
            {
                "id": "b",
                "formula": "CH2",
                "charge": 1,
                "annotation": {"inchikey": "shared", "bigg.metabolite": "b"},
            },
        ],
        "reactions": [{"id": "r", "metabolites": {"a": -1, "b": 1}}],
    }
    plan = [
        {"action": "create", "reaction_id": "r", "location": "x"},
        {"action": "retain", "reaction_id": "r", "location": "c"},
    ]
    corrected = [
        {
            "action": "retain",
            "reaction_id": "r",
            "location": "x",
            "reason": "unbalanced-parent",
        }
    ]
    result = runner.measure(
        model, {"retained_metabolites": {"a": "b"}}, plan, model, corrected
    )
    assert result["pairs_vetoed_by_identifier_rule"] == 1
    assert result["unbalanced_copy_count"] == result["unbalanced_parent_count"] == 1
    assert result["old_unbalanced_copies"][0]["imbalance"] == {"charge": 1}
    assert result["archived_corrected_exclusions_matching_old_copies"] == 1


def test_stage_table_excludes_stale_downstream_artifacts(tmp_path, monkeypatch):
    import hashlib

    script = Path(__file__).resolve().parents[2] / "publication/scripts/stage_table.py"
    spec = importlib.util.spec_from_file_location("publication_stages", script)
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    monkeypatch.setattr(
        runner,
        "REFERENCE_STAGES",
        (
            SimpleNamespace(id="input", dependencies=()),
            SimpleNamespace(id="clean", dependencies=("input",)),
            SimpleNamespace(id="export", dependencies=("clean",)),
        ),
    )
    model = tmp_path / "model.json"
    model.write_text('{"reactions": [1, 2], "metabolites": [1], "genes": []}')
    artifact = {
        "role": "model",
        "path": model.name,
        "sha256": hashlib.sha256(model.read_bytes()).hexdigest(),
    }
    completed = {
        "status": "completed",
        "attempt": 1,
        "outputs": [artifact],
        "started_at": "2026-11-09T00:00:00Z",
        "finished_at": "2026-11-09T00:00:02Z",
    }
    manifest = {
        "overall_status": "running",
        "steps": {
            "input": completed,
            "clean": {"status": "running", "attempt": 2},
            "export": completed,
        },
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    rows = runner.export(tmp_path, tmp_path / "out")
    assert rows[0]["runtime_seconds"] == 2
    assert json.loads(rows[0]["output_models"])[0]["reactions"] == 2
    assert rows[1]["output_models"] == rows[2]["output_models"] == "[]"
    assert rows[2]["status"] == "stale"
    model.write_text("changed")
    with pytest.raises(ValueError, match="differs from ledger"):
        runner.export(tmp_path, tmp_path / "out")


def test_stage_table_counts_sbml_without_solver(tmp_path):
    script = Path(__file__).resolve().parents[2] / "publication/scripts/stage_table.py"
    spec = importlib.util.spec_from_file_location("publication_stages", script)
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    model = tmp_path / "model.xml"
    model.write_text(
        '<sbml xmlns="sbml" xmlns:fbc="fbc"><model>'
        "<species/><reaction><speciesReference/></reaction>"
        "<fbc:geneProduct/></model></sbml>"
    )
    assert runner.model_size(model) == {"reactions": 1, "metabolites": 1, "genes": 1}
