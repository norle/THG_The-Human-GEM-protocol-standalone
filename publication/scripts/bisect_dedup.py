"""Bisect which deduplicate-and-clean merge makes VerifyModel task 21 feasible.
Usage: bisect_dedup.py RUN_ARTIFACTS_DIR OUT.json"""
import os, sys, json
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "2")
from pathlib import Path
import cobra
from thg_protocol.raven_tasks import import_raven_tasks
from thg_protocol.tasks import run_task_suite

A = Path(sys.argv[1]); out = sys.argv[2]
T = Path(__file__).resolve().parents[2] / "files/metabolic_tasks"
cobra.Configuration().solver = "gurobi"
base = cobra.io.load_json_model(str(A / "apply-balance-proposals/attempt-0001/balanced-model.json"))
base.solver.configuration.threads = 2
c = json.load(open(A / "deduplicate-and-clean/attempt-0001/cleanup.json"))
for r in base.reactions:
    if not r.boundary:
        if r.lower_bound > 0: r.lower_bound = 0
        if r.upper_bound < 0: r.upper_bound = 0

def merge(model, pairs, drop_rxns):
    for a, b in pairs:
        old, new = model.metabolites.get_by_id(a), model.metabolites.get_by_id(b)
        for r in list(old.reactions):
            coef = r.metabolites[old]
            r.subtract_metabolites({old: coef})
            r.add_metabolites({new: coef})
    for rid in drop_rxns:
        if rid in model.reactions: model.reactions.get_by_id(rid).remove_from_model()

def feasible21(model):
    imp = import_raven_tasks(T / "metabolicTasks_VerifyModel.txt", model, mapping=T / "human_gem_names.json")
    import dataclasses
    suite = dataclasses.replace(imp.suite, tasks=tuple(t for t in imp.suite.tasks if str(t.id) == "21"))
    rep = run_task_suite(model, suite)
    return rep["tasks"][0]["actual_outcome"]

mets = list(c["retained_metabolites"].items())
rxns = list(c["retained_reactions"])
res = {}
res["none"] = feasible21(base.copy())
for pair in mets:
    m = base.copy(); merge(m, [pair], [])
    res[f"{pair[0]}->{pair[1]}"] = feasible21(m); print(pair, res[f"{pair[0]}->{pair[1]}"], flush=True)
m = base.copy(); merge(m, mets, []); res["all-metabolites"] = feasible21(m)
m = base.copy(); merge(m, mets, rxns); res["all+reactions"] = feasible21(m)
print(res); json.dump(res, open(out, "w"), indent=1)
