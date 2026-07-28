"""Compatibility wrapper for the package model-annotation API."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from thg_protocol.annotation.model import annotate_cobra_model as _annotate_cobra_model

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def annotate_cobra_model(
    model: Any,
    met_annotation: Mapping[str, Mapping[str, Any]],
    reac_annotation: Mapping[str, Mapping[str, Any]],
    out_file1: str | Path = PROJECT_ROOT / "models" / "THG-beta1.1.1.xml",
    out_file2: str | Path = PROJECT_ROOT / "models" / "THG-beta1.1.xml",
) -> None:
    """Preserve the legacy defaults while delegating to ``thg_protocol``."""
    _annotate_cobra_model(model, met_annotation, reac_annotation, out_file1, out_file2)


__all__ = ["annotate_cobra_model"]
