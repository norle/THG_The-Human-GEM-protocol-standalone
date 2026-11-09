"""Run Human-GEM RAVEN task tables on a model with the stored name mapping.

Usage: run_tasks.py MODEL LABEL OUTDIR [TABLE ...]
Optional env THG_BLOCK=RXN,RXN sets those reactions to [0,0] in memory (patch test).
Settings (benchmark protocol): closed medium, Gurobi, forced non-boundary
fluxes (LB>0 or UB<0) relaxed to 0, stored Human-GEM name mapping.
THG_SOLVER=glpk selects a separately recorded corroboration run.
"""

import csv
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

# Set BLAS limits before importing COBRA and NumPy.
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "2")

import cobra  # noqa: E402

from thg_protocol.raven_tasks import import_raven_tasks  # noqa: E402
from thg_protocol.tasks import (  # noqa: E402
    RESIDUAL_RELIABILITY_THRESHOLD,
    run_task_suite,
)

ROOT = Path(__file__).resolve().parents[2]
TASKS = ROOT / "files/metabolic_tasks"
MAPPING = TASKS / "human_gem_names.json"
TABLES = {
    "VerifyModel": "metabolicTasks_VerifyModel.txt",
    "Essential": "metabolicTasks_Essential.txt",
    "Full": "metabolicTasks_Full.txt",
}


def main():
    model_path, label, outdir = sys.argv[1:4]
    which = sys.argv[4:] or list(TABLES)
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    settings = json.loads((ROOT / "publication/benchmark_settings.json").read_text())
    if (
        settings["tasks"]["residual_reliability_threshold"]
        != RESIDUAL_RELIABILITY_THRESHOLD
    ):
        raise ValueError(
            "Task runner reliability threshold differs from pinned settings"
        )
    for filename, expected in settings["tasks"]["sha256"].items():
        if hashlib.sha256((TASKS / filename).read_bytes()).hexdigest() != expected:
            raise ValueError(f"Task table checksum differs: {filename}")
    if (
        hashlib.sha256(MAPPING.read_bytes()).hexdigest()
        != settings["tasks"]["mapping_sha256"]
    ):
        raise ValueError("Task mapping checksum differs")
    solver = os.environ.get("THG_SOLVER", settings["solver"]["name"])
    if solver == "gurobi":
        import gurobipy

        # COBRA copies discard native parameters; new LP copies inherit this default.
        gurobipy.setParam("Threads", settings["solver"]["threads"])
    cobra.Configuration().solver = solver
    cobra.Configuration().processes = 1
    model = (
        cobra.io.load_json_model(model_path)
        if model_path.endswith(".json")
        else cobra.io.read_sbml_model(model_path)
    )
    for key, value in settings["solver"]["tolerances"].items():
        if key in dir(model.solver.configuration.tolerances):
            setattr(model.solver.configuration.tolerances, key, value)
    relaxed = 0
    for r in model.reactions:
        if r.boundary:
            continue
        if r.lower_bound > 0:
            r.lower_bound = 0
            relaxed += 1
        if r.upper_bound < 0:
            r.upper_bound = 0
            relaxed += 1
    for rid in filter(None, os.environ.get("THG_BLOCK", "").split(",")):
        model.reactions.get_by_id(rid).bounds = (0, 0)
    commit = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True
    ).stdout.strip()
    rows = []
    reports = {}
    # VerifyModel must resolve before functional tasks are interpreted.
    if "VerifyModel" in which:
        which = ["VerifyModel"] + [name for name in which if name != "VerifyModel"]
    for name in which:
        imp = import_raven_tasks(TASKS / TABLES[name], model, mapping=MAPPING)
        rep = run_task_suite(model, imp.suite)
        reports[name] = rep
        for t in rep["tasks"]:
            d = t.get("diagnostics") or {}
            cause = ""
            if t["status"] == "invalid":
                cause = "; ".join(map(str, d.get("problems", [])))[:300]
            elif t["status"] == "error":
                cause = str(d)[:300]
            rows.append(
                {
                    "model": label,
                    "table": name,
                    "task_id": t["id"],
                    "description": next(
                        (x.description for x in imp.suite.tasks if x.id == t["id"]), ""
                    ),
                    "expected": t["expected_outcome"],
                    "actual": t["actual_outcome"],
                    "status": t["status"],
                    "solver_status": t["solver_status"],
                    "solver_interface": d.get("solver_interface"),
                    "solver_threads": d.get("solver_threads"),
                    "cause": cause,
                    "max_bound_violation": d.get("max_bound_violation"),
                    "max_constraint_violation": d.get("max_constraint_violation"),
                    "numerical_reliability": d.get(
                        "numerical_reliability", "unavailable"
                    ),
                }
            )
        print(label, name, rep["counts"], flush=True)
        if name == "VerifyModel" and not rep["passed"]:
            print(
                "VerifyModel gate unresolved or failed; functional tables skipped",
                flush=True,
            )
            break
    with open(out / f"task_results_{label}.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    provenance = {
        "model": str(Path(model_path).resolve()),
        "model_sha256": hashlib.sha256(Path(model_path).read_bytes()).hexdigest(),
        "code_commit": commit,
        "code_diff_sha256": hashlib.sha256(
            subprocess.run(
                ["git", "-C", str(ROOT), "diff", "HEAD"], capture_output=True
            ).stdout
        ).hexdigest(),
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "settings": settings,
        "solver": solver,
        "cobra_version": cobra.__version__,
        "blocked_reactions": list(
            filter(None, os.environ.get("THG_BLOCK", "").split(","))
        ),
        "relaxed_forced_bounds": relaxed,
        "runtime_seconds": time.monotonic() - started,
        "reports": reports,
    }
    (out / f"task_results_{label}.json").write_text(
        json.dumps(provenance, indent=2) + "\n"
    )
    print("relaxed forced bounds:", relaxed, "commit", commit)


if __name__ == "__main__":
    main()
