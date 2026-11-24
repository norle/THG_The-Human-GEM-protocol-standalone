"""Measure the effect of the gapfill-selection change (plan version 6 -> 7).

Usage: measure_gapfill_change.py OLD_PLAN NEW_PLAN NEW_REPORT CONNECTORS OUT_JSON
Reads saved plan artifacts only; no solver is run.
"""
import json
import sys


def load(path):
    return [json.loads(line) for line in open(path)]


def split(rows):
    plan = [r for r in rows if r.get("record_type") != "header"]
    return ({r["reaction_id"] for r in plan if r.get("phase") == 2},
            {r["reaction_id"] for r in plan if r.get("phase") == 3})


def main(old, new, report, conn, out):
    old_c, old_s = split(load(old))
    new_c, new_s = split(load(new))
    proposed = {json.loads(line)["reaction_id"] for line in open(conn)}
    rep = json.load(open(report))
    ver = rep["solver"].get("verification")
    result = {
        "connectors_proposed_new_run": len(proposed),
        "connectors_in_old_plan": len(old_c),
        "connectors_kept_new": len(new_c),
        "connectors_dropped_new": len(old_c - new_c),
        "kept_subset_of_old_connectors": new_c <= old_c,
        "kept_not_in_old": sorted(new_c - old_c),
        "selected_ptrs_old": len(old_s),
        "selected_ptrs_new": len(new_s),
        "selected_ptrs_identical": old_s == new_s,
        "selected_only_old": sorted(old_s - new_s),
        "selected_only_new": sorted(new_s - old_s),
        "reactions_added_old": len(old_c | old_s),
        "reactions_added_new": len(new_c | new_s),
        "reactions_differing": len((old_c | old_s) ^ (new_c | new_s)),
        "solver": {k: v for k, v in rep["solver"].items() if k != "verification"},
        "verification": ver,
        "before_metrics": rep["before_metrics"],
        "after_metrics": rep["after_metrics"],
    }
    json.dump(result, open(out, "w"), indent=1, default=str)
    print(json.dumps({k: v for k, v in result.items()
                      if k not in ("verification", "solver")}, indent=1)[:2500])


if __name__ == "__main__":
    main(*sys.argv[1:6])
