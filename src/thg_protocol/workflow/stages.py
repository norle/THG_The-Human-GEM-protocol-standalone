"""Compatibility facade for the workflow-agnostic runtime stage contract."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from thg_protocol.io.models import load_model
from thg_protocol.runtime.stage import (
    Stage,
    StageContext,
    StageResult,
    dependency_path,
    dependency_records,
    dump_json,
)

_dump = dump_json


def _load_cobra_model(path: str | Path) -> Any:
    return load_model(path)


def _dependency_records(
    context: StageContext, stage_id: str
) -> list[Mapping[str, object]]:
    return dependency_records(context, stage_id)


def _dependency_path(context: StageContext, stage_id: str, role: str) -> Path:
    return dependency_path(context, stage_id, role)


__all__ = [
    "Stage", "StageContext", "StageResult", "_dump", "_load_cobra_model",
    "_dependency_records", "_dependency_path",
]
