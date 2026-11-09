"""Freeze completed beta2 evidence and prepare a fresh offline replay config.

python publication/scripts/freeze_evidence.py RUN_DIR REPLAY_CONFIG OUTDIR
This freezes collected evidence, not the original remote HTTP responses.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path

from thg_protocol.runtime.hashing import sha256_json
from thg_protocol.runtime.stage import StageContext
from thg_protocol.workflow.config import load_snapshot
from thg_protocol.workflow.reference import REFERENCE_STAGES

SOURCES = {
    "collect-gpr-evidence": "evidence",
    "collect-location-evidence": "evidence",
    "collect-reaction-location-evidence": "evidence",
    "normalize-compartments": "registry",
}


def freeze(run, template, out, *, archived=False):
    if out.exists() and any(out.iterdir()):
        raise FileExistsError(f"Freeze destination must be empty: {out}")
    raw_manifest = (run / "manifest.json").read_bytes()
    manifest = json.loads(raw_manifest)
    if archived and manifest.get("overall_status") not in {
        "completed",
        "failed",
        "interrupted",
    }:
        raise ValueError("Archived input capture requires a terminal source run")
    steps = manifest["steps"]
    definitions = {stage.id: stage for stage in REFERENCE_STAGES}
    context = StageContext(load_snapshot(run), run.resolve(), manifest)

    def require_current(stage_id):
        if steps[stage_id]["status"] != "completed":
            raise ValueError(f"Cannot freeze incomplete stage: {stage_id}")
        if not archived and steps[stage_id]["fingerprint"] != sha256_json(
            definitions[stage_id].fingerprint_data(context)
        ):
            raise ValueError(f"Cannot freeze stale stage fingerprint: {stage_id}")
        for dependency in definitions[stage_id].dependencies:
            require_current(dependency)

    require_current("export-beta2")
    payloads, catalog, source_bytes = {}, [], {}
    for stage, role in SOURCES.items():
        require_current(stage)
        artifact = next(
            item for item in steps[stage]["outputs"] if item["role"] == role
        )
        path = run / artifact["path"]
        content = path.read_bytes()
        checksum = hashlib.sha256(content).hexdigest()
        if checksum != artifact["sha256"]:
            raise ValueError(f"Evidence differs from ledger: {path}")
        name = path.name
        source_bytes[name] = content
        payloads[stage] = (
            [json.loads(line) for line in content.decode().splitlines() if line.strip()]
            if path.suffix == ".jsonl"
            else json.loads(content)
        )
        catalog.append(
            {
                "stage": stage,
                "source_path": artifact["path"],
                "frozen_path": f"sources/{name}",
                "sha256": checksum,
            }
        )
    registry = payloads["normalize-compartments"]
    metadata = {"record_type": "metadata", **registry}
    records = [metadata]
    for record in payloads["collect-gpr-evidence"]:
        if record.get("reaction_id"):
            records.append({**record, "record_type": "gpr"})
    for gene, record in sorted(
        payloads["collect-location-evidence"]["gene_locations"].items()
    ):
        records.append({**record, "record_type": "location", "gene_id": gene})
    for record in payloads["collect-reaction-location-evidence"]:
        if record.get("reaction_id"):
            records.append({**record, "record_type": "reaction-location"})
    snapshot = "".join(json.dumps(record, sort_keys=True) + "\n" for record in records)
    config = json.loads(template.read_text())
    config["beta2"]["evidence_mode"] = "snapshot"
    config["beta2"]["evidence_file"] = os.path.relpath(
        out / "beta2-evidence.jsonl", template.parent
    )
    # Snapshot metadata supplies the ontology; no live/file adapters may add records.
    for key in (
        "go_ontology_file",
        "go_annotation_file",
        "uniprot_snapshot",
        "rhea_snapshot",
        "reactome_snapshot",
    ):
        config["beta2"].pop(key, None)
    generated = template.with_name(template.stem + "-frozen.json")
    (out / "sources").mkdir(parents=True, exist_ok=True)
    for name, content in source_bytes.items():
        (out / "sources" / name).write_bytes(content)
    (out / "beta2-evidence.jsonl").write_text(snapshot)
    generated.write_text(json.dumps(config, indent=2) + "\n")
    (out / "source-run-manifest.json").write_bytes(raw_manifest)
    (out / "manifest.json").write_text(
        json.dumps(
            {
                "source_run": str(run.resolve()),
                "runtime_fingerprints_verified": not archived,
                "input_status": "archived acquisition outputs"
                if archived
                else "current runtime artifacts",
                "source_manifest_sha256": hashlib.sha256(raw_manifest).hexdigest(),
                "script_sha256": hashlib.sha256(
                    Path(__file__).read_bytes()
                ).hexdigest(),
                "template_sha256": hashlib.sha256(template.read_bytes()).hexdigest(),
                "snapshot_sha256": hashlib.sha256(snapshot.encode()).hexdigest(),
                "source_releases": registry.get("source_releases", {}),
                "artifacts": catalog,
                "records": len(records),
                "replay_config": str(generated),
                "scope": "Collected location/GPR evidence and ontology replay; "
                "resolution and construction rerun; HTTP acquisition not replayed",
                "comparison_required": "Measure checksums and semantic differences; "
                "snapshot provenance can differ",
            },
            indent=2,
        )
        + "\n"
    )
    return generated


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    parser.add_argument("template", type=Path)
    parser.add_argument("out", type=Path)
    parser.add_argument(
        "--archived",
        action="store_true",
        help=(
            "Capture terminal acquisition outputs as archived inputs; "
            "do not certify their runtime fingerprints"
        ),
    )
    args = parser.parse_args()
    print(freeze(args.run, args.template, args.out, archived=args.archived))
