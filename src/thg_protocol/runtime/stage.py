"""Workflow-agnostic stage contract used by the execution runtime."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class StageContext:
    config: object
    run_dir: Path
    manifest: Mapping[str, object]
    log_path: Path | None = None


@dataclass(frozen=True)
class StageResult:
    outputs: tuple[tuple[str, Path], ...]
    summary: Mapping[str, object]


class Stage(Protocol):
    id: str
    dependencies: tuple[str, ...]
    implementation_version: int

    def enabled(self, config: object) -> bool: ...

    def fingerprint_data(self, context: StageContext) -> Mapping[str, object]: ...

    def run(self, context: StageContext, work_dir: Path) -> StageResult: ...

    def validate(self, result: StageResult) -> None: ...


def dump_json(path: Path, value: object) -> Path:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    return path


def dependency_records(
    context: StageContext, stage_id: str
) -> list[Mapping[str, object]]:
    steps = context.manifest.get("steps")
    if not isinstance(steps, Mapping):
        raise RuntimeError("manifest has no steps")
    entry = steps.get(stage_id)
    if not isinstance(entry, Mapping):
        raise RuntimeError(f"missing dependency step: {stage_id}")
    outputs = entry.get("outputs")
    if not isinstance(outputs, list) or not outputs:
        raise RuntimeError(f"dependency has no outputs: {stage_id}")
    return [item for item in outputs if isinstance(item, Mapping)]


def dependency_path(context: StageContext, stage_id: str, role: str) -> Path:
    for record in dependency_records(context, stage_id):
        if record.get("role") == role and isinstance(record.get("path"), str):
            return context.run_dir / str(record["path"])
    raise RuntimeError(f"dependency '{stage_id}' has no output role '{role}'")


__all__ = [
    "Stage",
    "StageContext",
    "StageResult",
    "dump_json",
    "dependency_records",
    "dependency_path",
]
