"""Validation workflow stages."""

from __future__ import annotations

import json
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

    implementation_version = 1

    def __init__(self, stage_id: str, dependencies: tuple[str, ...] = ()) -> None:
        self.id, self.dependencies = stage_id, dependencies
        self.output_role = "model" if stage_id == "validate-input" else "validation"
        self.kind = "collection" if stage_id == "validate-input" else "validation"

    def enabled(self, config: Any) -> bool:
        del config
        return True

    def fingerprint_data(self, context: StageContext) -> Mapping[str, object]:
        section = context.config.sections.get("validation", {})
        return {
            "stage": self.id,
            "version": self.implementation_version,
            "configuration": dict(section) if isinstance(section, Mapping) else {},
        }

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
        model = _load_cobra_model(_dependency_path(context, "validate-input", "model"))
        if self.id == "validate-checks":
            from thg_protocol.validation import validate_model

            report = validate_model(
                model,
                str(section.get("profile", "structural-fast")),
                run_solver=section.get("run_solver"),
            )
            output = work_dir / "validation.json"
            output.write_text(
                json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
            return StageResult((("validation", output),), report)
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
    )


__all__ = ["ValidationScientificStage", "validation_stages"]
