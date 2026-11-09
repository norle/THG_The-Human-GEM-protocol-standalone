"""Measure identity conflicts and inherited imbalance in archived WS1 artifacts.

python publication/scripts/measure_correctness.py
This measures chemistry/identity, not task feasibility or final-model quality.
"""

import hashlib
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

from cobra import Metabolite, Reaction

from thg_protocol.curation.beta1 import _chemical_identifiers, _identifiers_conflict

ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS = ROOT / "runs/thg-ws1-a/artifacts"


def measure(model, cleanup, plan, expansion_model, corrected_plan):
    metabolites = {item["id"]: item for item in model["metabolites"]}
    reactions = {item["id"]: item for item in expansion_model["reactions"]}
    expansion_metabolites = {
        item["id"]: item for item in expansion_model["metabolites"]
    }
    conflicts = []
    for old, kept in cleanup["retained_metabolites"].items():
        left = _chemical_identifiers(SimpleNamespace(**metabolites[old]))
        right = _chemical_identifiers(SimpleNamespace(**metabolites[kept]))
        namespaces = sorted(
            key for key in left.keys() & right.keys() if left[key] != right[key]
        )
        assert bool(namespaces) == _identifiers_conflict(left, right)
        conflicts.append(
            {
                "removed": old,
                "retained": kept,
                "conflicting_namespaces": namespaces,
                "rejected_by_current_identifier_rule": bool(namespaces),
            }
        )
    imbalance = {}
    copies = []
    for entry in plan:
        if entry["action"] != "create":
            continue
        parent = entry["reaction_id"]
        if parent not in imbalance:
            reaction = Reaction(parent)
            reaction.add_metabolites(
                {
                    Metabolite(
                        key,
                        formula=expansion_metabolites[key].get("formula"),
                        charge=expansion_metabolites[key].get("charge"),
                    ): coefficient
                    for key, coefficient in reactions[parent]["metabolites"].items()
                }
            )
            imbalance[parent] = reaction.check_mass_balance()
        if imbalance[parent]:
            copies.append(
                {
                    "parent": parent,
                    "location": entry.get("location"),
                    "imbalance": imbalance[parent],
                }
            )
    excluded = {
        (entry["reaction_id"], entry.get("location"))
        for entry in corrected_plan
        if entry.get("reason") == "unbalanced-parent"
    }
    return {
        "archived_corrected_exclusions_matching_old_copies": sum(
            (row["parent"], row["location"]) in excluded for row in copies
        ),
        "origin_identity_defect": "introduced by redesign",
        "origin_parent_chemistry": "inherited from baseline",
        "identity_pairs": conflicts,
        "old_merge_pairs": len(conflicts),
        "pairs_vetoed_by_identifier_rule": sum(
            row["rejected_by_current_identifier_rule"] for row in conflicts
        ),
        "old_unbalanced_copies": copies,
        "unbalanced_copy_count": len(copies),
        "unbalanced_parent_count": len({row["parent"] for row in copies}),
        "charge_only_parents": sorted(
            {row["parent"] for row in copies if set(row["imbalance"]) == {"charge"}}
        ),
        "scope": "Archived real-model proposals; not corrected-run or task evidence",
    }


def main():
    paths = [
        ARTIFACTS / item
        for item in (
            "apply-balance-proposals/attempt-0001/balanced-model.json",
            "deduplicate-and-clean/attempt-0001/cleanup.json",
            "generate-expansion-plan/attempt-0001/beta2-expansion-plan.jsonl",
            "export-beta1/attempt-0001/thg-beta1-candidate.json",
            "generate-expansion-plan/attempt-0002/beta2-expansion-plan.jsonl",
        )
    ]
    model, cleanup = [json.loads(path.read_text()) for path in paths[:2]]
    plan = [json.loads(line) for line in paths[2].read_text().splitlines()]
    result = measure(
        model,
        cleanup,
        plan,
        json.loads(paths[3].read_text()),
        [json.loads(line) for line in paths[4].read_text().splitlines()],
    )
    result["sources"] = [
        {
            "path": str(path.relative_to(ROOT)),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
        for path in paths
    ]
    result["code_commit"] = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    result["command"] = "python publication/scripts/measure_correctness.py"
    (ROOT / "publication/ws2/correctness.json").write_text(
        json.dumps(result, indent=2) + "\n"
    )
    print(
        {
            key: result[key]
            for key in (
                "old_merge_pairs",
                "pairs_vetoed_by_identifier_rule",
                "unbalanced_copy_count",
                "unbalanced_parent_count",
            )
        }
    )


if __name__ == "__main__":
    main()
