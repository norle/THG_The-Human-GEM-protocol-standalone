from __future__ import annotations

import hashlib
import json

import pytest

from thg_protocol.workflow.artifacts import (
    ArtifactReferenceError,
    resolve_artifact,
)
from thg_protocol.workflow.config import ConfigError, load_workflow_config
from thg_protocol.workflow.evidence import EvidenceError, EvidenceRecord, EvidenceStore
from thg_protocol.workflow.ids import DeterministicIdRegistry, IdRegistryError
from thg_protocol.workflow.proposals import (
    ChangeLedger,
    Decision,
    Proposal,
    ProposalError,
    apply_proposals,
    apply_proposals_file,
    write_proposals,
)
from thg_protocol.workflow.registry import REGISTRY, list_workflows


def test_workflow_config_rejects_sections_for_another_workflow(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps(
            {
                "format_version": 2,
                "workflow": "beta1",
                "run": {"name": "run", "output_dir": str(tmp_path / "run")},
                "beta2": {},
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match="do not apply"):
        load_workflow_config(path)


def test_beta1_config_rejects_unknown_section_keys(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps(
            {
                "format_version": 2,
                "workflow": "beta1",
                "run": {"name": "run", "output_dir": str(tmp_path / "run")},
                "beta1": {"not_a_beta1_option": True},
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match="unknown key"):
        load_workflow_config(path)


def test_builtin_workflows_have_independently_validated_dags():
    assert {"beta1", "beta2", "validate", "compare"}.issubset(list_workflows())
    REGISTRY.validate_all()
    for workflow_id in ("beta1", "beta2"):
        definition = REGISTRY.get(workflow_id)
        assert len(definition.stage_ids) == 6
        assert definition.stage_ids


def test_evidence_store_connects_raw_checksum_and_rejects_schema_drift(tmp_path):
    store = EvidenceStore(tmp_path / "evidence")
    raw, digest = store.cache_raw(b"recorded response")
    record = EvidenceRecord(
        evidence_id="ev-1",
        source="fixture",
        source_version="2026-08-06",
        query={"id": "A"},
        normalized_result={"match": "A"},
        raw_response_path=str(raw.relative_to(store.root)),
        raw_response_sha256=digest,
        parser_version="parser-1",
        normalization_version="normalizer-1",
        confidence="high",
        affected_objects=("metabolite:A",),
        errors=(),
        warnings=(),
        retry_history=(),
        license="fixture",
    )
    store.append(record)
    assert store.read()[0].evidence_id == "ev-1"
    store.verify_offline()
    with pytest.raises(EvidenceError, match="unsupported"):
        EvidenceRecord.from_mapping({**record.to_dict(), "schema_version": 99})


def test_proposal_modes_share_input_set_and_ledger_is_idempotent(tmp_path):
    proposal = Proposal(
        "p1",
        "update",
        "metabolite",
        "m1",
        {"name": "old"},
        {"name": "new"},
        ("ev-1",),
        "high",
        "default",
        "beta1-proposals",
        reason="curated",
    )
    seen: list[object] = []
    applied_all, ledger_all = apply_proposals(
        [proposal], apply=lambda item, value: seen.append(value)
    )
    report_only, ledger_report = apply_proposals([proposal], mode="report-only")
    user_only, ledger_user = apply_proposals(
        [proposal],
        mode="user-approved-only",
        decisions=[Decision("p1", "approve")],
        apply=lambda item, value: seen.append(value),
    )
    assert [item.proposal_id for item in applied_all] == [
        item.proposal_id for item in user_only
    ]
    assert not report_only
    assert len(ledger_all) == len(ledger_report) == len(ledger_user) == 1
    assert seen == [{"name": "new"}, {"name": "new"}]

    proposal_path = tmp_path / "proposals.jsonl"
    write_proposals(proposal_path, [proposal])
    applied_from_file, _ = apply_proposals_file(
        proposal_path, apply=lambda item, value: seen.append(value)
    )
    assert [item.proposal_id for item in applied_from_file] == ["p1"]

    ledger = ChangeLedger(tmp_path / "ledger.jsonl")
    ledger.append(ledger_all)
    ledger.append(ledger_all)
    assert len(ledger.entries()) == 1
    with pytest.raises(ProposalError, match="unknown proposal"):
        apply_proposals([proposal], decisions=[Decision("missing", "approve")])


def test_deterministic_ids_are_stable_and_conflicts_fail(tmp_path):
    first = DeterministicIdRegistry(tmp_path / "ids.json")
    first_id = first.generate(object_type="metabolite", source_id="A", compartment="c")
    first.generate(object_type="metabolite", source_id="unrelated", compartment="c")
    first.save()
    second = DeterministicIdRegistry(tmp_path / "ids.json")
    assert (
        second.generate(object_type="metabolite", source_id="A", compartment="c")
        == first_id
    )
    second.register_imported(source_id="A", target_id="original")
    with pytest.raises(IdRegistryError, match="conflicting"):
        second.register_imported(source_id="A", target_id="different")


def test_artifact_reference_rejects_ambiguous_roles(tmp_path):
    run = tmp_path / "run"
    (run / "artifact").mkdir(parents=True)
    (run / "artifact" / "a").write_text("a", encoding="utf-8")
    (run / "artifact" / "b").write_text("b", encoding="utf-8")
    records = []
    for name in ("a", "b"):
        path = run / "artifact" / name
        records.append(
            {
                "role": "same",
                "path": f"artifact/{name}",
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "size": 1,
            }
        )
    (run / "manifest.json").write_text(
        json.dumps(
            {
                "format_version": 2,
                "steps": {"stage": {"status": "completed", "outputs": records}},
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ArtifactReferenceError, match="ambiguous"):
        resolve_artifact({"run_dir": str(run), "stage_id": "stage", "role": "same"})
