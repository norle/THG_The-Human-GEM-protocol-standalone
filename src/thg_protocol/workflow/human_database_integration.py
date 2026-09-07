"""Reusable Human Database merge stage for reference construction."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from thg_protocol.io.models import load_model, save_json
from thg_protocol.merge import (
    MergePlan,
    MergePolicy,
    apply_merge_plan,
    generate_merge_plan,
)
from thg_protocol.runtime.stage import (
    StageContext,
    StageResult,
    dependency_path,
    dump_json,
)


class HumanDatabaseIntegrationStage:
    implementation_version = 1

    def __init__(self, stage_id: str, dependencies: tuple[str, ...]) -> None:
        self.id, self.dependencies = stage_id, dependencies
        self.output_role = (
            "model" if stage_id == "integrate-human-database" else "artifact"
        )
        self.kind = "mutation" if self.output_role == "model" else "analysis"

    def enabled(self, config: Any) -> bool:
        return "human_database" in config.sections

    def fingerprint_data(self, context: StageContext) -> Mapping[str, object]:
        return {
            "stage": self.id,
            "version": self.implementation_version,
            "config": context.config.sections.get("reference", {}),
            "dependencies": list(self.dependencies),
        }

    def run(self, context: StageContext, work_dir: Path) -> StageResult:
        settings = context.config.sections.get("reference", {})
        policy_data = (
            settings.get("human_database_integration", {})
            if isinstance(settings, Mapping)
            else {}
        )
        policy = MergePolicy(
            **(
                {
                    key: value
                    for key, value in policy_data.items()
                    if key != "remove_isolated_metabolites"
                }
                if isinstance(policy_data, Mapping)
                else {}
            )
        )
        base = load_model(dependency_path(context, "export-beta2", "model"))
        incoming = load_model(
            dependency_path(context, "human-database-reconstruct", "model")
        )
        if self.id == "plan-human-database-integration":
            plan = generate_merge_plan(base, incoming, policy=policy)
            return StageResult(
                (
                    (
                        "merge-plan",
                        dump_json(work_dir / "merge-plan.json", plan.to_dict()),
                    ),
                ),
                {"decisions": len(plan.decisions)},
            )
        plan = MergePlan.from_dict(
            json.loads(
                dependency_path(
                    context, "plan-human-database-integration", "merge-plan"
                ).read_text()
            )
        )
        merged, report = apply_merge_plan(base, incoming, plan)
        report_data = dict(report.__dict__)
        if isinstance(policy_data, Mapping) and policy_data.get(
            "remove_isolated_metabolites"
        ):
            isolated = [item for item in merged.metabolites if not item.reactions]
            merged.remove_metabolites(isolated)
            report_data["removed_isolated_metabolites"] = len(isolated)
        model = work_dir / "integrated-reference.json"
        save_json(merged, model)
        return StageResult(
            (
                ("model", model),
                (
                    "merge-report",
                    dump_json(work_dir / "merge-report.json", report_data),
                ),
                ("merge-plan", dump_json(work_dir / "merge-plan.json", plan.to_dict())),
            ),
            report_data,
        )

    def validate(self, result: StageResult) -> None:
        if not result.outputs or any(not path.is_file() for _, path in result.outputs):
            raise ValueError(f"stage '{self.id}' did not produce complete artifacts")
