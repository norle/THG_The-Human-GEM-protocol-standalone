"""Measure the old standalone multi-location filter on current real evidence.

python publication/scripts/measure_locations.py
This isolates the policy changed in 0188ac5, not the complete legacy pipeline.
"""

import csv
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / "runs/thg-ws1-a"


def measure(genes, records):
    rows = []
    for gene in sorted(genes):
        record = records.get(gene, {})
        locations = record.get("locations", [])
        if not isinstance(locations, list) or not all(
            isinstance(x, str) for x in locations
        ):
            raise ValueError(f"Invalid resolved locations for {gene}")
        targets = sorted(set(locations))
        after = bool(targets) and record.get("status") != "conflicting"
        before = after and len(targets) == 1
        rows.append(
            {
                "gene": gene,
                "status": record.get("status", "missing"),
                "mapped_locations": json.dumps(targets),
                "retained_before": before,
                "retained_after": after,
                "lost_under_old_multi_location_rule": after and not before,
            }
        )
    return rows


def main():
    manifest = json.loads((RUN / "manifest.json").read_text())
    config = json.loads((RUN / "config.snapshot.json").read_text())
    assert (
        config["beta2"].get("uncertainty_policy", "reject-conflicts")
        == "reject-conflicts"
    )
    sources, data = [], []
    for stage, role in (
        ("apply-balance-proposals", "model"),
        ("resolve-compartment-evidence", "evidence"),
    ):
        state = manifest["steps"][stage]
        assert state["status"] == "completed", stage
        artifact = next(item for item in state["outputs"] if item["role"] == role)
        path = RUN / artifact["path"]
        checksum = hashlib.sha256(path.read_bytes()).hexdigest()
        if checksum != artifact["sha256"]:
            raise ValueError(f"Source differs from ledger: {path}")
        sources.append({"path": str(path.relative_to(ROOT)), "sha256": checksum})
        data.append(json.loads(path.read_text()))
    genes = {gene["id"] for gene in data[0]["genes"]}
    records = data[1]["gene_locations"]
    rows = measure(genes, records)
    assert len(rows) == len(genes)
    summary = {
        "baseline_derived_genes": len(genes),
        "genes_with_evidence_records": len(genes & records.keys()),
        "localized_under_historical_rule": sum(row["retained_before"] for row in rows),
        "localized_under_current_rule": sum(row["retained_after"] for row in rows),
        "lost_under_historical_multi_location_rule": sum(
            row["lost_under_old_multi_location_rule"] for row in rows
        ),
        "without_mapped_targets": sum(
            not json.loads(row["mapped_locations"]) for row in rows
        ),
        "sources": sources,
        "rule_change_commit": "0188ac599131edb27ec3c5933abef4aa0ffa41fd",
        "command": "python publication/scripts/measure_locations.py",
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "code_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "scope": "Historical standalone policy applied to the same current resolved "
        "evidence; no legacy lookup execution or reaction-level effect claimed",
        "legacy_attribution": "not established by this experiment",
    }
    out = ROOT / "publication/ws2"
    with (out / "gene_locations.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0], lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    (out / "gene_locations.json").write_text(json.dumps(summary, indent=2) + "\n")
    print({key: value for key, value in summary.items() if isinstance(value, int)})


if __name__ == "__main__":
    main()
