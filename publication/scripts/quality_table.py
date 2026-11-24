"""Tabulate validation reports side by side.

Usage: quality_table.py OUT.csv LABEL=VALIDATION_REPORT.json [LABEL=...]

One row per metric, one column per model. Counts come from the
``thg.validation.report/v1`` checks; a metric a report lacks is ``n/a``.
"""

import csv
import json
import sys
from pathlib import Path

METRICS = [
    # (metric, check id, detail key)
    ("reactions_with_mass_imbalance", "mass-balance", "imbalance"),
    ("mass_imbalance_not_by_design", "mass-balance", "unbalanced"),
    ("reactions_with_charge_imbalance", "charge-balance", "imbalance"),
    ("charge_imbalance_not_by_design", "charge-balance", "unbalanced"),
    ("fractional_coefficient_reactions", "fractional-coefficients", "reactions"),
    (
        "formula_disagreement_across_compartments",
        "formula-disagreement",
        "across_compartments",
    ),
    ("unusual_proton_reactions", "unusual-protons", "reactions"),
    ("dead_end_metabolites", "dead-end-topology", "metabolites"),
    ("blocked_reactions", "flux-consistency", "blocked"),
    ("obligatory_loops", "obligatory-loops", "loops"),
    ("obligatory_loop_reactions", "obligatory-loops", "reactions"),
    ("unconserved_metabolites", "stoichiometric-consistency", "unconserved"),
    ("metabolites_leaking_produced", "metabolite-leaks", "produced"),
    ("metabolites_leaking_consumed", "metabolite-leaks", "consumed"),
    ("energy_generating_cycles", "energy-generating-cycles", "cycles"),
    ("objective_value", "objective-feasibility", "objective"),
    ("objective_status", "objective-feasibility", "status"),
]


def size(value):
    return len(value) if isinstance(value, (list, dict)) else value


def column(path):
    report = json.loads(Path(path).read_text())
    checks = {c["id"]: c for c in report["validation"]["checks"]}
    values = {
        "reactions": report["after"]["reactions"],
        "metabolites": report["after"]["metabolites"],
        "genes": report["after"]["genes"],
        "compartments": report["after"]["compartments"],
        "memote": report["memote"]["status"],
        "model_sha256": report["model_checksum"],
    }
    for name, check, key in METRICS:
        row = checks.get(check, {})
        details = {} if row.get("status") == "not-evaluated" else row.get("details", {})
        values[name] = size(details[key]) if key in details else "n/a"
    for check_id, check in checks.items():
        values[f"check:{check_id}"] = check["status"]
    return values


def main():
    out = Path(sys.argv[1])
    labelled = [arg.split("=", 1) for arg in sys.argv[2:]]
    columns = {label: column(path) for label, path in labelled}
    names = list(dict.fromkeys(k for col in columns.values() for k in col))
    with out.open("w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["metric", *columns])
        for name in names:
            writer.writerow([name, *(col.get(name, "n/a") for col in columns.values())])
    print(f"wrote {out}: {len(names)} metrics x {len(columns)} models")


if __name__ == "__main__":
    main()
