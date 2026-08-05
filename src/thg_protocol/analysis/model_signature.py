"""Deterministic semantic signatures for COBRA-style models.

The signature deliberately compares model meaning rather than serialized
formatting. It is dependency-light: callers provide a model exposing the
usual COBRApy collections, while no model is loaded at import time.
"""

from __future__ import annotations

import ast
import json
import math
from collections.abc import Mapping, Sequence
from typing import Any

__all__ = ["model_signature", "diff_model_signatures"]

SIGNATURE_VERSION = 1


def _stable_key(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def _normalize(value: Any) -> Any:
    """Return JSON-compatible, recursively sorted annotation data."""
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if math.isfinite(value):
            return value
        return str(value)
    if isinstance(value, Mapping):
        return {
            str(key): _normalize(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (set, frozenset)):
        return sorted((_normalize(item) for item in value), key=_stable_key)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return sorted((_normalize(item) for item in value), key=_stable_key)
    item = getattr(value, "item", None)
    if callable(item):
        return _normalize(item())
    return str(value)


def _object_name(value: Any) -> str | None:
    name = getattr(value, "name", None)
    return None if name is None else str(name)


def _annotation(value: Any) -> Any:
    return _normalize(getattr(value, "annotation", {}))


def _gpr_node(node: ast.AST) -> Any:
    if isinstance(node, ast.Name):
        return {"gene": node.id}
    if isinstance(node, ast.Constant):
        return {"value": _normalize(node.value)}
    if isinstance(node, ast.BoolOp):
        operation = "and" if isinstance(node.op, ast.And) else "or"
        children = sorted((_gpr_node(child) for child in node.values), key=_stable_key)
        return {operation: children}
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        return {"not": _gpr_node(node.operand)}
    return {"ast": ast.dump(node, annotate_fields=True, include_attributes=False)}


def _normalized_gpr(reaction: Any) -> Any:
    gpr = getattr(reaction, "gpr", None)
    body = getattr(gpr, "body", None)
    if body is not None:
        return _gpr_node(body)
    rule = str(getattr(reaction, "gene_reaction_rule", "") or "").strip()
    if not rule:
        return None
    try:
        return _gpr_node(ast.parse(rule, mode="eval").body)
    except SyntaxError:
        return {"raw": rule}


def _stoichiometry(reaction: Any) -> list[dict[str, Any]]:
    metabolites = getattr(reaction, "metabolites", {})
    items = metabolites.items() if hasattr(metabolites, "items") else metabolites
    values = [
        {"metabolite": str(metabolite.id), "coefficient": float(coefficient)}
        for metabolite, coefficient in items
    ]
    return sorted(values, key=lambda item: item["metabolite"])


def _metabolite_signature(metabolite: Any) -> dict[str, Any]:
    return {
        "id": str(metabolite.id),
        "name": _object_name(metabolite),
        "formula": getattr(metabolite, "formula", None),
        "charge": getattr(metabolite, "charge", None),
        "compartment": getattr(metabolite, "compartment", None),
        "annotation": _annotation(metabolite),
    }


def _reaction_signature(reaction: Any) -> dict[str, Any]:
    return {
        "id": str(reaction.id),
        "name": _object_name(reaction),
        "lower_bound": float(reaction.lower_bound),
        "upper_bound": float(reaction.upper_bound),
        "stoichiometry": _stoichiometry(reaction),
        "gene_reaction_rule": _normalized_gpr(reaction),
        "annotation": _annotation(reaction),
    }


def _gene_signature(gene: Any) -> dict[str, Any]:
    return {
        "id": str(gene.id),
        "name": _object_name(gene),
        "annotation": _annotation(gene),
    }


def _group_signature(group: Any) -> dict[str, Any]:
    members = getattr(group, "members", ())
    return {
        "id": str(group.id),
        "name": _object_name(group),
        "kind": getattr(group, "kind", None),
        "members": sorted(str(member.id) for member in members),
    }


def _objective_signature(model: Any) -> list[dict[str, Any]]:
    objective = getattr(model, "objective", None)
    if objective is None:
        return []
    result: list[dict[str, Any]] = []
    for reaction in getattr(model, "reactions", ()):
        try:
            coefficients = objective.get_linear_coefficients(
                [reaction.forward_variable, reaction.reverse_variable]
            )
            forward = float(coefficients.get(reaction.forward_variable, 0.0))
            reverse = float(coefficients.get(reaction.reverse_variable, 0.0))
        except (AttributeError, TypeError):
            continue
        coefficient = forward if forward != 0.0 else -reverse
        if coefficient != 0.0:
            result.append({"reaction": str(reaction.id), "coefficient": coefficient})
    return sorted(result, key=lambda item: item["reaction"])


def model_signature(model: Any) -> dict[str, Any]:
    """Return a deterministic JSON-compatible semantic model signature.

    Collections and annotation values are sorted. Boolean GPR operands are
    canonicalized as commutative ``and``/``or`` trees, so equivalent operand
    ordering does not create a false difference.
    """
    compartments = getattr(model, "compartments", {})
    compartment_items = [
        {"id": str(identifier), "name": name}
        for identifier, name in compartments.items()
    ]
    signature = {
        "signature_version": SIGNATURE_VERSION,
        "model": {
            "id": str(getattr(model, "id", "")),
            "name": _object_name(model),
            "compartments": sorted(compartment_items, key=lambda item: item["id"]),
        },
        "metabolites": sorted(
            (_metabolite_signature(item) for item in model.metabolites),
            key=lambda item: item["id"],
        ),
        "reactions": sorted(
            (_reaction_signature(item) for item in model.reactions),
            key=lambda item: item["id"],
        ),
        "genes": sorted(
            (_gene_signature(item) for item in model.genes), key=lambda item: item["id"]
        ),
        "groups": sorted(
            (_group_signature(item) for item in getattr(model, "groups", ())),
            key=lambda item: item["id"],
        ),
        "objective": _objective_signature(model),
    }
    return _normalize(signature)


def _keyed(
    values: Sequence[Mapping[str, Any]], key: str
) -> dict[str, Mapping[str, Any]]:
    return {str(value[key]): value for value in values}


def diff_model_signatures(
    signature_a: Mapping[str, Any], signature_b: Mapping[str, Any]
) -> dict[str, Any]:
    """Return added, removed, and changed semantic objects between signatures."""
    collections = ("metabolites", "reactions", "genes", "groups", "objective")
    diff: dict[str, Any] = {
        "signature_versions": {
            "a": signature_a.get("signature_version"),
            "b": signature_b.get("signature_version"),
        },
        "model": {
            "changed": signature_a.get("model") != signature_b.get("model"),
            "a": signature_a.get("model"),
            "b": signature_b.get("model"),
        },
        "added": {},
        "removed": {},
        "changed": {},
    }
    for collection in collections:
        key = "reaction" if collection == "objective" else "id"
        left = _keyed(signature_a.get(collection, ()), key)
        right = _keyed(signature_b.get(collection, ()), key)
        left_ids, right_ids = set(left), set(right)
        diff["added"][collection] = sorted(right_ids - left_ids)
        diff["removed"][collection] = sorted(left_ids - right_ids)
        diff["changed"][collection] = [
            {"id": identifier, "a": left[identifier], "b": right[identifier]}
            for identifier in sorted(left_ids & right_ids)
            if left[identifier] != right[identifier]
        ]
    return diff
