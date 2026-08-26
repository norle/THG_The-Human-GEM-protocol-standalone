"""Executable offline Phase 4 workflow stages."""

from __future__ import annotations

import json
import shutil
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .artifacts import upstream_fingerprint
from .hashing import sha256_file
from .stages import (
    StageContext,
    StageResult,
    _dependency_path,
    _dump,
    _load_cobra_model,
)


def _copy_input(source: Path, destination: Path) -> Path:
    shutil.copy2(source, destination)
    return destination


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
        result: dict[str, object] = {
            "stage": self.id,
            "version": self.implementation_version,
            "config": dict(section) if isinstance(section, Mapping) else {},
            "dependencies": {
                dependency: [
                    str(output.get("sha256"))
                    for output in context.manifest.get("steps", {})
                    .get(dependency, {})
                    .get("outputs", [])
                    if isinstance(output, Mapping)
                ]
                for dependency in self.dependencies
            },
        }
        if isinstance(section, Mapping):
            records = section.get("records")
            result["records_sha256"] = (
                sha256_file(records)
                if isinstance(records, str) and Path(records).is_file()
                else None
            )
        return result

    def run(self, context: StageContext, work_dir: Path) -> StageResult:
        if self.id in {
            "collect-records",
            "snapshot-records",
            "normalize-records",
            "human-database-reconstruct",
            "human-database-validate",
            "human-database-export",
        }:
            return self._run_first_class(context, work_dir)
        section = context.config.sections.get("human_database", {})
        if not isinstance(section, Mapping):
            raise ValueError("human_database section is required")
        if str(section.get("mode", "offline")) == "live":
            raise ValueError(
                "registered Human Database live mode requires an injected source "
                "adapter; use harvest_snapshot() with the adapter"
            )
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

    def _run_first_class(self, context: StageContext, work_dir: Path) -> StageResult:
        section = context.config.sections["human_database"]
        records = Path(str(section["records"]))
        if self.id == "collect-records":
            if section.get("mode", "offline") == "live":
                raise ValueError(
                    "registered Human Database live mode requires an injected "
                    "source adapter"
                )
            output = _copy_input(records, work_dir / "collected-records.json")
            manifest = _dump(
                work_dir / "collection-provenance.json",
                {
                    "mode": section.get("mode", "offline"),
                    "source_release": section.get("source_release", "offline-snapshot"),
                    "source_checksum": sha256_file(records),
                    "network_stage": section.get("mode") == "live",
                },
            )
            return StageResult((("records", output), ("provenance", manifest)), {})
        if self.id == "snapshot-records":
            source = _dependency_path(context, "collect-records", "records")
            output = _copy_input(source, work_dir / "records-snapshot.json")
            return StageResult(
                (
                    ("snapshot", output),
                    (
                        "provenance",
                        _dump(
                            work_dir / "snapshot-provenance.json",
                            {"checksum": sha256_file(source), "network": False},
                        ),
                    ),
                ),
                {},
            )
        if self.id == "normalize-records":
            from thg_protocol.database_workflow import (
                normalize_records,
                records_checksum,
            )

            payload = json.loads(
                _dependency_path(context, "snapshot-records", "snapshot").read_text()
            )
            normalized = normalize_records(payload)
            return StageResult(
                (
                    (
                        "records",
                        _dump(
                            work_dir / "normalized-records.json", normalized.to_dict()
                        ),
                    ),
                ),
                {"checksum": records_checksum(normalized)},
            )
        if self.id == "human-database-reconstruct":
            from thg_protocol.database_workflow import (
                normalize_records,
                reconstruct_snapshot,
            )

            payload = json.loads(
                _dependency_path(context, "normalize-records", "records").read_text()
            )
            model_path = work_dir / "human-database-model.json"
            reconstruct_snapshot(
                str(section.get("model_id", "human-database")),
                normalize_records(payload),
                output_path=model_path,
            )
            return StageResult(
                (("model", model_path),),
                {"model_id": str(section.get("model_id", "human-database"))},
            )
        if self.id == "human-database-validate":
            model = _load_cobra_model(
                _dependency_path(context, "human-database-reconstruct", "model")
            )
            from thg_protocol.validation import validate_model

            report = validate_model(model, "structural-fast")
            return StageResult(
                (("validation", _dump(work_dir / "validation-report.json", report)),),
                report,
            )
        model = _load_cobra_model(
            _dependency_path(context, "human-database-reconstruct", "model")
        )
        from cobra.io import save_json_model, write_sbml_model

        json_model = work_dir / "human-database-model.json"
        xml_model = work_dir / "human-database-model.xml"
        save_json_model(model, str(json_model))
        write_sbml_model(model, str(xml_model))
        validation = _copy_input(
            _dependency_path(context, "human-database-validate", "validation"),
            work_dir / "validation-report.json",
        )
        provenance = _dump(
            work_dir / "provenance.json",
            {
                "source_checksum": sha256_file(records),
                "mode": section.get("mode", "offline"),
                "network_only_in_collection": True,
                "software": "thg_protocol",
            },
        )
        return StageResult(
            (
                ("model", json_model),
                ("sbml", xml_model),
                ("validation", validation),
                ("provenance", provenance),
            ),
            {},
        )

    def validate(self, result: StageResult) -> None:
        if not result.outputs or any(not path.is_file() for _, path in result.outputs):
            raise ValueError(f"stage '{self.id}' did not produce complete artifacts")


