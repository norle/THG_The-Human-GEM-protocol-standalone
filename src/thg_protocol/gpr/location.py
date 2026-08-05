"""Injectable subcellular-location resolution for GPR workflows."""

from __future__ import annotations

import ast
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from thg_protocol.services.ensembl import EnsemblClientProtocol
from thg_protocol.services.location import LocationClient, LocationClientProtocol

_LOCATION_PATTERNS = (
    ("Mitochondria", re.compile(r"mitochondri", re.I)),
    ("Nucleus", re.compile(r"nucle(?:us|ar)", re.I)),
    (
        "Endoplasmic reticulum",
        re.compile(r"endoplasmic\s+reticulum|(?<![A-Za-z])ER(?![A-Za-z])", re.I),
    ),
    ("Golgi apparatus", re.compile(r"golgi", re.I)),
    ("Peroxisome", re.compile(r"peroxisom", re.I)),
    ("Plasma membrane", re.compile(r"plasma\s+membrane", re.I)),
    ("Cytosol", re.compile(r"cytosol|cytoplasm", re.I)),
)


def _location_from_page(
    page: str, allowed: set[str], fallback_location: str | None
) -> str | None:
    for name, pattern in _LOCATION_PATTERNS:
        if name in allowed and pattern.search(page):
            return name
    return fallback_location


def _ensembl_identifier(value: Any) -> str | None:
    if isinstance(value, Mapping):
        value = value.get("ensembl")
    else:
        value = getattr(value, "ensembl", None)
    return str(value) if value else None


def _parse_gpr(gpr: str, tokens: list[str]) -> tuple[ast.AST, dict[str, str]] | None:
    if not gpr.strip():
        return None
    replacements: dict[str, str] = {}
    expression = gpr
    for index, token in enumerate(
        sorted(set(tokens), key=lambda value: (-len(value), value))
    ):
        placeholder = f"THGGENE{index}"
        expression = re.sub(
            rf"(?<![A-Za-z0-9_-]){re.escape(token)}(?![A-Za-z0-9_-])",
            placeholder,
            expression,
        )
        replacements[placeholder] = token
    expression = re.sub(r"\bAND\b", "and", expression, flags=re.I)
    expression = re.sub(r"\bOR\b", "or", expression, flags=re.I)
    try:
        return ast.parse(expression, mode="eval").body, replacements
    except SyntaxError:
        return None


def _render_gpr(
    node: ast.AST,
    replacements: Mapping[str, str],
    *,
    stoich: bool = False,
    resolved: Mapping[str, str] | None = None,
) -> str:
    if isinstance(node, ast.Name):
        token = replacements.get(node.id, node.id)
        token = (resolved or {}).get(token, token)
        return f"({token}*1)" if stoich else f"({token})"
    if isinstance(node, ast.BoolOp):
        operator = "and" if isinstance(node.op, ast.And) else "or"
        children = [
            _render_gpr(child, replacements, stoich=stoich, resolved=resolved)
            for child in node.values
        ]
        return f"({f' {operator} '.join(children)})"
    if isinstance(node, ast.Constant):
        return str(node.value)
    return ast.unparse(node)


def _sorted_rules(rules: dict[str, str]) -> dict[str, str]:
    return {location: rules[location] for location in sorted(rules)}


