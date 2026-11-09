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
    monkeypatch.setattr(runner, "load_snapshot", lambda _: SimpleNamespace())
    for stage in runner.REFERENCE_STAGES:
        stage.fingerprint_data = lambda _: {"revision": 1}
        stage.enabled = lambda _: True
    model = tmp_path / "model.json"
    model.write_text('{"reactions": [1, 2], "metabolites": [1], "genes": []}')
    artifact = {
        "role": "model",
        "path": model.name,
        "sha256": hashlib.sha256(model.read_bytes()).hexdigest(),
    }
    completed = {
        "fingerprint": runner.sha256_json({"revision": 1}),
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
    runner.REFERENCE_STAGES[0].fingerprint_data = lambda _: {"revision": 2}
    stale = runner.export(tmp_path, tmp_path / "out")
    assert stale[0]["status"] == "stale"
    assert stale[0]["output_models"] == "[]"
    runner.REFERENCE_STAGES[0].fingerprint_data = lambda _: {"revision": 1}
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


@pytest.mark.parametrize("terminal_status", ["completed", "failed", "interrupted"])
def test_freeze_evidence_preserves_sources_and_requires_completed_run(
    tmp_path, monkeypatch, terminal_status
):
    import hashlib

    script = (
        Path(__file__).resolve().parents[2] / "publication/scripts/freeze_evidence.py"
    )
    spec = importlib.util.spec_from_file_location("publication_freeze", script)
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    definitions = [
        SimpleNamespace(id=stage, dependencies=()) for stage in runner.SOURCES
    ]
    definitions.append(
        SimpleNamespace(id="export-beta2", dependencies=tuple(runner.SOURCES))
    )
    monkeypatch.setattr(runner, "REFERENCE_STAGES", definitions)
    monkeypatch.setattr(runner, "load_snapshot", lambda _: SimpleNamespace())
    for stage in definitions:
        stage.fingerprint_data = lambda _: {"revision": 1}
    data = {
        "collect-gpr-evidence": '{"reaction_id":"r","candidate_gpr":"g"}\n',
        "collect-location-evidence": json.dumps(
            {
                "gene_locations": {
                    "g": {"raw_locations": [{"go_id": "GO:1"}], "confidence": "strong"}
                }
            }
        ),
        "collect-reaction-location-evidence": '{"reaction_id":"r","locations":[]}\n',
        "normalize-compartments": json.dumps(
            {"go_graph": {"GO:1": []}, "source_releases": {"go": "frozen"}}
        ),
    }
    fingerprint = runner.sha256_json({"revision": 1})
    steps = {"export-beta2": {"status": "running", "fingerprint": fingerprint}}
    for stage, content in data.items():
        suffix = (
            ".jsonl"
            if stage in ("collect-gpr-evidence", "collect-reaction-location-evidence")
            else ".json"
        )
        path = tmp_path / (stage + suffix)
        path.write_text(content)
        steps[stage] = {
            "fingerprint": fingerprint,
            "status": "completed",
            "outputs": [
                {
                    "role": runner.SOURCES[stage],
                    "path": path.name,
                    "sha256": hashlib.sha256(content.encode()).hexdigest(),
                }
            ],
        }
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"steps": steps}))
    template = tmp_path / "replay.json"
    template.write_text(
        json.dumps(
            {
                "run": {"output_dir": "run-b"},
                "beta2": {"evidence_mode": "live", "go_ontology_file": "unfrozen.obo"},
            }
        )
    )
    out = tmp_path / "frozen"
    with pytest.raises(ValueError, match="incomplete stage"):
        runner.freeze(tmp_path, template, out)
    assert not out.exists()
    steps["export-beta2"]["status"] = "completed"
    steps["collect-gpr-evidence"]["status"] = "running"
    manifest.write_text(json.dumps({"steps": steps}))
    with pytest.raises(ValueError, match="incomplete stage"):
        runner.freeze(tmp_path, template, out)
    steps["collect-gpr-evidence"]["status"] = "completed"
    manifest.write_text(json.dumps({"steps": steps}))
    definitions[0].fingerprint_data = lambda _: {"revision": 2}
    with pytest.raises(ValueError, match="stale stage fingerprint"):
        runner.freeze(tmp_path, template, out)
    with pytest.raises(ValueError, match="terminal source run"):
        runner.freeze(tmp_path, template, tmp_path / "archive", archived=True)
    manifest.write_text(json.dumps({"steps": steps, "overall_status": terminal_status}))
    runner.freeze(tmp_path, template, tmp_path / "archive", archived=True)
    archived = json.loads((tmp_path / "archive/manifest.json").read_text())
    assert archived["runtime_fingerprints_verified"] is False
    assert archived["input_status"] == "archived acquisition outputs"
    definitions[0].fingerprint_data = lambda _: {"revision": 1}
    generated = runner.freeze(tmp_path, template, out)
    config = json.loads(generated.read_text())
    assert config["beta2"]["evidence_mode"] == "snapshot"
    assert "go_ontology_file" not in config["beta2"]
    records = [
        json.loads(line)
        for line in (out / "beta2-evidence.jsonl").read_text().splitlines()
    ]
    assert [row["record_type"] for row in records] == [
        "metadata",
        "gpr",
        "location",
        "reaction-location",
    ]
    assert records[2]["raw_locations"] == [{"go_id": "GO:1"}]
    assert (out / "sources/collect-gpr-evidence.jsonl").read_text() == data[
        "collect-gpr-evidence"
    ]
    with pytest.raises(FileExistsError, match="must be empty"):
        runner.freeze(tmp_path, template, out)

    (tmp_path / "collect-gpr-evidence.jsonl").write_text("changed")
    with pytest.raises(ValueError, match="differs from ledger"):
        runner.freeze(tmp_path, template, tmp_path / "other")


