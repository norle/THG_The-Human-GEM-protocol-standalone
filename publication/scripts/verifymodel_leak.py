"""pFBA flux solution for feasible VerifyModel tasks. Usage: verifymodel_leak.py MODEL REFMODEL TASKID OUT.json"""
import os
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "2")
import json, sys
from pathlib import Path
import cobra
from cobra import Reaction
from cobra.flux_analysis import pfba
from thg_protocol.raven_tasks import import_raven_tasks

ROOT = Path(__file__).resolve().parents[2]
T = ROOT / "files/metabolic_tasks"
mp, refp, tid, out = sys.argv[1:5]
cobra.Configuration().solver = "gurobi"
_load = lambda p: cobra.io.load_json_model(p) if p.endswith('.json') else cobra.io.read_sbml_model(p)
m = _load(mp); m.solver.configuration.threads = 2
ref = _load(refp)
for r in m.reactions:
    if not r.boundary:
        if r.lower_bound > 0: r.lower_bound = 0
        if r.upper_bound < 0: r.upper_bound = 0
task = next(t for t in import_raven_tasks(T / "metabolicTasks_VerifyModel.txt", m, mapping=T / "human_gem_names.json").suite.tasks if t.id == tid)
with m:
    for r in m.boundary: r.bounds = (0.0, 0.0)
    added = []
    for rid, (mid, coef, pair) in task.exchange_bounds().items():
        r = Reaction(rid, lower_bound=pair[0], upper_bound=pair[1]); r.add_metabolites({m.metabolites.get_by_id(mid): coef}); added.append(r)
    for s in task.temporary_reactions:
        r = Reaction(str(s["id"]), lower_bound=float(s["lower_bound"]), upper_bound=float(s["upper_bound"]))
        r.add_metabolites({m.metabolites.get_by_id(k): v for k, v in s["stoichiometry"].items()}); added.append(r)
    m.add_reactions(added)
    for rid, pair in task.reaction_bounds().items(): m.reactions.get_by_id(rid).bounds = pair
    sol = pfba(m)
    rows = []
    for rid, v in sorted(sol.fluxes.items(), key=lambda kv: -abs(kv[1])):
        if abs(v) < 1e-7: continue
        r = m.reactions.get_by_id(rid)
        temp = rid.startswith("TASK_") or rid in {a.id for a in added}
        bal = None if temp else r.check_mass_balance()
        in_ref = (not temp) and rid in ref.reactions
        same = None
        if in_ref:
            rr = ref.reactions.get_by_id(rid)
            same = {x.id: c for x, c in r.metabolites.items()} == {x.id: c for x, c in rr.metabolites.items()} and r.bounds == rr.bounds
        rows.append({"id": rid, "flux": v, "equation": r.reaction, "names": r.build_reaction_string(use_metabolite_names=True),
                     "temporary": temp, "mass_charge_imbalance": {k: float(x) for k, x in (bal or {}).items()},
                     "in_reference_model": in_ref, "identical_to_reference": same, "subsystem": r.subsystem, "bounds": list(r.bounds)})
json.dump({"model": mp, "reference": refp, "task": tid, "description": task.description, "n_active": len(rows), "reactions": rows}, open(out, "w"), indent=1)
print(len(rows), "active reactions")
