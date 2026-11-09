"""Compare task-21 construction, solve order and native thread configuration.

python publication/scripts/measure_task_numerics.py
Full VerifyModel sequences are recorded as stage evidence, not a final-model gate.
"""

import gc
import hashlib
import json
import os
import subprocess
import time
from pathlib import Path

from thg_protocol.raven_tasks import import_raven_tasks
from thg_protocol.tasks import _run_on, run_task, run_task_suite

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
    cobra.Configuration().processes = 1
    tasks = ROOT / "files/metabolic_tasks/metabolicTasks_VerifyModel.txt"
    mapping = ROOT / "files/metabolic_tasks/human_gem_names.json"
    report = {
        "protocol_version": 2,
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
        "complete": False,
        "planned_experiments": len(CASES) * 6,
        "task_sha256": hashlib.sha256(tasks.read_bytes()).hexdigest(),
        "mapping_sha256": hashlib.sha256(mapping.read_bytes()).hexdigest(),
        "scope": "Cold task 21 versus sequential VerifyModel; previous publication "
        "thread recipe is a labelled control, not a pinned benchmark condition",
    }
    out = ROOT / "publication/ws2/task_numerics.json"
    out.write_text(json.dumps(report, indent=2) + "\n")
    modes = (
        ("gurobi", settings["solver"]["threads"], "native-default"),
        ("gurobi", 0, "previous-publication-attribute"),
        ("glpk", None, "not-applicable"),
    )
    for label, relative in CASES.items():
        path = ROOT / relative
        checksum = hashlib.sha256(path.read_bytes()).hexdigest()
        for solver, threads, application in modes:
            if solver == "gurobi":
                gurobipy.setParam("Threads", threads)
            cobra.Configuration().solver = solver
            model = cobra.io.load_json_model(str(path))
            if application == "previous-publication-attribute":
                # Reenact the old recipe; diagnostics must reveal its native default.
                model.solver.configuration.threads = settings["solver"]["threads"]
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
            assert len(selected) == 1 and len(suite.tasks) == 21
            assert all(not task.expected and not task.problems for task in suite.tasks)
            before = snapshot(model)
            methods = []
            if application == "native-default":
                methods.append(("direct", "cold-task21", _run_on))
            if application != "previous-publication-attribute":
                methods.append(("COBRA-copy", "cold-task21", run_task))
            methods.append(("COBRA-copy", "sequential-VerifyModel", run_task_suite))
            for construction, sequence, evaluate in methods:
                suite_report = None
                if sequence == "sequential-VerifyModel":
                    suite_report = evaluate(model, suite)
                    results = suite_report["tasks"]
                    result = next(task for task in results if task["id"] == "21")
                else:
                    result = evaluate(model, selected[0])
                    results = [result]
                assert snapshot(model) == before, "Task changed the source model"
                report["cases"].append(
                    {
                        "model": label,
                        "path": relative,
                        "sha256": checksum,
                        "solver": solver,
                        "construction": construction,
                        "sequence": sequence,
                        "thread_application": application,
                        "native_default_threads": threads,
                        "result": result,
                        "suite_report": suite_report,
                    }
                )
                if label == "current-beta1" and any(
                    task["actual_outcome"] == "success" for task in results
                ):
                    report["needs_current_model_investigation"] = True
                report["runtime_seconds"] = time.monotonic() - started
                out.write_text(json.dumps(report, indent=2) + "\n")
                print(
                    label,
                    solver,
                    application,
                    construction,
                    sequence,
                    result["status"],
                    result["diagnostics"],
                    flush=True,
                )
                if report["needs_current_model_investigation"]:
                    return
            del model
            gc.collect()
    assert len(report["cases"]) == report["planned_experiments"]
    report["complete"] = True
    report["runtime_seconds"] = time.monotonic() - started
    out.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
