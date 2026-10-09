from __future__ import annotations

import json
from pathlib import Path

import pytest
from cobra import Metabolite, Model, Reaction
from cobra.io import load_json_model, save_json_model

from thg_protocol.workflow.runner import get_status, resume, start


def _model(path: Path) -> None:
    model = Model("gapfill-fixture")
    metabolites = {
        identifier: Metabolite(identifier, compartment=compartment)
        for identifier, compartment in (
            ("A_c", "c"),
            ("A_e", "e"),
            ("B_c", "c"),
            ("B_e", "e"),
        )
    }
    for reaction_id, stoichiometry in (
        ("R_c", {"A_c": -1, "B_c": 1}),
        ("R_e", {"A_e": -1, "B_e": 1}),
    ):
        reaction = Reaction(reaction_id)
        reaction.add_metabolites(
            {metabolites[key]: value for key, value in stoichiometry.items()}
        )
        model.add_reactions([reaction])
    save_json_model(model, path)


def _config(tmp_path: Path, source: Path, *, maximum: int = 10) -> Path:
    config = tmp_path / "gapfill.json"
    config.write_text(
        json.dumps(
            {
                "workflow": "gapfill",
                "run": {"name": "gapfill", "output_dir": str(tmp_path / "run")},
                "gapfill": {
                    "input_model": str(source),
                    "external_input": True,
                    "method": "greedy",
                    "max_additions": maximum,
                    "allowed_connections": [["c", "e"]],
                    "candidate_types": ["A", "B", "C"],
                    "validation_profile": "structural-fast",
                },
            }
        ),
        encoding="utf-8",
    )
    return config


def test_gapfill_workflow_exports_external_provenance_and_release_bundle(tmp_path):
    source = tmp_path / "model.json"
    _model(source)
    start(_config(tmp_path, source))
    status = get_status(tmp_path / "run")
    assert status["overall_status"] == "completed"
    assert (
        json.loads(
            (
                tmp_path
                / "run"
                / status["steps"]["load-gapfill-source"]["outputs"][1]["path"]
            ).read_text()
        )["external_input"]
        is True
    )
    names = {
        Path(item["path"]).name
        for item in status["steps"]["export-gapfilled-reference"]["outputs"]
    }
    assert {
        "thg-reference-gapfilled.json",
        "gapfill-plan.jsonl",
        "gapfill-change-ledger.jsonl",
        "gapfill-gate.json",
        "validation-report.html",
    } <= names


def test_gapfill_limit_is_blocked_without_release_export(tmp_path):
    source = tmp_path / "model.json"
    _model(source)
    with pytest.raises(RuntimeError, match="gate-gapfill"):
        start(_config(tmp_path, source, maximum=1))
    status = get_status(tmp_path / "run")
    assert status["overall_status"] == "failed"
    assert status["steps"]["gate-gapfill"]["status"] == "failed"
    assert status["steps"]["export-gapfilled-reference"]["status"] == "pending"


def test_reference_workflow_hands_off_beta2_and_keeps_it_unchanged(tmp_path):
    fixture = (
        Path(__file__).parents[1]
        / "fixtures"
        / "beta1"
        / "sanctioned_human_reference.json"
    )
    config = tmp_path / "reference.json"
    config.write_text(
        json.dumps(
            {
                "workflow": "reference",
                "run": {"name": "reference", "output_dir": str(tmp_path / "run")},
                "beta1": {
                    "input_model": str(fixture.resolve()),
                    "sanctioned_model": True,
                },
                "beta2": {
                    "compartments": {"c": "cytosol", "m": "mitochondria"},
                    "gene_locations": {
                        "ENSG000001": ["cytosol"],
                        "ENSG000002": ["mitochondria"],
                    },
                },
                "gapfill": {
                    "method": "greedy",
                    "max_additions": 1,
                    "allowed_connections": [["c", "e"]],
                    "candidate_types": ["A", "B", "C"],
                    "validation_profile": "structural-fast",
                },
            }
        ),
        encoding="utf-8",
    )
    start(config)
    status = get_status(tmp_path / "run")
    beta2 = next(
        item
        for item in status["steps"]["export-beta2"]["outputs"]
        if item["role"] == "model"
    )
    source = next(
        item
        for item in status["steps"]["load-gapfill-source"]["outputs"]
        if item["role"] == "model"
    )
    assert beta2["sha256"] == source["sha256"]
    assert status["steps"]["gate-beta2"]["summary"]["status"] == "passed"
    assert status["steps"]["export-gapfilled-reference"]["status"] == "completed"


