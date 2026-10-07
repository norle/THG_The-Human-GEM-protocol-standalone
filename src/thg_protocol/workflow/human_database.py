"""Human Database workflow stages and registration."""

from __future__ import annotations

import json
import shutil
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from thg_protocol.io.models import load_model as _load_cobra_model
from thg_protocol.runtime.hashing import sha256_file
from thg_protocol.runtime.stage import (
    StageContext,
    StageResult,
)
from thg_protocol.runtime.stage import (
    dependency_path as _dependency_path,
)
from thg_protocol.runtime.stage import (
    dump_json as _dump,
)

from .registry import WorkflowDefinition


class HumanDatabaseStage:
    implementation_version = 1

    def __init__(self, stage_id: str, dependencies: tuple[str, ...] = ()) -> None:
        self.id, self.dependencies = stage_id, dependencies
        if stage_id == "human-database-validate":
            self.implementation_version = 3
        self.output_role = "model" if stage_id.endswith("reconstruct") else "artifact"
        self.kind = "mutation" if stage_id.endswith("reconstruct") else "collection"

    def enabled(self, config: Any) -> bool:
        return "human_database" in config.sections

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
        if self.id not in {
            "collect-records",
            "snapshot-records",
            "normalize-records",
            "human-database-reconstruct",
            "human-database-validate",
            "human-database-export",
        }:
            raise ValueError(f"unknown Human Database stage: {self.id}")
        section = context.config.sections["human_database"]
        records = Path(str(section["records"]))
        if self.id == "collect-records":
            if section.get("mode", "offline") == "live":
                raise ValueError(
                    "registered Human Database live mode requires an injected "
                    "source adapter"
                )
            output = shutil.copy2(records, work_dir / "collected-records.json")
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
            output = shutil.copy2(source, work_dir / "records-snapshot.json")
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
        from thg_protocol.io.models import save_json, save_sbml

        json_model = work_dir / "human-database-model.json"
        xml_model = work_dir / "human-database-model.xml"
        save_json(model, json_model)
        save_sbml(model, xml_model)
        validation = shutil.copy2(
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


HUMAN_DATABASE_WORKFLOW = WorkflowDefinition(
    "human-database",
    human_database_stages(),
    frozenset({"human_database"}),
    "Offline-first Human Database reconstruction",
)


__all__ = ["HUMAN_DATABASE_WORKFLOW", "HumanDatabaseStage", "human_database_stages"]
