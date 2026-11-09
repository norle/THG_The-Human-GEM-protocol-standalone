"""Compare task-21 LP construction on real WS1 models, with residual diagnostics.

python publication/scripts/measure_task_numerics.py
Task 21 alone is a numerical case study, not the full VerifyModel gate.
"""

import gc
import hashlib
import json
import os
import subprocess
import time
from pathlib import Path

from thg_protocol.raven_tasks import import_raven_tasks
from thg_protocol.tasks import _run_on, run_task

ROOT = Path(__file__).resolve().parents[2]
CASES = {
    "current-beta1": "runs/thg-ws1-a/artifacts/export-beta1/attempt-0002/"
    "thg-beta1-candidate.json",
    "archived-beta2": "runs/thg-ws1-a/artifacts/export-beta2/attempt-0002/"
    "thg-beta2-candidate.json",
}


def snapshot(model):
    return (
        [(reaction.id, reaction.bounds) for reaction in model.reactions],
        [metabolite.id for metabolite in model.metabolites],
        str(model.objective.expression),
        model.objective_direction,
    )


def main():
    for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
        os.environ.setdefault(name, "2")
    import cobra
    import gurobipy

    started = time.monotonic()
    settings = json.loads((ROOT / "publication/benchmark_settings.json").read_text())
    gurobipy.setParam("Threads", settings["solver"]["threads"])
    cobra.Configuration().processes = 1
    tasks = ROOT / "files/metabolic_tasks/metabolicTasks_VerifyModel.txt"
    mapping = ROOT / "files/metabolic_tasks/human_gem_names.json"
    report = {
        "command": "python publication/scripts/measure_task_numerics.py",
        "code_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "task_runner_sha256": hashlib.sha256(
            (ROOT / "src/thg_protocol/tasks.py").read_bytes()
        ).hexdigest(),
        "settings": settings,
        "cases": [],
        "needs_current_model_investigation": False,
        "task_sha256": hashlib.sha256(tasks.read_bytes()).hexdigest(),
        "mapping_sha256": hashlib.sha256(mapping.read_bytes()).hexdigest(),
        "scope": "Task 21 only; LP construction comparison; "
        "no chemistry or bounds curated",
    }
    out = ROOT / "publication/ws2/task_numerics.json"
    for label, relative in CASES.items():
        path = ROOT / relative
        checksum = hashlib.sha256(path.read_bytes()).hexdigest()
        for solver in ("gurobi", "glpk"):
            cobra.Configuration().solver = solver
            model = cobra.io.load_json_model(str(path))
            for key, value in settings["solver"]["tolerances"].items():
                if key in dir(model.solver.configuration.tolerances):
                    setattr(model.solver.configuration.tolerances, key, value)
            for reaction in model.reactions:
                if not reaction.boundary:
                    reaction.bounds = (
                        min(reaction.lower_bound, 0),
                        max(reaction.upper_bound, 0),
                    )
            suite = import_raven_tasks(tasks, model, mapping=mapping).suite
            selected = [task for task in suite.tasks if task.id == "21"]
            assert len(selected) == 1 and not selected[0].expected
            assert not selected[0].problems, selected[0].problems
            before = snapshot(model)
            methods = (
                (("direct", _run_on), ("LP-copy", run_task))
                if solver == "gurobi"
                else (("LP-copy", run_task),)
            )
            for construction, evaluate in methods:
                result = evaluate(model, selected[0])
                assert snapshot(model) == before, "Task changed the source model"
                report["cases"].append(
                    {
                        "model": label,
                        "path": relative,
                        "sha256": checksum,
                        "solver": solver,
                        "construction": construction,
                        "result": result,
                    }
                )
                if label == "current-beta1" and result["actual_outcome"] == "success":
                    report["needs_current_model_investigation"] = True
                report["runtime_seconds"] = time.monotonic() - started
                out.write_text(json.dumps(report, indent=2) + "\n")
                print(
                    label,
                    solver,
                    construction,
                    result["status"],
                    result["diagnostics"],
                    flush=True,
                )
                if report["needs_current_model_investigation"]:
                    return
            del model
            gc.collect()


if __name__ == "__main__":
    main()