def test_reference_workflow_accepts_an_intermediate_beta1_candidate(tmp_path):
    source = tmp_path / "model.json"
    _model(source)
    config = tmp_path / "reference.json"
    config.write_text(
        json.dumps(
            {
                "workflow": "reference",
                "run": {"name": "reference", "output_dir": str(tmp_path / "run")},
                "beta1": {"input_model": str(source.resolve())},
                "beta2": {
                    "compartments": {"c": "cytosol", "e": "extracellular"},
                    "gene_locations": {"ENSG000001": ["cytosol"]},
                },
                "gapfill": {
                    "method": "greedy",
                    "max_additions": 10,
                    "allowed_connections": [["c", "e"]],
                    "candidate_types": ["A", "B", "C"],
                    "validation_profile": "structural-fast",
                },
            }
        ),
        encoding="utf-8",
    )

    status = get_status(start(config))

    assert status["steps"]["gate-beta2"]["summary"]["status"] == "passed"


def test_forcing_validation_reuses_gapfill_plan_and_model(tmp_path):
    source = tmp_path / "model.json"
    _model(source)
    start(_config(tmp_path, source))
    before = get_status(tmp_path / "run")["steps"]
    resume(tmp_path / "run", force_step="validate-gapfill")
    after = get_status(tmp_path / "run")["steps"]
    assert (
        after["generate-gapfill-plan"]["attempt"]
        == before["generate-gapfill-plan"]["attempt"]
    )
    assert after["apply-gapfill"]["attempt"] == before["apply-gapfill"]["attempt"]
    assert (
        after["validate-gapfill"]["attempt"]
        == before["validate-gapfill"]["attempt"] + 1
    )


def test_resume_refreshes_old_validation_without_reapplying_gapfill(
    tmp_path, monkeypatch
):
    from thg_protocol.workflow.registry import get_workflow

    source = tmp_path / "model.json"
    _model(source)
    with monkeypatch.context() as previous_version:
        for stage in get_workflow("gapfill").stages:
            if stage.id == "validate-gapfill":
                previous_version.setattr(stage, "implementation_version", 1)
        start(_config(tmp_path, source))
    before = get_status(tmp_path / "run")["steps"]

    resume(tmp_path / "run")
    after = get_status(tmp_path / "run")["steps"]

    assert (
        after["validate-gapfill"]["attempt"]
        == before["validate-gapfill"]["attempt"] + 1
    )
    for stage_id in (
        "characterize-gapfill-baseline",
        "generate-gapfill-plan",
        "apply-gapfill",
    ):
        assert after[stage_id]["attempt"] == before[stage_id]["attempt"]