def test_workflow_figure_source_covers_registered_stages_and_gate_groups(monkeypatch):
    script = (
        Path(__file__).resolve().parents[2] / "publication/scripts/plot_workflow.py"
    )
    spec = importlib.util.spec_from_file_location("publication_workflow_plot", script)
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    rows = runner.workflow_rows()
    assert [row["stage"] for row in rows] == [
        stage.id for stage in runner.REFERENCE_STAGES
    ]
    by_id = {row["stage"]: row for row in rows}
    assert by_id["load-beta1"]["implicit_reference_upstream"] == "export-beta1"
    assert by_id["gate-beta2"]["group"] == "Expand compartments (beta2)"
    assert by_id["integrate-human-database"]["group"] == "Integrate database (optional)"
    assert by_id["gate-gapfill"]["group"] == "Gapfill"
    monkeypatch.setattr(
        runner,
        "REFERENCE_STAGES",
        [stage for stage in runner.REFERENCE_STAGES if stage.id != "gate-beta2"],
    )
    with pytest.raises(ValueError, match="review figure grouping"):
        runner.workflow_rows()


def test_stage_table_accepts_disabled_optional_dependencies(tmp_path, monkeypatch):
    script = Path(__file__).resolve().parents[2] / "publication/scripts/stage_table.py"
    spec = importlib.util.spec_from_file_location("publication_stages", script)
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)

    def fingerprint_data(_):
        return {"version": 1}

    optional = SimpleNamespace(id="optional", dependencies=(), enabled=lambda _: False)
    exported = SimpleNamespace(
        id="export", dependencies=("optional",), fingerprint_data=fingerprint_data
    )
    monkeypatch.setattr(runner, "REFERENCE_STAGES", [optional, exported])
    monkeypatch.setattr(runner, "load_snapshot", lambda _: SimpleNamespace())
    (tmp_path / "manifest.json").write_text(
        json.dumps(
            {
                "overall_status": "completed",
                "steps": {
                    "optional": {"status": "skipped", "attempt": 0},
                    "export": {
                        "status": "completed",
                        "attempt": 1,
                        "outputs": [],
                        "fingerprint": runner.sha256_json(fingerprint_data(None)),
                    },
                },
            }
        )
    )
    rows = runner.export(tmp_path, tmp_path / "out")
    assert rows[1]["status"] == "completed"
    optional.enabled = lambda _: True
    rows = runner.export(tmp_path, tmp_path / "out")
    assert rows[1]["status"] == "stale"


@pytest.mark.gurobi
def test_publication_gurobi_threads_apply_to_actual_task_copies(tmp_path, monkeypatch):
    gurobipy = pytest.importorskip("gurobipy")
    from thg_protocol.tasks import MetabolicTask, TaskSuite

    script = Path(__file__).resolve().parents[2] / "publication/scripts/run_tasks.py"
    spec = importlib.util.spec_from_file_location("publication_tasks", script)
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    model_path = tmp_path / "model.json"
    model_path.write_text("{}")
    monkeypatch.setattr(cobra.io, "load_json_model", lambda _: cobra.Model("threads"))
    monkeypatch.setenv("THG_SOLVER", "gurobi")
    monkeypatch.delenv("THG_BLOCK", raising=False)
    monkeypatch.setattr(
        "sys.argv", [str(script), str(model_path), "test", str(tmp_path)]
    )
    suite = TaskSuite("native-thread-check", "1", (MetabolicTask("feasible"),))
    monkeypatch.setattr(
        runner,
        "import_raven_tasks",
        lambda *_args, **_kwargs: SimpleNamespace(suite=suite),
    )
    previous_threads = gurobipy.getParamInfo("Threads")[2]
    previous_solver = cobra.Configuration().solver
    try:
        runner.main()
        report = json.loads((tmp_path / "task_results_test.json").read_text())
        for table in report["reports"].values():
            solved = table["tasks"][0]
            assert solved["status"] == "passed"
            assert solved["diagnostics"]["solver_threads"] == 2
            assert (
                solved["diagnostics"]["solver_interface"] == "optlang.gurobi_interface"
            )
    finally:
        gurobipy.setParam("Threads", previous_threads)
        cobra.Configuration().solver = previous_solver


def test_location_policy_measurement_preserves_conflicts_and_unmapped_genes():
    script = (
        Path(__file__).resolve().parents[2] / "publication/scripts/measure_locations.py"
    )
    spec = importlib.util.spec_from_file_location("publication_locations", script)
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    rows = runner.measure(
        {"dual", "single", "conflict", "unmapped"},
        {
            "dual": {"locations": ["c", "m", "c"], "status": "candidate"},
            "single": {"locations": ["c"], "status": "candidate"},
            "conflict": {"locations": ["c", "m"], "status": "conflicting"},
            "not-a-baseline-gene": {"locations": ["c", "m"]},
        },
    )
    assert sum(row["retained_before"] for row in rows) == 1
    assert sum(row["retained_after"] for row in rows) == 2
    assert sum(row["lost_under_old_multi_location_rule"] for row in rows) == 1
    assert len(rows) == 4
    with pytest.raises(ValueError, match="Invalid resolved locations"):
        runner.measure({"bad"}, {"bad": {"locations": "cytosol"}})
