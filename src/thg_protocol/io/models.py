"""Lazy COBRA model loading and saving at the package I/O boundary."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def load_model(path: str | Path) -> Any:
    source = Path(path)
    if source.suffix.lower() == ".json":
        from cobra.io import load_json_model

        return load_json_model(str(source))
    from cobra.io import read_sbml_model

    return read_sbml_model(str(source))


def save_model(model: Any, path: str | Path) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.suffix.lower() == ".json":
        return save_json(model, destination)
    return save_sbml(model, destination)


def save_json(model: Any, path: str | Path) -> Path:
    from cobra.io import save_json_model

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    save_json_model(model, str(destination))
    return destination


def save_sbml(model: Any, path: str | Path) -> Path:
    from cobra.io import write_sbml_model

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    write_sbml_model(model, str(destination))
    return destination


load_cobra_model = load_model
save_json_model = save_json
write_sbml_model = save_sbml

__all__ = [
    "load_model",
    "load_cobra_model",
    "save_model",
    "save_json",
    "save_sbml",
    "save_json_model",
    "write_sbml_model",
]
