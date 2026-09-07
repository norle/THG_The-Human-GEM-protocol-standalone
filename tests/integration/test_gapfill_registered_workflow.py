from __future__ import annotations

import json
from pathlib import Path

import pytest
from cobra import Metabolite, Model, Reaction
from cobra.io import save_json_model

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
                    "allowed_connections": [],
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
                "beta2": {"compartments": {"c": "cytosol", "m": "mitochondria"}},
                "human_database": {"records": str(records)},
                "reference": {
                    "human_database_integration": {"source_precedence": "base"}
                },
                "gapfill": {
                    "method": "greedy",
                    "max_additions": 1,
                    "allowed_connections": [],
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