def resolve_locations(
    gpr: str,
    gene_names: list[str] | tuple[str, ...],
    gene_ids: list[str] | tuple[str, ...],
    *,
    allowed_locations: set[str] | None = None,
    location_client: LocationClientProtocol | None = None,
    ensembl_client: EnsemblClientProtocol | None = None,
    session: Any | None = None,
    location_dict_file: str | Path | None = None,
    fallback_location: str | None = None,
) -> tuple[dict[str, str], dict[str, str], dict[str, str], dict[str, list[str]]]:
    """Resolve genes to locations and return the historical four dictionaries.

    ``gpr`` is parsed when supplied, preserving Boolean AND/OR relationships.
    A complex spanning locations is retained in full for each participating
    location; callers must resolve cross-compartment reaction semantics before
    using the result for expansion. ``ensembl_client`` is used to normalize the
    third rule dictionary when supplied.

    A missing or unmatched page is unresolved by default. Set
    ``fallback_location`` explicitly to request a deterministic fallback; the
    resolver never silently assigns Cytosol merely because lookup failed.
    """
    allowed = set(allowed_locations or {"Cytosol"})
    if fallback_location is not None and fallback_location not in allowed:
        raise ValueError("fallback_location must be one of allowed_locations")
    if location_dict_file is not None:
        import pickle

        with Path(location_dict_file).open("rb") as handle:
            loaded = pickle.load(handle)
        if isinstance(loaded, dict) and loaded:
            allowed = {str(value) for value in loaded.values()}
            if fallback_location is not None and fallback_location not in allowed:
                raise ValueError("fallback_location must be in location dictionary")

    client = location_client or LocationClient(session=session)
    names = list(gene_names)
    identifiers = list(gene_ids)
    resolved_ensembl: dict[str, str] = {}
    if ensembl_client is not None:
        lookup_tokens = [token for token in (*names, *identifiers) if token]
        try:
            annotations = ensembl_client.annotate(lookup_tokens)
        except Exception:
            annotations = {}
        for token, annotation in annotations.items():
            resolved = _ensembl_identifier(annotation)
            if resolved:
                resolved_ensembl[str(token)] = resolved

    location_by_token: dict[str, str | None] = {}
    gene_map: dict[str, list[str]] = {}
    client_locations: dict[str, str | None] = {}
    for index, gene in enumerate(names):
        identifier = identifiers[index] if index < len(identifiers) else gene
        try:
            page = client.get_page(
                f"https://www.uniprot.org/uniprotkb/{identifier}_HUMAN.txt"
            )
        except Exception:
            page = ""
        location = _location_from_page(page, allowed, fallback_location)
        client_locations[gene] = location
        location_by_token[gene] = location
        location_by_token[identifier] = location
        gene_map.setdefault(identifier, []).append(gene)

    for identifier, genes in gene_map.items():
        gene_map[identifier] = sorted(set(genes))

    rule_stoich: dict[str, str] = {}
    rule_plain: dict[str, str] = {}
    rule_ensembl: dict[str, str] = {}
    parsed = _parse_gpr(gpr, [*names, *identifiers])
    if gpr.strip() and parsed is None:
        raise ValueError("gpr could not be parsed for location resolution")
    if parsed is not None:
        tree, replacements = parsed
        tokens_in_rule = {
            replacements.get(node.id, node.id)
            for node in ast.walk(tree)
            if isinstance(node, ast.Name)
        }
        locations = {
            location_by_token[token]
            for token in tokens_in_rule
            if location_by_token.get(token) is not None
        }
        for location in sorted(locations):
            rule_plain[location] = _render_gpr(tree, replacements)
            rule_stoich[location] = _render_gpr(tree, replacements, stoich=True)
            resolved = {
                token: resolved_ensembl.get(token, token)
                for token in tokens_in_rule
            }
            rule_ensembl[location] = _render_gpr(
                tree, replacements, resolved=resolved
            )
    else:
        for index, gene in enumerate(names):
            identifier = identifiers[index] if index < len(identifiers) else gene
            location = client_locations.get(gene)
            if location is None:
                continue
            ensembl = resolved_ensembl.get(
                gene, resolved_ensembl.get(identifier, identifier)
            )
            rule_stoich[location] = (
                f"{rule_stoich[location]} or ({gene}*1)"
                if location in rule_stoich
                else f"({gene}*1)"
            )
            rule_plain[location] = (
                f"{rule_plain[location]} or ({gene})"
                if location in rule_plain
                else f"({gene})"
            )
            rule_ensembl[location] = (
                f"{rule_ensembl[location]} or ({ensembl})"
                if location in rule_ensembl
                else f"({ensembl})"
            )

    return (
        _sorted_rules(rule_stoich),
        _sorted_rules(rule_plain),
        _sorted_rules(rule_ensembl),
        {identifier: gene_map[identifier] for identifier in sorted(gene_map)},
    )


__all__ = ["resolve_locations"]
