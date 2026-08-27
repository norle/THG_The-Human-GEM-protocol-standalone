"""Model file input/output helpers."""

from __future__ import annotations

from pathlib import Path

from .models import load_model, save_json, save_model, save_sbml


def convert_json_to_sbml(input_path: str | Path, output_path: str | Path) -> Path:
    """Convert a COBRA JSON model to SBML at an explicit destination."""
    source = Path(input_path)
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    save_sbml(load_model(source), destination)
    return destination


__all__ = [
    "convert_json_to_sbml", "load_model", "save_model", "save_json", "save_sbml"
]
