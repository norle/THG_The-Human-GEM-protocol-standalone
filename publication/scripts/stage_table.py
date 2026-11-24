"""Export current WS1 stage sizes/runtime without loading a solver.

python publication/scripts/stage_table.py RUN_DIR OUTDIR
Pending/invalidated outputs are omitted even when old files remain on disk.
"""

import csv
import hashlib
import json
import sys
from datetime import datetime
from functools import cache
from pathlib import Path
from xml.etree.ElementTree import iterparse

from thg_protocol.runtime.hashing import sha256_json
from thg_protocol.runtime.stage import StageContext
from thg_protocol.workflow.config import load_snapshot
from thg_protocol.workflow.reference import REFERENCE_STAGES


def model_size(path):
    if path.suffix == ".json":
        model = json.loads(path.read_text())
        return {key: len(model[key]) for key in ("reactions", "metabolites", "genes")}
    counts = {"reactions": 0, "metabolites": 0, "genes": 0}
    tags = {"reaction": "reactions", "species": "metabolites", "geneProduct": "genes"}
    for _, element in iterparse(path):
        key = tags.get(element.tag.rsplit("}", 1)[-1])
        if key:
            counts[key] += 1
        element.clear()
    return counts


def export(run, out):
    manifest_bytes = (run / "manifest.json").read_bytes()
    manifest = json.loads(manifest_bytes)
    definitions = {stage.id: stage for stage in REFERENCE_STAGES}
    steps = manifest["steps"]
    context = StageContext(load_snapshot(run), run.resolve(), manifest)

    @cache
    def current(stage_id):
        state = steps[stage_id]
        if state["status"] == "skipped":
            return not definitions[stage_id].enabled(context.config)
        if state["status"] != "completed":
            return False
        try:
            fingerprint = sha256_json(definitions[stage_id].fingerprint_data(context))
        except Exception:
            return False
        return state["fingerprint"] == fingerprint and all(
            current(dependency) for dependency in definitions[stage_id].dependencies
        )

    @cache
    def models(stage_id):
        state = steps[stage_id]
        if not current(stage_id):
            return []
        result = []
        for artifact in state.get("outputs", []):
            if artifact["role"] != "model":
                continue
            path = run / artifact["path"]
            checksum = hashlib.sha256(path.read_bytes()).hexdigest()
            if checksum != artifact["sha256"]:
                raise ValueError(f"Artifact differs from ledger: {path}")
            result.append(
                {"path": artifact["path"], "sha256": checksum, **model_size(path)}
            )
        return result

    @cache
    def inputs(stage_id):
        result = {}
        for dependency in definitions[stage_id].dependencies:
            if not current(dependency) or steps[dependency]["status"] == "skipped":
                continue
            for model in models(dependency) or inputs(dependency):
                result[model["path"]] = model
        return list(result.values())

    rows = []
    for stage in REFERENCE_STAGES:
        state = steps[stage.id]
        start, end = state.get("started_at"), state.get("finished_at")
        runtime = (
            (
                datetime.fromisoformat(end.replace("Z", "+00:00"))
                - datetime.fromisoformat(start.replace("Z", "+00:00"))
            ).total_seconds()
            if start and end
            else None
        )
        cleanup = None
        if stage.id == "deduplicate-and-clean" and current(stage.id):
            artifact = next(
                item for item in state["outputs"] if item["role"] == "cleanup"
            )
            path = run / artifact["path"]
            if hashlib.sha256(path.read_bytes()).hexdigest() != artifact["sha256"]:
                raise ValueError(f"Cleanup differs from ledger: {path}")
            cleanup = len(json.loads(path.read_text())["retained_metabolites"])
        rows.append(
            {
                "stage": stage.id,
                "status": (
                    "stale"
                    if state["status"] == "completed" and not current(stage.id)
                    else state["status"]
                ),
                "attempt": state["attempt"],
                "started_at": start,
                "finished_at": end,
                "runtime_seconds": runtime,
                "input_models": json.dumps(inputs(stage.id), sort_keys=True),
                "output_models": json.dumps(models(stage.id), sort_keys=True),
                "merged_metabolites": cleanup,
            }
        )
    out.mkdir(parents=True, exist_ok=True)
    with (out / "stage_table.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0], lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    (out / "run_manifest.json").write_bytes(manifest_bytes)
    (out / "stage_table_provenance.json").write_text(
        json.dumps(
            {
                "run": str(run.resolve()),
                "overall_status": manifest["overall_status"],
                "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
                "command": f"python publication/scripts/stage_table.py {run} {out}",
                "scope": "Current manifest attempts; completed-stage models checked "
                "against ledger and runtime fingerprints; task gates not inferred",
            },
            indent=2,
        )
        + "\n"
    )
    return rows


if __name__ == "__main__":
    export(Path(sys.argv[1]), Path(sys.argv[2]))
