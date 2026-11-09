"""Run Human-GEM RAVEN task tables on a model with the stored name mapping.

Usage: run_tasks.py MODEL LABEL OUTDIR [TABLE ...]
Optional env THG_BLOCK=RXN,RXN sets those reactions to [0,0] in memory (patch test).
Settings (benchmark protocol): closed medium, Gurobi, forced non-boundary
fluxes (LB>0 or UB<0) relaxed to 0, name mapping files/metabolic_tasks/human_gem_names.json.
"""
import os
for _v in ("OMP_NUM_THREADS","OPENBLAS_NUM_THREADS","MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "2")
import csv, subprocess, sys
from pathlib import Path

import cobra
from thg_protocol.raven_tasks import import_raven_tasks
from thg_protocol.tasks import run_task_suite

ROOT = Path(__file__).resolve().parents[2]
TASKS = ROOT / "files/metabolic_tasks"
MAPPING = TASKS / "human_gem_names.json"
TABLES = {"VerifyModel": "metabolicTasks_VerifyModel.txt",
          "Essential": "metabolicTasks_Essential.txt",
          "Full": "metabolicTasks_Full.txt"}


def main():
    model_path, label, outdir = sys.argv[1:4]
    which = sys.argv[4:] or list(TABLES)
    out = Path(outdir); out.mkdir(parents=True, exist_ok=True)
    cobra.Configuration().solver = "gurobi"
    cobra.Configuration().processes = 1
    model = cobra.io.load_json_model(model_path) if model_path.endswith(".json") else cobra.io.read_sbml_model(model_path)
    model.solver.configuration.threads = 2
    relaxed = 0
    for r in model.reactions:
        if r.boundary:
            continue
        if r.lower_bound > 0:
            r.lower_bound = 0; relaxed += 1
        if r.upper_bound < 0:
            r.upper_bound = 0; relaxed += 1
    for rid in filter(None, os.environ.get("THG_BLOCK", "").split(",")):
        model.reactions.get_by_id(rid).bounds = (0, 0)
    commit = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    rows = []
    for name in which:
        imp = import_raven_tasks(TASKS / TABLES[name], model, mapping=MAPPING)
        rep = run_task_suite(model, imp.suite)
        for t in rep["tasks"]:
            d = t.get("diagnostics") or {}
            cause = ""
            if t["status"] == "invalid":
                cause = "; ".join(map(str, d.get("problems", [])))[:300]
            elif t["status"] == "error":
                cause = str(d)[:300]
            rows.append({"model": label, "table": name, "task_id": t["id"],
                         "description": next((x.description for x in imp.suite.tasks if x.id == t["id"]), ""),
                         "expected": t["expected_outcome"], "actual": t["actual_outcome"],
                         "status": t["status"], "solver_status": t["solver_status"], "cause": cause})
        print(label, name, rep["counts"], flush=True)
    with open(out / f"task_results_{label}.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    print("relaxed forced bounds:", relaxed, "commit", commit)


main()
