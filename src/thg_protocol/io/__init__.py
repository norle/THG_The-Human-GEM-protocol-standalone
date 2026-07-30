"""Model file input/output helpers."""

from __future__ import annotations

from pathlib import Path


def convert_json_to_sbml(input_path: str | Path, output_path: str | Path) -> Path:
    """Convert a COBRA JSON model to SBML at an explicit destination."""
    from cobra.io import load_json_model, write_sbml_model

    source = Path(input_path)
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    write_sbml_model(load_json_model(str(source)), str(destination))
    return destination


__all__ = ["convert_json_to_sbml"]
