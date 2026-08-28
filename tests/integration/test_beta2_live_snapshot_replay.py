from __future__ import annotations

import json
from pathlib import Path

from cobra import Metabolite, Model, Reaction
from cobra.io import save_json_model

from thg_protocol.gpr import location as gpr_location
from thg_protocol.gpr import lookup
from thg_protocol.services import biocyc
from thg_protocol.workflow.runner import get_status, start


def _artifact(run: Path, role: str) -> Path:
    outputs = get_status(run)["steps"]["export-beta2"]["outputs"]
    return run / next(item["path"] for item in outputs if item["role"] == role)


def _stage_artifact(run: Path, stage: str, role: str) -> Path:
    outputs = get_status(run)["steps"][stage]["outputs"]
    return run / next(item["path"] for item in outputs if item["role"] == role)


def _jsonl(path: Path) -> list[dict[str, object]]:
    return [
        {
            key: value
            for key, value in json.loads(line).items()
            if key != "record_type"
        }
        for line in path.read_text().splitlines()
        if line.strip()
    ]


def _semantic(value: object) -> object:
    if isinstance(value, dict):
        return {
            key: _semantic(item)
            for key, item in value.items()
            if key != "record_type" and not (key == "identifiers" and item == {})
        }
    if isinstance(value, list):
        return [_semantic(item) for item in value]
    return value


def _config(path: Path, run: Path, model: Path, **beta2: object) -> None:
    path.write_text(
        json.dumps(
            {
                "workflow": "beta2",
                "run": {"name": run.name, "output_dir": str(run)},
                "beta2": {
                    "input_model": str(model),
                    "external_beta1_equivalent": True,
                    "compartments": {"c": "cytosol", "m": "mitochondria"},
                    "run_solver_checks": False,
                    **beta2,
                },
            }
        ),
        encoding="utf-8",
    )


def test_live_smoke_snapshot_replay_is_semantically_identical(tmp_path, monkeypatch):
    model = Model("beta2-live-smoke")
    metabolites = [
        Metabolite("a_c", formula="C", compartment="c"),
        Metabolite("b_c", formula="C", compartment="c"),
    ]
    reactions = []
    for reaction_id, gpr, ec in (
        ("R_VALID", "G_MODEL", "1.1.1.1"),
        ("R_MISSING", "", "2.2.2.2"),
        ("R_CCO", "", "3.3.3.3"),
    ):
        reaction = Reaction(reaction_id)
        reaction.add_metabolites({metabolites[0]: -1, metabolites[1]: 1})
        reaction.gene_reaction_rule = gpr
        reaction.annotation["ec-code"] = [ec]
        reactions.append(reaction)
    model.add_reactions(reactions)
    source = tmp_path / "beta1-smoke.json"
    save_json_model(model, source)

    calls: list[str] = []
    candidates = {
        "1.1.1.1": "G_LIVE",
        "2.2.2.2": "G_EC",
        "3.3.3.3": "G_CCO",
    }

    def fake_gpr(ec: str, **kwargs) -> dict[str, object]:
        del kwargs
        calls.append(ec)
        gene = candidates[ec]
        return {
            "ec": ec,
            "source": "biocyc",
            "source_version": "fixture",
            "retrieved_at": "2026-08-14T00:00:00Z",
            "parser_version": "fixture-parser-v1",
            "gene_symbols": [gene],
            "gene_identifiers": [f"ID-{gene}"],
            "candidate_gpr": f"({gene})",
            "status": "candidate",
            "warnings": [],
            "source_metadata": {
                "source": "BioCyc",
                "release": "fixture-release",
                "url": "https://fixture.invalid/ec",
                "raw_response_sha256": "a" * 64,
                "parser_version": "fixture-parser-v1",
            },
        }

    class FakeBioCycClient:
        def __init__(self, **kwargs):
            del kwargs

        def get_cco(self, identifier: str):
            calls.append(f"cco:{identifier}")
            return {
                "name": "mitochondrial inner membrane"
                if identifier == "CCO-IMEM"
                else "mitochondrion",
                "component_of": ["CCO-MIT"] if identifier == "CCO-IMEM" else [],
            }

    def fake_locations(*args, **kwargs):
        assert "ensembl_client" not in kwargs
        del args, kwargs
        return {}, {"Mitochondria": "(G)"}, {}, {}

    monkeypatch.setattr(lookup, "get_gpr_evidence", fake_gpr)
    monkeypatch.setattr(gpr_location, "resolve_locations", fake_locations)
    monkeypatch.setattr(biocyc, "BioCycClient", FakeBioCycClient)

    live_config = tmp_path / "live.json"
    live_run = tmp_path / "live-run"
    _config(
        live_config,
        live_run,
        source,
        evidence_mode="live",
        reaction_location_evidence={
            "R_CCO": [
                {
                    "raw_location": "mitochondrial inner membrane",
                    "cco_id": "CCO-IMEM",
                },
                {"raw_location": "nucleus"},
            ]
        },
    )
    start(live_config)
    assert get_status(live_run)["overall_status"] == "completed"
    for role in (
        "fallback-checkpoint",
        "rhea-checkpoint",
        "reactome-checkpoint",
    ):
        assert _stage_artifact(live_run, "collect-gpr-evidence", role).is_file()
    assert (
        calls.count("1.1.1.1")
        == calls.count("2.2.2.2")
        == calls.count("3.3.3.3")
        == 1
    )
    assert "cco:CCO-IMEM" in calls and "cco:CCO-MIT" in calls

    gpr_records = [
        json.loads(line)
        for line in _artifact(live_run, "gpr-evidence").read_text().splitlines()
    ]
    valid = next(item for item in gpr_records if item["reaction_id"] == "R_VALID")
    assert valid["source"] == "biocyc"
    assert get_status(live_run)["steps"]["resolve-gprs"]["summary"]["conflicts"] == 1
    resolutions = json.loads(
        _artifact(live_run, "compartment-resolution-evidence").read_text()
    )
    assert any(
        item.get("status") == "rejected"
        and item.get("reason") == "location-not-in-registry"
        for item in resolutions["reaction_locations"]
    )
    assert any(
        item.get("status") == "conflict"
        for item in json.loads(
            _stage_artifact(live_run, "resolve-gprs", "gprs").read_text()
        )["records"].values()
    )

    snapshot = _artifact(live_run, "evidence-snapshot")
    snapshot_metadata = next(
        json.loads(line)
        for line in snapshot.read_text().splitlines()
        if json.loads(line).get("record_type") == "metadata"
    )
    assert snapshot_metadata["source_releases"]["biocyc"]["release"] == (
        "fixture-release"
    )
    assert snapshot_metadata["source_releases"]["biocyc"][
        "raw_response_sha256"
    ] == "a" * 64
    snapshot_config = tmp_path / "snapshot.json"
    snapshot_run = tmp_path / "snapshot-run"
    _config(
        snapshot_config,
        snapshot_run,
        source,
        evidence_mode="snapshot",
        evidence_file=str(snapshot),
    )
    calls.clear()
    start(snapshot_config)
    assert calls == []
    assert get_status(snapshot_run)["overall_status"] == "completed"
    for role in (
        "gpr-evidence",
        "proposals",
    ):
        assert _jsonl(_artifact(snapshot_run, role)) == _jsonl(
            _artifact(live_run, role)
        )
    for role in ("compartment-resolution-evidence", "id-registry"):
        assert _semantic(
            json.loads(_artifact(snapshot_run, role).read_text())
        ) == _semantic(
            json.loads(_artifact(live_run, role).read_text())
        )


