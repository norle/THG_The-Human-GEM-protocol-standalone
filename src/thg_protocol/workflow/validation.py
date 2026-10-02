"""Validation workflow stages."""

from __future__ import annotations

import json
import platform
import shutil
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from thg_protocol.io.models import load_model as _load_cobra_model
from thg_protocol.runtime.hashing import sha256_file
from thg_protocol.runtime.stage import StageContext, StageResult
from thg_protocol.runtime.stage import dependency_path as _dependency_path


class ValidationScientificStage:
    """Run structural validation and optional MEMOTE checks."""

    implementation_version = 5

    def __init__(self, stage_id: str, dependencies: tuple[str, ...] = ()) -> None:
        self.id, self.dependencies = stage_id, dependencies
        self.output_role = "model" if stage_id == "validate-input" else "validation"
        self.kind = "collection" if stage_id == "validate-input" else "validation"

    def enabled(self, config: Any) -> bool:
        del config
        return True

    def fingerprint_data(self, context: StageContext) -> Mapping[str, object]:
        section = context.config.sections.get("validation", {})
        section = dict(section) if isinstance(section, Mapping) else {}
        data: dict[str, object] = {
            "stage": self.id,
            "version": self.implementation_version,
            "configuration": section,
        }
        reference = section.get("reference_model")
        if self.id == "validate-checks" and reference is not None:
            data["reference_model_sha256"] = sha256_file(Path(str(reference)))
        return data

    def run(self, context: StageContext, work_dir: Path) -> StageResult:
        section = context.config.sections.get("validation", {})
        if not isinstance(section, Mapping):
            section = {}
        if self.id == "validate-input":
            source = Path(str(section["input_model"]))
            destination = work_dir / f"input-model{source.suffix.lower()}"
            shutil.copy2(source, destination)
            _load_cobra_model(destination)
            return StageResult(
                (("model", destination),), {"input_sha256": sha256_file(source)}
            )
        model_path = _dependency_path(context, "validate-input", "model")
        model = _load_cobra_model(model_path)
        if self.id == "validate-checks":
            from thg_protocol.validation import validate_model

            reference = section.get("reference_model")
            report = validate_model(
                model,
                str(section.get("profile", "structural-fast")),
                run_solver=section.get("run_solver"),
                conservation_exclusions=section.get("conservation_exclusions", ()),
                reference_model=None
                if reference is None
                else _load_cobra_model(Path(str(reference))),
            )
            output = work_dir / "validation.json"
            output.write_text(
                json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
            return StageResult((("validation", output),), report)
        if self.id == "assemble-validation-report":
            from thg_protocol.validation_report import (
                render_validation_html,
                render_validation_summary,
            )

            validation = json.loads(
                _dependency_path(context, "validate-checks", "validation").read_text(
                    encoding="utf-8"
                )
            )
            memote = json.loads(
                _dependency_path(context, "validate-memote", "memote").read_text(
                    encoding="utf-8"
                )
            )
            payload = {
                "schema": "thg.validation.report/v1",
                "schema_version": 1,
                "model_id": model.id,
                "model_checksum": sha256_file(model_path),
                "validation_profile": validation["profile"],
                "validation_profile_version": 1,
                "software": {"python": platform.python_version()},
                "after": {
                    "reactions": len(model.reactions),
                    "metabolites": len(model.metabolites),
                    "genes": len(model.genes),
                    "compartments": len(model.compartments),
                },
                "validation": validation,
                "solver": validation.get("solver", {}),
                "tasks": {"status": "not-requested", "tasks": [], "passed": None},
                "memote": memote,
                "warnings": sorted(
                    str(item["id"])
                    for item in validation.get("checks", [])
                    if item.get("passed") is not True
                    and not item.get("release_blocking")
                ),
            }
            report = work_dir / "validation-report.json"
            report.write_text(
                json.dumps(payload, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            html = work_dir / "validation-report.html"
            html.write_text(render_validation_html(payload), encoding="utf-8")
            summary = work_dir / "validation-summary.md"
            summary.write_text(render_validation_summary(payload), encoding="utf-8")
            return StageResult(
                (
                    ("validation", report),
                    ("validation-html", html),
                    ("validation-summary", summary),
                ),
                {"passed": validation.get("passed")},
            )

        from thg_protocol.memote import run_memote

        if bool(section.get("run_memote", False)):
            report = run_memote(
                _dependency_path(context, "validate-input", "model"),
                work_dir / "memote",
                command=tuple(section.get("memote_command", ["memote", "run"])),
                threshold=section.get("memote_threshold"),
            )
        else:
            report = {"status": "not-requested", "artifacts": {}}
        output = work_dir / "memote.json"
        output.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        return StageResult((("memote", output),), report)

    def validate(self, result: StageResult) -> None:
        if not result.outputs or any(not path.is_file() for _, path in result.outputs):
            raise ValueError(f"stage '{self.id}' did not produce complete artifacts")


def validation_stages() -> tuple[ValidationScientificStage, ...]:
    return (
        ValidationScientificStage("validate-input"),
        ValidationScientificStage("validate-checks", ("validate-input",)),
        ValidationScientificStage("validate-memote", ("validate-checks",)),
        ValidationScientificStage("assemble-validation-report", ("validate-memote",)),
    )


__all__ = ["ValidationScientificStage", "validation_stages"]
