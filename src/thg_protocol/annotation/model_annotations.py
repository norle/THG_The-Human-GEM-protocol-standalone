"""Dependency-light analysis of JSON model metabolite annotations."""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any


def _load_model_payload(model_path: str | Path) -> Mapping[str, Any]:
    payload = json.loads(Path(model_path).read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("model JSON must contain an object")
    metabolites = payload.get("metabolites", [])
    if not isinstance(metabolites, list):
        raise ValueError("model JSON field 'metabolites' must be a list")
    return payload


def analyze_model_annotations(model_path: str | Path) -> dict[str, int]:
    """Count annotation fields across metabolites in a JSON model."""
    payload = _load_model_payload(model_path)
    counts: Counter[str] = Counter()
    for metabolite in payload.get("metabolites", []):
        if not isinstance(metabolite, Mapping):
            continue
        annotations = metabolite.get("annotation", {})
        if isinstance(annotations, Mapping):
            counts.update(str(key) for key in annotations)
    return dict(counts)


def extract_metabolite_annotations(
    model_path: str | Path,
    targets: Sequence[str],
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """Extract annotations for target metabolite names from a JSON model."""
    payload = _load_model_payload(model_path)
    found: dict[str, dict[str, Any]] = {}
    not_found: list[str] = []
    metabolites = payload.get("metabolites", [])
    for target in targets:
        target_text = str(target)
        target_lower = target_text.lower()
        match: Mapping[str, Any] | None = None
        for candidate in metabolites:
            if not isinstance(candidate, Mapping):
                continue
            name = str(candidate.get("name", ""))
            compartment = candidate.get("compartment")
            if name.lower() == target_lower or (
                target_lower in name.lower() and compartment == "c"
            ):
                match = candidate
                break
        if match is None:
            not_found.append(target_text)
            continue

        annotation: dict[str, Any] = {}
        values = match.get("annotation", {})
        if isinstance(values, Mapping):
            for key, value in values.items():
                annotation[str(key)] = value[0] if isinstance(value, list) and len(value) == 1 else value
        for key in ("inchi", "inchikey"):
            if key in match:
                annotation[key] = match[key]
        found[target_text] = annotation
    return found, not_found


__all__ = ["analyze_model_annotations", "extract_metabolite_annotations"]
