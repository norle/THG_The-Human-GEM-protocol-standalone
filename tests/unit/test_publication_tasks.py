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