def test_snapshot_keeps_each_source_and_prefers_reactome_structure(tmp_path):
    model = Model("beta2-sgpr-sources")
    left = Metabolite("left_c", formula="C", compartment="c")
    right = Metabolite("right_c", formula="C", compartment="c")
    reaction = Reaction("R_SGPR")
    reaction.add_metabolites({left: -1, right: 1})
    reaction.annotation["ec-code"] = ["1.1.1.1"]
    model.add_reactions([reaction])
    source = tmp_path / "beta1.json"
    save_json_model(model, source)
    evidence = tmp_path / "evidence.jsonl"
    evidence.write_text(
        "\n".join(
            json.dumps(item)
            for item in (
                {
                    "record_type": "gpr-evidence",
                    "reaction_id": "R_SGPR",
                    "ec": "1.1.1.1",
                    "source": "rhea",
                    "candidate_gpr": "A or B",
                    "status": "candidate",
                },
                {
                    "record_type": "gpr-evidence",
                    "reaction_id": "R_SGPR",
                    "ec": "1.1.1.1",
                    "source": "reactome",
                    "candidate_gpr": "A and B",
                    "status": "resolved",
                },
            )
        )
        + "\n",
        encoding="utf-8",
    )
    config = tmp_path / "beta2.json"
    run = tmp_path / "run"
    _config(
        config,
        run,
        source,
        evidence_mode="snapshot",
        evidence_file=str(evidence),
    )

    start(config)

    records = [
        item
        for item in _jsonl(_artifact(run, "gpr-evidence"))
        if item.get("reaction_id") == "R_SGPR"
    ]
    assert [item["source"] for item in records] == ["reactome", "rhea"]
    resolutions = json.loads(_stage_artifact(run, "resolve-gprs", "gprs").read_text())
    assert resolutions["records"]["R_SGPR"]["gpr"] == "A and B"