def test_reference_gapfill_uses_human_database_integration(tmp_path):
    fixture = (
        Path(__file__).parents[1]
        / "fixtures"
        / "beta1"
        / "sanctioned_human_reference.json"
    )
    records = tmp_path / "records.json"
    records.write_text(
        json.dumps({"schema_version": 1, "metabolites": [], "reactions": []}),
        encoding="utf-8",
    )
    config = tmp_path / "reference.json"
    config.write_text(
        json.dumps(
            {
                "workflow": "reference",
                "run": {"name": "reference", "output_dir": str(tmp_path / "run")},
                "beta1": {
                    "input_model": str(fixture.resolve()),
                    "sanctioned_model": True,
                },
                "beta2": {
                    "compartments": {"c": "cytosol", "m": "mitochondria"},
                    "gene_locations": {"ENSG000001": ["cytosol"]},
                },
                "human_database": {"records": str(records)},
                "reference": {
                    "human_database_integration": {"source_precedence": "base"}
                },
                "gapfill": {
                    "method": "greedy",
                    "max_additions": 1,
                    "allowed_connections": [["c", "e"]],
                    "candidate_types": ["A", "B", "C"],
                    "validation_profile": "structural-fast",
                },
            }
        ),
        encoding="utf-8",
    )
    status = get_status(start(config))
    integrated = next(
        item
        for item in status["steps"]["integrate-human-database"]["outputs"]
        if item["role"] == "model"
    )
    source = next(
        item
        for item in status["steps"]["load-gapfill-source"]["outputs"]
        if item["role"] == "model"
    )
    assert source["sha256"] == integrated["sha256"]
    exported = status["steps"]["export-reference"]["outputs"]
    names = {Path(item["path"]).name for item in exported}
    assert {
        "beta1-semantic-diff.json",
        "beta2-semantic-diff.json",
        "human-database-semantic-diff.json",
        "gapfill-semantic-diff.json",
        "input-to-reference-semantic-diff.json",
    } <= names
    checksums = json.loads(
        (
            tmp_path
            / "run"
            / next(item for item in exported if item["role"] == "checksums")["path"]
        ).read_text()
    )
    assert {
        item["sha256"] for item in exported if item["role"] in {"model", "sbml"}
    } <= set(checksums["export-reference"])


def _reference_config(tmp_path: Path, source: Path, beta2: dict) -> Path:
    config = tmp_path / "reference.json"
    config.write_text(
        json.dumps(
            {
                "workflow": "reference",
                "run": {"name": "reference", "output_dir": str(tmp_path / "run")},
                "beta1": {"input_model": str(source.resolve())},
                "beta2": {
                    "compartments": {"c": "cytosol", "e": "extracellular"},
                    **beta2,
                },
                "gapfill": {
                    "method": "greedy",
                    "max_additions": 1,
                    "allowed_connections": [["c", "e"]],
                    "candidate_types": ["A", "B", "C"],
                    "validation_profile": "structural-fast",
                },
            }
        ),
        encoding="utf-8",
    )
    return config


def test_reference_blocks_beta2_without_gene_location_evidence(tmp_path):
    source = tmp_path / "model.json"
    _model(source)
    snapshot = tmp_path / "evidence.jsonl"
    snapshot.write_text("", encoding="utf-8")
    config = _reference_config(
        tmp_path,
        source,
        {"evidence_mode": "snapshot", "evidence_file": str(snapshot)},
    )

    with pytest.raises(RuntimeError, match="gate-beta2"):
        start(config)

    gate = json.loads(
        (tmp_path / "run/failed/gate-beta2/attempt-0001/beta2-gate.json").read_text()
    )
    assert gate["status"] == "blocked"
    assert "β2 found no gene-location evidence" in gate["reasons"]


def test_reference_blocks_gapfill_without_candidates_for_dead_ends(tmp_path):
    source = tmp_path / "model.json"
    model = Model("no-shared-metabolites")
    metabolites = {
        identifier: Metabolite(identifier, compartment=compartment)
        for identifier, compartment in (
            ("A_c", "c"),
            ("B_c", "c"),
            ("C_e", "e"),
            ("D_e", "e"),
        )
    }
    for reaction_id, stoichiometry in (
        ("R_c", {"A_c": -1, "B_c": 1}),
        ("R_e", {"C_e": -1, "D_e": 1}),
    ):
        reaction = Reaction(reaction_id)
        reaction.add_metabolites(
            {metabolites[key]: value for key, value in stoichiometry.items()}
        )
        model.add_reactions([reaction])
    save_json_model(model, source)
    config = _reference_config(
        tmp_path, source, {"gene_locations": {"ENSG000001": ["cytosol"]}}
    )

    with pytest.raises(RuntimeError, match="gate-gapfill"):
        start(config)

    gate = json.loads(
        (
            tmp_path / "run/failed/gate-gapfill/attempt-0001/gapfill-gate.json"
        ).read_text()
    )
    assert any("no candidate" in item for item in gate["blocking_findings"])


