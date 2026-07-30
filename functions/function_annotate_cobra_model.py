"""Compatibility wrapper for the package model-annotation API."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from thg_protocol.annotation.model import annotate_cobra_model as _annotate_cobra_model

def annotate_cobra_model(
    model: Any,
    met_annotation: Mapping[str, Mapping[str, Any]],
    reac_annotation: Mapping[str, Mapping[str, Any]],
    out_file1: str | Path,
    out_file2: str | Path,
) -> None:
    """Delegate annotation while requiring explicit output paths."""
    _annotate_cobra_model(model, met_annotation, reac_annotation, out_file1, out_file2)


__all__ = ["annotate_cobra_model"]
