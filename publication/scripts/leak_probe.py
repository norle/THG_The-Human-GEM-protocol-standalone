"""Probe VerifyModel task feasibility with reactions blocked. Usage: leak_probe.py MODEL RXN[,RXN...]  (empty = none)"""
import os
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "2")
import sys
from pathlib import Path
import cobra
from thg_protocol.raven_tasks import import_raven_tasks
from thg_protocol.tasks import run_task_suite
T = Path(__file__).resolve().parents[2] / "files/metabolic_tasks"
cobra.Configuration().solver = "gurobi"
m = cobra.io.read_sbml_model(sys.argv[1]); m.solver.configuration.threads = 2
for r in m.reactions:
    if not r.boundary:
        if r.lower_bound > 0: r.lower_bound = 0
        if r.upper_bound < 0: r.upper_bound = 0
for rid in filter(None, sys.argv[2].split(",")):
    m.reactions.get_by_id(rid).bounds = (0, 0)
rep = run_task_suite(m, import_raven_tasks(T / "metabolicTasks_VerifyModel.txt", m, mapping=T / "human_gem_names.json").suite)
print(rep["counts"], [t["id"] for t in rep["tasks"] if t["status"] != "passed"])
