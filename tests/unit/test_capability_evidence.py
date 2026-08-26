"""Validate the machine-readable capability and evidence registry."""

from __future__ import annotations

import json
import re
from pathlib import Path

from ruamel.yaml import YAML

from thg_protocol.capabilities import validate_capability_registry

ROOT = Path(__file__).parents[2]
REGISTRY = ROOT / "docs/protocol/capability-evidence.json"
STATUS = ROOT / "docs/protocol/implementation-status.md"
REFERENCE_REGISTRY = ROOT / "docs/reference/capabilities.yaml"

IMPLEMENTATIONS = {"Implemented", "External integration", "Archived", "Not implemented"}
VERIFICATIONS = {
    "Unit-tested",
    "Integration-tested",
    "Parity-tested",
    "Artifact-reproduction-tested",
    "Not yet verified",
}
WORKFLOW_COVERAGE = {
    "Operation",
    "Orchestrated stage",
    "Workflow-complete for documented scope",
    "Published stage complete",
    "N/A",
}
LEGACY_RELATIONSHIPS = {
    "Verified equivalent",
    "Intentional difference",
    "No replacement",
    "No legacy target",
    "Not assessed",
}
PUBLICATION_REPRODUCTIONS = {"Verified", "Not yet verified", "N/A"}


def test_registry_has_valid_controlled_values_and_existing_evidence_paths():
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    assert registry["schema_version"] == 1
    entries = registry["entries"]
    assert entries
    assert len({entry["id"] for entry in entries}) == len(entries)

    for entry in entries:
        assert entry["implementation"] in IMPLEMENTATIONS
        assert entry["verification"] in VERIFICATIONS
        assert entry["workflow_coverage"] in WORKFLOW_COVERAGE
        assert entry["legacy_relationship"] in LEGACY_RELATIONSHIPS
        assert entry["published_reproduction"] in PUBLICATION_REPRODUCTIONS
        for relative_path in (*entry["current_sources"], *entry["tests"]):
            assert (ROOT / relative_path).is_file(), (
                f"missing evidence path: {relative_path}"
            )


def test_public_status_matrix_contains_exactly_the_registry_entries():
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    expected = {entry["id"] for entry in registry["entries"]}
    status = STATUS.read_text(encoding="utf-8")
    actual = set(re.findall(r"^\| `([^`]+)` \|", status, flags=re.MULTILINE))
    assert actual == expected
    assert "Partial" not in status

    entries = {entry["id"]: entry for entry in registry["entries"]}
    for line in status.splitlines():
        if not line.startswith("| `"):
            continue
        cells = [cell.strip() for cell in line.split("|")[1:-1]]
        registry_entry = entries[cells[0].strip("`")]
        assert cells[1] == registry_entry["publication_concept"]
        assert cells[2:7] == [
            registry_entry["implementation"],
            registry_entry["verification"],
            registry_entry["workflow_coverage"],
            registry_entry["legacy_relationship"],
            registry_entry["published_reproduction"],
        ]
        assert cells[7] == "; ".join(registry_entry["known_differences"])


def test_maintained_docs_do_not_reintroduce_partial_status_admonitions():
    prohibited = re.compile(r"\bPartial\b")
    documents = [
        path for path in (ROOT / "docs").rglob("*.md") if "plans" not in path.parts
    ]
    assert not [path for path in documents if prohibited.search(path.read_text())]


def test_reference_capability_registry_has_scientific_coverage():
    payload = YAML(typ="safe").load(REFERENCE_REGISTRY.read_text(encoding="utf-8"))
    validate_capability_registry(payload["capabilities"])
