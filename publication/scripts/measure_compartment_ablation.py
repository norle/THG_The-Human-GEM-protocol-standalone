"""Replay three β2 planning stages with historical standalone location rules."""

import csv
import hashlib
import json
import subprocess
import tempfile
from collections import Counter
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import cobra
from measure_hpa_agreement import HPA_DIR, compare, hpa_locations, summarize

from thg_protocol.curation import go
from thg_protocol.runtime.stage import StageContext, dependency_path
from thg_protocol.workflow.beta2._stages import Beta2Stage
from thg_protocol.workflow.config import load_workflow_config

RUN = Path("runs/thg-ws1-b")
CONFIG = Path("publication/ws1/reference-b-frozen.json")
OUT = Path("publication/ws2/compartment-resolution")
OLD_GO = "4e88dea275ad934df3f4c7301d7d5c719a1eede1^"
STAGES = (
    ("resolve-compartment-evidence", "evidence"),
    ("infer-complex-and-isoenzyme-locations", "locations"),
    ("generate-expansion-plan", "plan"),
)


def read(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def replay(ctx, folder, resolver, reject_multi, names):
    for stage, role in STAGES:
        with patch.object(go, "resolve_go_compartment", resolver):
            result = Beta2Stage(stage).run(ctx, folder)
        path = dict(result.outputs)[role]
        if stage == "resolve-compartment-evidence":
            payload = read(path)
            genes = payload["gene_locations"]
            if reject_multi:
                for record in genes.values():
                    if len(record.get("locations", [])) > 1:
                        record["status"] = "conflicting"
                path.write_text(json.dumps(payload))
        entry = {stage: {"outputs": [{"role": role, "path": str(path)}]}}
        ctx = replace(ctx, manifest={"steps": ctx.manifest["steps"] | entry})
    copies = Counter(
        row["target_compartment"]
        for line in path.read_text().splitlines()
        if (row := json.loads(line))["action"] == "create"
    )
    targets = {
        gene: {names[location] for location in record["locations"]}
        for gene, record in genes.items()
        if record.get("locations") and record.get("status") != "conflicting"
    }
    return targets, copies, digest(path)


def main():
    cobra.Configuration().solver = "glpk"
    ctx = StageContext(load_workflow_config(CONFIG), RUN, read(RUN / "manifest.json"))
    registry = read(dependency_path(ctx, "normalize-compartments", "registry"))
    names = {name: key for key, name in registry["compartments"].items()}
    hpa, *_ = hpa_locations(registry, registry["go_graph"], False)
    old_go = {}
    source = subprocess.check_output(
        ["git", "show", f"{OLD_GO}:src/thg_protocol/curation/go.py"], text=True
    )
    exec(compile(source, f"{OLD_GO}:go.py", "exec"), old_go)
    variants = (
        ("both-older-rules", old_go["resolve_go_compartment"], True),
        ("retain-multi-location-genes", old_go["resolve_go_compartment"], False),
        ("current", go.resolve_go_compartment, False),
    )
    evidence = [
        dependency_path(ctx, stage, role)
        for stage, role in (
            ("normalize-compartments", "registry"),
            ("collect-location-evidence", "evidence"),
            ("collect-reaction-location-evidence", "evidence"),
            ("resolve-gprs", "gprs"),
            ("resolve-gprs", "model"),
            ("generate-expansion-plan", "plan"),
        )
    ]
    rows, targets_by_variant = [], {}
    with tempfile.TemporaryDirectory() as temp:
        for name, resolver, reject_multi in variants:
            folder = Path(temp) / name
            folder.mkdir()
            targets, copies, plan_hash = replay(
                ctx, folder, resolver, reject_multi, names
            )
            targets_by_variant[name] = targets
            rows.append(
                {
                    "variant": name,
                    "genes_localised": len(targets),
                    "copies": copies.total(),
                    "copies_by_compartment": dict(copies),
                    "plan_sha256": plan_hash,
                }
            )
    expected = digest(evidence[-1])
    if rows[-1]["plan_sha256"] != expected:
        raise ValueError("Current-rule planning replay differs from rebuilt B")
    common = set.intersection(*(set(g) for g in targets_by_variant.values()))
    for row in rows:
        targets = targets_by_variant[row["variant"]]
        row["hpa_all"] = summarize(compare(hpa, targets))
        row["hpa_common_genes"] = summarize(
            compare(hpa, {g: targets[g] for g in common})
        )
    hpa_path = HPA_DIR / "source/subcellular_location.tsv"
    frozen = Path(ctx.config.sections["beta2"]["evidence_file"])
    OUT.mkdir(parents=True, exist_ok=True)
    summary = {
        "command": "python publication/scripts/measure_compartment_ablation.py",
        "code_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True
        ).strip(),
        "script_sha256": digest(Path(__file__)),
        "old_go_source": OLD_GO,
        "scope": (
            "Historical standalone rules on frozen B inputs. "
            "HPA comparison uses gene targets."
        ),
        "sources": {
            str(path): digest(path) for path in (*evidence, CONFIG, hpa_path, frozen)
        },
        "variants": rows,
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    with (OUT / "copies_by_compartment.csv").open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(
            ("variant", "genes_localised", "total_copies", *sorted(names.values()))
        )
        for row in rows:
            writer.writerow(
                (
                    row["variant"],
                    row["genes_localised"],
                    row["copies"],
                    *(
                        row["copies_by_compartment"].get(key, 0)
                        for key in sorted(names.values())
                    ),
                )
            )


if __name__ == "__main__":
    main()
