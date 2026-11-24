"""Hold coverage and costs fixed to isolate the exact MILP and tie-break."""

import ast
import hashlib
import json
import subprocess
from collections.abc import Mapping
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from optlang import gurobi_interface

from thg_protocol.gapfill.ptr import (
    _RANK,
    ComponentCoverage,
    Selection,
    candidate_costs,
    select_unblockers,
)
from thg_protocol.runtime.stage import StageContext, dependency_path
from thg_protocol.workflow.config import load_workflow_config
from thg_protocol.workflow.gapfill import _coverage_lines, _ptr_candidates

RUN = Path("runs/thg-ws1-b")
CONFIG = Path("publication/ws1/reference-b-frozen.json")
OLD = "b731a2b10015e7fd72c56c6e548a3c43f14b232b^"
OUT = Path("publication/ws1/gapfill-change/selection_ablation.json")


def main():
    ctx = StageContext(
        load_workflow_config(CONFIG),
        RUN,
        json.loads((RUN / "manifest.json").read_text()),
    )
    coverage_path = dependency_path(ctx, "compute-gapfill-coverage", "coverage")
    candidate_path = dependency_path(ctx, "generate-gapfill-candidates", "candidates")
    plan_path = dependency_path(ctx, "generate-gapfill-plan", "plan")
    _, lines = _coverage_lines(coverage_path)
    coverage = [ComponentCoverage.from_dict(row) for row in lines]
    candidates = _ptr_candidates(ctx)
    records = [json.loads(line) for line in plan_path.read_text().splitlines()]
    header = records[0]
    params = header["parameters"]
    report_path = dependency_path(ctx, "generate-gapfill-plan", "report")
    report = json.loads(report_path.read_text())
    settings = {
        "tradeoff_lambda": params["tradeoff_lambda"],
        "budget": report["solver"]["budget"],
        "costs": candidate_costs(candidates, params["connection_costs"]),
    }
    source = subprocess.check_output(
        ["git", "show", f"{OLD}:src/thg_protocol/gapfill/ptr.py"], text=True
    )
    implementation = next(
        node
        for node in ast.parse(source).body
        if isinstance(node, ast.FunctionDef) and node.name == "select_unblockers"
    )
    namespace = {
        "Selection": Selection,
        "Mapping": Mapping,
        "Any": Any,
        "ComponentCoverage": ComponentCoverage,
    }
    exec(
        compile(
            ast.Module(body=[implementation], type_ignores=[]), f"{OLD}:ptr.py", "exec"
        ),
        namespace,
    )
    old_select = namespace["select_unblockers"]

    def exact_model():
        model = gurobi_interface.Model()
        model.problem.Params.MIPGap = 0
        return model

    exact_interface = SimpleNamespace(
        Model=exact_model,
        Variable=gurobi_interface.Variable,
        Constraint=gurobi_interface.Constraint,
        Objective=gurobi_interface.Objective,
    )
    results = {
        "default_gap_no_tie_break": old_select(
            coverage, interface=gurobi_interface, **settings
        ),
        "exact_gap_no_tie_break": old_select(
            coverage, interface=exact_interface, **settings
        ),
        "exact_gap_with_tie_break": select_unblockers(
            coverage,
            interface=gurobi_interface,
            **settings,
            ranks={item.reaction_id: _RANK[item.type] for item in candidates},
        ),
    }
    expected = {row["reaction_id"] for row in records[1:] if row.get("phase") == 3}
    assert all(item.solver["milp_status"] == "optimal" for item in results.values())
    assert set(results["exact_gap_with_tie_break"].selected) == expected
    labels = list(results)
    paired = {
        f"{left}_vs_{right}": {
            "selected_only_in_first": len(
                set(results[left].selected) - set(results[right].selected)
            ),
            "selected_only_in_second": len(
                set(results[right].selected) - set(results[left].selected)
            ),
            "same_covered_targets": set(results[left].covered)
            == set(results[right].covered),
        }
        for left, right in zip(labels[:-1], labels[1:], strict=True)
    }
    output = {
        "old_selection_source": OLD,
        "sources": {
            str(path): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (coverage_path, candidate_path, plan_path, report_path)
        },
        "settings": {
            "budget": settings["budget"],
            "tradeoff_lambda": settings["tradeoff_lambda"],
        },
        "variants": {
            name: {
                "number_selected": len(item.selected),
                "number_covered": len(item.covered),
                "selected": item.selected,
                "solver": item.solver,
            }
            for name, item in results.items()
        },
        "paired": paired,
    }
    OUT.write_text(json.dumps(output, indent=2) + "\n")


if __name__ == "__main__":
    main()
