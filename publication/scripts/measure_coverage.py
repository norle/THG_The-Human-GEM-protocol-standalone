"""Coverage analysis: what a THG build adds to the baseline, by stage.

Usage: measure_coverage.py BASELINE_MODEL THG_MODEL GAPFILL_DIR EVIDENCE_JSON OUTDIR

Reports, for reactions that are in THG but not in the baseline, split into
beta2 compartment copies (``THG_*``) and gapfill reactions (``GAPFILL_*``):
counts, mass and charge balance, gene association, location-evidence source,
compartment pairs, and dead-end metabolites before and after.
No optimization is used. Flux capability comes from the validation reports.
"""

import collections
import csv
import json
import os
import sys
from pathlib import Path

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "2")

import cobra  # noqa: E402

from thg_protocol.analysis.consistency import (  # noqa: E402
    dead_end_metabolites,
    unassessable_reactions,
    unbalanced_reactions,
    unbalanced_reactions_by_charge,
)


def load(path):
    return (
        cobra.io.load_json_model(path)
        if str(path).endswith(".json")
        else cobra.io.read_sbml_model(path)
    )


def balance(model, ids):
    wanted = set(ids)
    unassessable = set(unassessable_reactions(model)) & wanted
    mass = set(unbalanced_reactions(model)) & wanted
    charge = set(unbalanced_reactions_by_charge(model)) & wanted
    return {
        "reactions": len(wanted),
        "unassessable": len(unassessable),
        "mass_unbalanced": len(mass),
        "charge_unbalanced": len(charge),
        "mass_and_charge_balanced": len(wanted - unassessable - mass - charge),
    }


def location_sources(reaction, evidence):
    """Sources behind the location evidence of a copy's genes.

    Raw location names (e.g. "Lysosome membrane") are not the compartment
    names, so the source is taken from the genes' evidence as a whole, not
    matched to the chosen compartment.
    """
    found = set()
    for gene in reaction.genes:
        for raw in evidence.get(gene.id, {}).get("raw_locations", []):
            found.add(raw.get("source", "unknown"))
    return "+".join(sorted(found)) or "none"


def main():
    baseline_path, thg_path, gapfill_dir, evidence_path, outdir = sys.argv[1:6]
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    baseline, thg = load(baseline_path), load(thg_path)
    evidence = json.loads(Path(evidence_path).read_text())["gene_locations"]
    base_ids = {r.id for r in baseline.reactions}
    added = [r for r in thg.reactions if r.id not in base_ids]
    groups = {
        "beta2-copy": [r for r in added if r.id.startswith("THG_")],
        "gapfill": [r for r in added if r.id.startswith("GAPFILL_")],
    }
    other = [r for r in added if r not in groups["beta2-copy"] + groups["gapfill"]]
    if other:
        raise ValueError(f"unclassified added reactions: {len(other)}")

    result = {
        "baseline": {
            "reactions": len(baseline.reactions),
            "metabolites": len(baseline.metabolites),
            "dead_end_metabolites": len(dead_end_metabolites(baseline)),
        },
        "thg": {
            "reactions": len(thg.reactions),
            "metabolites": len(thg.metabolites),
            "dead_end_metabolites": len(dead_end_metabolites(thg)),
        },
        "removed_baseline_reactions": len(base_ids - {r.id for r in thg.reactions}),
        "balance": {
            "baseline_all": balance(baseline, base_ids),
            **{name: balance(thg, [r.id for r in rs]) for name, rs in groups.items()},
        },
    }

    copies = groups["beta2-copy"]
    result["beta2_copies"] = {
        "with_gpr": sum(bool(r.gene_reaction_rule) for r in copies),
        "distinct_parents": len(
            {r.annotation.get("thg_source_reaction") for r in copies}
        ),
        "by_location": dict(
            collections.Counter(r.annotation.get("thg_location") for r in copies)
        ),
        "location_source": dict(
            collections.Counter(location_sources(r, evidence) for r in copies)
        ),
        "gpr_policy_evidence": dict(
            collections.Counter(
                str(r.annotation.get("thg_evidence_id", "")).split(":")[0]
                for r in copies
            )
        ),
    }

    fills = groups["gapfill"]
    plan = [
        json.loads(line) for line in (Path(gapfill_dir) / "gapfill-plan.jsonl").open()
    ]
    by_id = {p["reaction_id"]: p for p in plan if "reaction_id" in p}
    pairs = collections.Counter(
        "-".join(sorted({m.compartment for m in r.metabolites})) for r in fills
    )
    result["gapfill"] = {
        "by_candidate_type": dict(
            collections.Counter(by_id[r.id].get("candidate_type") for r in fills)
        ),
        "by_phase": dict(collections.Counter(by_id[r.id].get("phase") for r in fills)),
        "by_coverage_kind": dict(
            collections.Counter(
                str(by_id[r.id].get("coverage_or_improvement", {}).get("coverage"))
                for r in fills
            )
        ),
        "compartment_pairs": dict(pairs.most_common()),
        "report": {
            key: value
            for key, value in json.loads(
                (Path(gapfill_dir) / "gapfill-report.json").read_text()
            ).items()
            if key in {"before_metrics", "after_metrics", "status", "stop_reason"}
        },
    }
    (out / "coverage.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n"
    )
    with (out / "coverage_summary.csv").open("w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["metric", "value"])
        writer.writerow(["baseline_reactions", result["baseline"]["reactions"]])
        writer.writerow(["thg_reactions", result["thg"]["reactions"]])
        for name, rs in groups.items():
            writer.writerow([f"added_{name}", len(rs)])
            for key, value in result["balance"][name].items():
                writer.writerow([f"{name}_{key}", value])
        writer.writerow(
            ["baseline_dead_ends", result["baseline"]["dead_end_metabolites"]]
        )
        writer.writerow(["thg_dead_ends", result["thg"]["dead_end_metabolites"]])
    print(json.dumps(result, indent=1)[:3000])


if __name__ == "__main__":
    main()