def _three_components(path: Path) -> None:
    """Main (c) plus two islands; phase 3 must drain island m's Ym surplus."""
    model = Model("sink-milp-fixture")
    reactions = {
        "EXA": {"Ac": -1},
        "R1": {"Ac": -1, "Dc": 1},
        "EXD": {"Dc": -1},
        "EXY": {"Yc": -1},
        "R2": {"Yc": -1, "Dc": 1},
        "I1": {"Ae": -1, "Be": 1},
        "I2": {"Be": -1, "Ae": 2},
        "I3": {"Be": -1, "Ke": 1},
        "J1": {"Ym": -1, "Wm": 1},
        "J2": {"Wm": -1, "Ym": 2},
        "J3": {"Km": -1, "Wm": 1},
    }
    metabolites = {
        identifier: Metabolite(identifier, compartment=identifier[-1])
        for stoichiometry in reactions.values()
        for identifier in stoichiometry
    }
    for reaction_id, stoichiometry in reactions.items():
        reaction = Reaction(
            reaction_id, lower_bound=-1000 if reaction_id in {"EXA", "EXY"} else 0
        )
        reaction.add_metabolites(
            {metabolites[key]: value for key, value in stoichiometry.items()}
        )
        model.add_reactions([reaction])
    save_json_model(model, path)


def _sink_milp_config(tmp_path: Path, source: Path) -> Path:
    config = _config(tmp_path, source)
    payload = json.loads(config.read_text(encoding="utf-8"))
    payload["gapfill"].update(
        method="sink-milp",
        allowed_connections=[["c", "e"], ["c", "m"], ["e", "m"]],
    )
    config.write_text(json.dumps(payload), encoding="utf-8")
    return config


_PHASE_STAGES = (
    "generate-gapfill-candidates",
    "select-gapfill-connectors",
    "compute-gapfill-coverage",
)


def _plan(run: Path) -> list[dict]:
    status = get_status(run)
    path = run / next(
        item["path"]
        for item in status["steps"]["generate-gapfill-plan"]["outputs"]
        if item["role"] == "plan"
    )
    return [json.loads(line) for line in path.read_text().splitlines()]


def test_sink_milp_workflow_runs_phase_stages(tmp_path):
    source = tmp_path / "model.json"
    _three_components(source)
    start(_sink_milp_config(tmp_path, source))
    status = get_status(tmp_path / "run")
    assert status["overall_status"] == "completed"
    for stage_id in _PHASE_STAGES:
        assert status["steps"][stage_id]["status"] == "completed"
    phases = {
        line["reaction_id"]: line["phase"]
        for line in _plan(tmp_path / "run")
        if "reaction_id" in line
    }
    assert phases == {
        "GAPFILL_PTR_Ac_Ae": 2,
        "GAPFILL_PTR_Ke_Km": 2,
        "GAPFILL_PTR_Yc_Ym": 3,
    }


def test_phase_stages_are_skipped_for_greedy(tmp_path):
    source = tmp_path / "model.json"
    _model(source)
    start(_config(tmp_path, source))
    steps = get_status(tmp_path / "run")["steps"]
    for stage_id in _PHASE_STAGES:
        assert steps[stage_id]["status"] == "skipped"


def test_coverage_resumes_from_partial_attempt(tmp_path, monkeypatch):
    from thg_protocol.gapfill import ptr

    original = ptr.compute_coverage
    calls: list[list[int]] = []

    def interrupting(*args, on_component=None, **kwargs):
        seen: list[int] = []
        calls.append(seen)

        def record(entry):
            on_component(entry)
            seen.append(entry.component)
            if len(calls) == 1 and len(seen) == 2:
                raise RuntimeError("stopped mid-coverage")

        return original(*args, on_component=record, **kwargs)

    monkeypatch.setattr(ptr, "compute_coverage", interrupting)
    source = tmp_path / "model.json"
    _three_components(source)
    with pytest.raises(RuntimeError, match="compute-gapfill-coverage"):
        start(_sink_milp_config(tmp_path, source))
    resume(tmp_path / "run")
    assert calls == [[1, 2], [3]]
    status = get_status(tmp_path / "run")
    assert status["overall_status"] == "completed"
    assert {line.get("phase") for line in _plan(tmp_path / "run")} >= {2, 3}


