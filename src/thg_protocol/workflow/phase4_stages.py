"""Executable offline Phase 4 workflow stages."""

from __future__ import annotations

import json
import shutil
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .hashing import sha256_file
from .stages import StageContext, StageResult, _dependency_path, _load_cobra_model


class HumanDatabaseStage:
    implementation_version = 1

    def __init__(self, stage_id: str, dependencies: tuple[str, ...] = ()) -> None:
        self.id, self.dependencies = stage_id, dependencies
        self.output_role = "model" if stage_id.endswith("reconstruct") else "artifact"
        self.kind = "mutation" if stage_id.endswith("reconstruct") else "collection"

    def enabled(self, config: Any) -> bool:
        del config
        return True

    def fingerprint_data(self, context: StageContext) -> Mapping[str, object]:
        section = context.config.sections.get("human_database", {})
        return {
            "stage": self.id,
            "version": self.implementation_version,
            "config": dict(section) if isinstance(section, Mapping) else {},
        }

    def run(self, context: StageContext, work_dir: Path) -> StageResult:
        section = context.config.sections.get("human_database", {})
        if not isinstance(section, Mapping):
            raise ValueError("human_database section is required")
        records = Path(str(section["records"]))
        if self.id == "human-database-source":
            copied = work_dir / "normalized-records.json"
            shutil.copy2(records, copied)
            manifest = work_dir / "source-manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "mode": section.get("mode", "offline"),
                        "input_sha256": sha256_file(records),
                        "source_release": section.get(
                            "source_release", "offline-snapshot"
                        ),
                    },
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
            return StageResult(
                (("records", copied), ("provenance", manifest)),
                {"mode": section.get("mode", "offline")},
            )
        if self.id == "human-database-reconstruct":
            from thg_protocol.database_workflow import (
                normalize_records,
                reconstruct_snapshot,
            )

            payload = json.loads(
                _dependency_path(context, "human-database-source", "records").read_text(
                    encoding="utf-8"
                )
            )
            normalized = normalize_records(payload)
            output = work_dir / "human-database-candidate.json"
            reconstruct_snapshot(
                str(section.get("model_id", "human-database")),
                normalized,
                output_path=output,
            )
            report = work_dir / "reconstruction-report.json"
            report.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "record_checksum": __import__(
                            "thg_protocol.database_workflow",
                            fromlist=["records_checksum"],
                        ).records_checksum(normalized),
                        "counts": {
                            "metabolites": len(normalized.metabolites),
                            "reactions": len(normalized.reactions),
                            "genes": len(normalized.genes),
                        },
                    },
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
            return StageResult(
                (("model", output), ("report", report)),
                {"reactions": len(normalized.reactions)},
            )
        model = _load_cobra_model(
            _dependency_path(context, "human-database-reconstruct", "model")
        )
        validation = {
            "model_id": str(model.id),
            "unique_metabolites": len({item.id for item in model.metabolites})
            == len(model.metabolites),
            "unique_reactions": len({item.id for item in model.reactions})
            == len(model.reactions),
            "counts": {
                "metabolites": len(model.metabolites),
                "reactions": len(model.reactions),
            },
        }
        output = work_dir / "human-database-validation.json"
        output.write_text(
            json.dumps(validation, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        return StageResult((("validation", output),), validation)

    def validate(self, result: StageResult) -> None:
        if not result.outputs or any(not path.is_file() for _, path in result.outputs):
            raise ValueError(f"stage '{self.id}' did not produce complete artifacts")


class FinalTHGStage:
    implementation_version = 1

    def __init__(self, stage_id: str, dependencies: tuple[str, ...] = ()) -> None:
        self.id, self.dependencies = stage_id, dependencies
        self.output_role = "model" if stage_id.endswith("export") else "artifact"
        self.kind = "mutation" if stage_id.endswith("apply") else "analysis"

    def enabled(self, config: Any) -> bool:
        del config
        return True

    def fingerprint_data(self, context: StageContext) -> Mapping[str, object]:
        section = context.config.sections.get("final_thg", {})
        return {
            "stage": self.id,
            "version": self.implementation_version,
            "config": dict(section) if isinstance(section, Mapping) else {},
        }

    def run(self, context: StageContext, work_dir: Path) -> StageResult:
        section = context.config.sections.get("final_thg", {})
        if not isinstance(section, Mapping):
            raise ValueError("final_thg section is required")
        if self.id == "final-thg-load":
            paths = [
                Path(str(section[key])) for key in ("beta2_model", "database_model")
            ]
            for path in paths:
                if not path.is_file():
                    raise FileNotFoundError(path)
            copied = []
            for name, path in (("beta2", paths[0]), ("database", paths[1])):
                destination = work_dir / f"{name}{path.suffix.lower()}"
                shutil.copy2(path, destination)
                copied.append((name, destination))
            return StageResult(tuple(copied), {"inputs": [str(path) for path in paths]})
        from thg_protocol.merge import MergePolicy, generate_merge_plan

        policy = MergePolicy(
            source_precedence=str(section.get("source_precedence", "base")),
            direction=str(section.get("direction", "strict")),
            proton_water=str(section.get("proton_water", "strict")),
            formula_charge=str(section.get("formula_charge", "report")),
            bounds=str(section.get("bounds", "report")),
            gpr=str(section.get("gpr", "report")),
        )

        left = _load_cobra_model(_dependency_path(context, "final-thg-load", "beta2"))
        right = _load_cobra_model(
            _dependency_path(context, "final-thg-load", "database")
        )
        plan = generate_merge_plan(left, right, policy=policy)
        output = work_dir / "merge-plan.json"
        output.write_text(
            json.dumps(plan.to_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        if self.id == "final-thg-plan":
            return StageResult(
                (("merge-plan", output),), {"decisions": len(plan.decisions)}
            )
        from thg_protocol.merge import apply_merge_plan

        merged, report = apply_merge_plan(left, right, plan)
        from thg_protocol.merge import bounded_repair, validate_merged_model

        merged, repair_report = bounded_repair(
            merged, max_iterations=int(section.get("max_repair_iterations", 0))
        )
        from thg_protocol.tasks import TaskSuite

        task_suite = TaskSuite("final-thg-empty", "1", ())
        if isinstance(section.get("task_suite"), str):
            from thg_protocol.tasks import load_task_suite

            task_suite = load_task_suite(str(section["task_suite"]))
        validation = validate_merged_model(
            merged,
            profile=str(section.get("validation_profile", "final-standard")),
            task_suite=task_suite,
        )
        model_path = work_dir / "final-thg-candidate.json"
        from cobra.io import save_json_model

        save_json_model(merged, str(model_path))
        output.write_text(
            json.dumps(
                {
                    "plan": plan.to_dict(),
                    "report": report.__dict__,
                    "repair": repair_report.__dict__,
                    "validation": validation,
                },
                indent=2,
                sort_keys=True,
                default=str,
            )
            + "\n",
            encoding="utf-8",
        )
        return StageResult(
            (("model", model_path), ("merge-plan", output)),
            {
                "decisions": len(plan.decisions),
                "reactions": len(merged.reactions),
                "repair_status": repair_report.status,
                "validation": validation,
            },
        )

    def validate(self, result: StageResult) -> None:
        if not result.outputs or any(not path.is_file() for _, path in result.outputs):
            raise ValueError(f"stage '{self.id}' did not produce complete artifacts")


def human_database_stages() -> tuple[HumanDatabaseStage, ...]:
    return (
        HumanDatabaseStage("human-database-source"),
        HumanDatabaseStage("human-database-reconstruct", ("human-database-source",)),
        HumanDatabaseStage("human-database-validate", ("human-database-reconstruct",)),
    )


def final_thg_stages() -> tuple[FinalTHGStage, ...]:
    return (
        FinalTHGStage("final-thg-load"),
        FinalTHGStage("final-thg-plan", ("final-thg-load",)),
        FinalTHGStage("final-thg-apply", ("final-thg-plan",)),
    )
