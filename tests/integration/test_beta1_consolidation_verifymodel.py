"""Regression: β1 metabolite consolidation must not open VerifyModel leaks.

Merging Human-GEM lipid pools that share a generic ChEBI class let flux enter a
pool through one composition reaction and leave through another, which made
VerifyModel tasks 10, 11, 17 and 21 feasible on Human2 (see
docs/plans/publication-plan.md, "Known issue: β1 metabolite consolidation").
"""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2]
HUMAN2 = ROOT / "inputs" / "models" / "Human2.xml"
VERIFY = ROOT / "files" / "metabolic_tasks" / "metabolicTasks_VerifyModel.txt"

pytestmark = [
    pytest.mark.slow,
    pytest.mark.solver,
    pytest.mark.skipif(
        not HUMAN2.is_file(), reason="Human2.xml is a gitignored caller-owned input"
    ),
]


def _verify_failures(model) -> list[str]:
    from thg_protocol.raven_tasks import import_raven_tasks
    from thg_protocol.tasks import run_tasks

    for reaction in model.reactions:
        if not reaction.boundary:
            reaction.lower_bound = min(reaction.lower_bound, 0.0)
            reaction.upper_bound = max(reaction.upper_bound, 0.0)
    suite = import_raven_tasks(VERIFY, model).suite
    report = run_tasks(model, suite.tasks)
    assert report["counts"]["invalid"] == 0
    return [task["id"] for task in report["tasks"] if not task["passed"]]


def test_consolidating_human2_keeps_every_verifymodel_task_infeasible():
    from thg_protocol.curation.beta1 import consolidate_model
    from thg_protocol.io.models import load_model

    model = load_model(HUMAN2)
    consolidated, report = consolidate_model(model)
    merged_pools = [
        identifier
        for identifier in report["removed_metabolites"]
        if "R" in (model.metabolites.get_by_id(identifier).formula or "")
    ]
    assert merged_pools == []
    assert _verify_failures(consolidated) == []