class FinalTHGStage:
    implementation_version = 1

    def __init__(self, stage_id: str, dependencies: tuple[str, ...] = ()) -> None:
        self.id, self.dependencies = stage_id, dependencies
        self.output_role = (
            "model"
            if stage_id in {"final-thg-merge", "export-final-thg"}
            else "artifact"
        )
        self.kind = (
            "mutation"
            if stage_id == "final-thg-merge"
            else "analysis"
        )

    def enabled(self, config: Any) -> bool:
        del config
        return True

    def fingerprint_data(self, context: StageContext) -> Mapping[str, object]:
        section = context.config.sections.get("final_thg", {})
        result: dict[str, object] = {
            "stage": self.id,
            "version": self.implementation_version,
            "config": dict(section) if isinstance(section, Mapping) else {},
            "dependencies": {
                dependency: [
                    str(output.get("sha256"))
                    for output in context.manifest.get("steps", {})
                    .get(dependency, {})
                    .get("outputs", [])
                    if isinstance(output, Mapping)
                ]
                for dependency in self.dependencies
            },
        }
        if isinstance(section, Mapping):
            input_hashes: dict[str, object] = {}
            for path_key, upstream_key in (
                ("beta2_model", "beta2_upstream"),
                ("database_model", "database_upstream"),
            ):
                direct = section.get(path_key)
                if isinstance(direct, str):
                    input_hashes[path_key] = (
                        sha256_file(direct) if Path(direct).is_file() else None
                    )
                upstream = section.get(upstream_key)
                if isinstance(upstream, Mapping):
                    try:
                        input_hashes[upstream_key] = upstream_fingerprint(
                            [upstream],
                            base_dir=(
                                context.config.source_path.parent
                                if context.config.source_path is not None
                                else None
                            ),
                        )
                    except Exception as error:
                        # Keep the fingerprint calculable so the runner can
                        # execute the stage and persist the actionable failure.
                        input_hashes[upstream_key] = {
                            "error": f"{type(error).__name__}: {error}"
                        }
            if isinstance(section.get("reference_upstream"), Mapping):
                try:
                    input_hashes["reference_upstream"] = upstream_fingerprint(
                        [section["reference_upstream"]],
                        base_dir=(
                            context.config.source_path.parent
                            if context.config.source_path is not None
                            else None
                        ),
                    )
                except Exception as error:
                    input_hashes["reference_upstream"] = {
                        "error": f"{type(error).__name__}: {error}"
                    }
            task_suite = section.get("task_suite")
            if isinstance(task_suite, str):
                result["task_suite_sha256"] = (
                    sha256_file(task_suite) if Path(task_suite).is_file() else None
                )
            result["inputs"] = input_hashes
        return result

    def run(self, context: StageContext, work_dir: Path) -> StageResult:
        return self._run_first_class(context, work_dir)

    @staticmethod
    def _inputs(context: StageContext) -> tuple[Path, Path, list[dict[str, object]]]:
        from .artifacts import resolve_artifact

        section = context.config.sections["final_thg"]
        inputs = []
        for name, path_key, upstream_key in (
            ("beta2", "beta2_model", "beta2_upstream"),
            ("database", "database_model", "database_upstream"),
        ):
            reference = section.get(upstream_key)
            if name == "beta2" and isinstance(
                section.get("reference_upstream"), Mapping
            ):
                reference = section["reference_upstream"]
            if isinstance(reference, Mapping):
                resolved = resolve_artifact(
                    reference,
                    base_dir=(
                        context.config.source_path.parent
                        if context.config.source_path
                        else None
                    ),
                )
                if resolved.reference.role not in {"model", "sbml"}:
                    raise ValueError(f"{upstream_key} must reference a model artifact")
                path = resolved.path
                record = {
                    "name": name,
                    "path": str(path),
                    "sha256": sha256_file(path),
                    "upstream": resolved.reference.to_dict(),
                }
            else:
                path = Path(str(section.get(path_key, "")))
                if not path.is_file():
                    raise FileNotFoundError(path)
                record = {"name": name, "path": str(path), "sha256": sha256_file(path)}
            inputs.append((path, record))
        return inputs[0][0], inputs[1][0], [item[1] for item in inputs]

    def _run_first_class(self, context: StageContext, work_dir: Path) -> StageResult:
        import json

        section = context.config.sections["final_thg"]
        from thg_protocol.merge import (
            MergePlan,
            MergePolicy,
            apply_merge_plan,
            generate_merge_plan,
        )

        if self.id == "final-thg-merge-plan":
            left_path, right_path, inputs = self._inputs(context)
            left, right = _load_cobra_model(left_path), _load_cobra_model(right_path)
            policy = MergePolicy(
                source_precedence=str(section.get("source_precedence", "base")),
                direction=str(section.get("direction", "strict")),
                proton_water=str(section.get("proton_water", "strict")),
                formula_charge=str(section.get("formula_charge", "report")),
                bounds=str(section.get("bounds", "report")),
                gpr=str(section.get("gpr", "report")),
            )
            plan = generate_merge_plan(left, right, policy=policy)
            return StageResult(
                (
                    ("merge-plan", _dump(work_dir / "merge-plan.json", plan.to_dict())),
                    (
                        "beta2",
                        _copy_input(left_path, work_dir / f"beta2{left_path.suffix}"),
                    ),
                    (
                        "database",
                        _copy_input(
                            right_path, work_dir / f"database{right_path.suffix}"
                        ),
                    ),
                    (
                        "provenance",
                        _dump(work_dir / "input-provenance.json", {"inputs": inputs}),
                    ),
                ),
                {"decisions": len(plan.decisions)},
            )
        if self.id == "final-thg-merge":
            plan = MergePlan.from_dict(
                json.loads(
                    _dependency_path(
                        context, "final-thg-merge-plan", "merge-plan"
                    ).read_text()
                )
            )
            left = _load_cobra_model(
                _dependency_path(context, "final-thg-merge-plan", "beta2")
            )
            right = _load_cobra_model(
                _dependency_path(context, "final-thg-merge-plan", "database")
            )
            merged, report = apply_merge_plan(left, right, plan)
            from cobra.io import save_json_model

            model_path = work_dir / "merged-model.json"
            save_json_model(merged, str(model_path))
            return StageResult(
                (
                    ("model", model_path),
                    (
                        "merge-report",
                        _dump(work_dir / "merge-report.json", report.__dict__),
                    ),
                ),
                {"decisions": len(plan.decisions)},
            )
        if self.id == "validate-final-thg":
            model = _load_cobra_model(
                _dependency_path(context, "final-thg-merge", "model")
            )
            task_suite = None
            if isinstance(section.get("task_suite"), str):
                from thg_protocol.tasks import load_task_suite

                task_suite = load_task_suite(str(section["task_suite"]))
            from thg_protocol.merge import validate_merged_model

            report = validate_merged_model(
                model,
                profile=str(section.get("validation_profile", "final-standard")),
                task_suite=task_suite,
            )
            return StageResult(
                (("validation", _dump(work_dir / "validation-report.json", report)),),
                report,
            )
        model = _load_cobra_model(_dependency_path(context, "final-thg-merge", "model"))
        from cobra.io import save_json_model, write_sbml_model

        json_model, xml_model = (
            work_dir / "final-thg-model.json",
            work_dir / "final-thg-model.xml",
        )
        save_json_model(model, str(json_model))
        write_sbml_model(model, str(xml_model))
        validation = _copy_input(
            _dependency_path(context, "validate-final-thg", "validation"),
            work_dir / "validation-report.json",
        )
        provenance = _dump(
            work_dir / "provenance.json",
            {
                "workflow": "final-thg",
                "inputs": self._inputs(context)[2],
                "software": "thg_protocol",
            },
        )
        return StageResult(
            (
                ("model", json_model),
                ("sbml", xml_model),
                ("validation", validation),
                ("provenance", provenance),
            ),
            {},
        )

    def validate(self, result: StageResult) -> None:
        if not result.outputs or any(not path.is_file() for _, path in result.outputs):
            raise ValueError(f"stage '{self.id}' did not produce complete artifacts")
        if self.id == "validate-final-thg":
            report = result.summary
            validation = report.get("validation")
            tasks = report.get("tasks")
            if isinstance(validation, Mapping) and validation.get("passed") is False:
                raise ValueError("final THG model validation failed")
            if isinstance(tasks, Mapping) and tasks.get("passed") is False:
                raise ValueError("final THG metabolic task suite failed")


def human_database_stages() -> tuple[HumanDatabaseStage, ...]:
    return (
        HumanDatabaseStage("collect-records"),
        HumanDatabaseStage("snapshot-records", ("collect-records",)),
        HumanDatabaseStage("normalize-records", ("snapshot-records",)),
        HumanDatabaseStage("human-database-reconstruct", ("normalize-records",)),
        HumanDatabaseStage("human-database-validate", ("human-database-reconstruct",)),
        HumanDatabaseStage(
            "human-database-export",
            ("human-database-reconstruct", "human-database-validate"),
        ),
    )


def final_thg_stages() -> tuple[FinalTHGStage, ...]:
    return (
        FinalTHGStage("final-thg-merge-plan"),
        FinalTHGStage("final-thg-merge", ("final-thg-merge-plan",)),
        FinalTHGStage("validate-final-thg", ("final-thg-merge",)),
        FinalTHGStage("export-final-thg", ("final-thg-merge", "validate-final-thg")),
    )