def test_coverage_resumes_after_a_hard_kill(tmp_path, monkeypatch):
    from thg_protocol.gapfill import ptr

    original = ptr.compute_coverage
    calls: list[list[int]] = []

    def interrupting(*args, on_component=None, **kwargs):
        seen: list[int] = []
        calls.append(seen)

        def record(entry):
            on_component(entry)
            seen.append(entry.component)
            if len(calls) == 1 and len(seen) == 2:
                raise RuntimeError("stopped mid-coverage")

        return original(*args, on_component=record, **kwargs)

    monkeypatch.setattr(ptr, "compute_coverage", interrupting)
    source = tmp_path / "model.json"
    _three_components(source)
    with pytest.raises(RuntimeError, match="compute-gapfill-coverage"):
        start(_sink_milp_config(tmp_path, source))
    # A killed process leaves its partial attempt in .tmp, still "running".
    run = tmp_path / "run"
    stage = "compute-gapfill-coverage"
    (run / ".tmp").mkdir(exist_ok=True)
    (run / "failed" / stage / "attempt-0001").rename(
        run / ".tmp" / f"{stage}-attempt-0001"
    )
    manifest = json.loads((run / "manifest.json").read_text())
    manifest["steps"][stage]["status"] = "running"
    manifest["overall_status"] = "running"
    (run / "manifest.json").write_text(json.dumps(manifest))
    resume(run)
    assert calls == [[1, 2], [3]]
    assert get_status(run)["overall_status"] == "completed"


def _failed_plan_header(run: Path) -> dict:
    path = run / "failed/generate-gapfill-plan/attempt-0001/gapfill-plan.jsonl"
    return json.loads(path.read_text().splitlines()[0])


def test_collision_skips_coverage_and_fails_the_plan(tmp_path, monkeypatch):
    from thg_protocol.gapfill import ptr

    def unexpected(*args, **kwargs):
        raise AssertionError("coverage computed despite a reaction-ID collision")

    monkeypatch.setattr(ptr, "compute_coverage", unexpected)
    source = tmp_path / "model.json"
    _model(source)
    model = load_json_model(source)
    clash = Reaction("GAPFILL_PTR_A_c_A_e")
    clash.add_metabolites({model.metabolites.A_c: -1, model.metabolites.B_c: 1})
    model.add_reactions([clash])
    save_json_model(model, source)
    config = _reference_config(
        tmp_path, source, {"gene_locations": {"ENSG000001": ["cytosol"]}}
    )
    payload = json.loads(config.read_text(encoding="utf-8"))
    payload["gapfill"].update(method="sink-milp", max_additions=10)
    config.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(RuntimeError, match="generate-gapfill-plan"):
        start(config)

    run = tmp_path / "run"
    assert get_status(run)["steps"]["compute-gapfill-coverage"]["status"] == (
        "completed"
    )
    header = _failed_plan_header(run)
    assert header["status"] == "failed"
    assert "reaction-ID collision" in header["failure"]


def test_plan_stage_records_solver_errors_in_a_failed_plan(tmp_path, monkeypatch):
    from thg_protocol.gapfill import ptr

    def broken(*args, **kwargs):
        raise RuntimeError("flux LP ended with status time_limit")

    monkeypatch.setattr(ptr, "verify_selection", broken)
    source = tmp_path / "model.json"
    _three_components(source)
    with pytest.raises(RuntimeError, match="gapfill algorithm failed"):
        start(_sink_milp_config(tmp_path, source))
    header = _failed_plan_header(tmp_path / "run")
    assert header["status"] == "failed"
    assert "time_limit" in header["failure"]
