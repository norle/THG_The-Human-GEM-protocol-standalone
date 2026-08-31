"""Pure model-vs-evidence GPR selection policy."""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from .evidence import SgprEvidence
from .merge import merge_sgpr_evidence
from .stoichiometry import (
    genes_in_sgpr,
    parse_sgpr,
    sgpr_to_dict,
    to_gpr,
    to_sgpr,
    unambiguous_stoichiometry,
)


def usable_gpr(raw: object) -> tuple[str, list[str]]:
    """Return a canonical GPR and its genes, or empty values when invalid."""
    from thg_protocol.curation.beta1 import canonicalize_gpr, serialize_gpr

    text = str(raw or "").strip()
    if not text:
        return "", []
    try:
        node = canonicalize_gpr(text)
        canonical = serialize_gpr(node)
    except (SyntaxError, TypeError, ValueError):
        return "", []
    return canonical, sorted(
        {str(node.value)}
        if node.kind == "gene"
        else {
            str(gene)
            for child in node.children
            for gene in _gpr_expression_genes(child)
        }
    )


def _gpr_expression_genes(node: object) -> set[str]:
    if getattr(node, "kind", "") == "gene":
        return {str(getattr(node, "value", ""))}
    return {
        gene
        for child in getattr(node, "children", ())
        for gene in _gpr_expression_genes(child)
    }


def _accepted_external_gpr(record: Mapping[str, object]) -> bool:
    status = str(record.get("status", "")).lower()
    confidence = str(record.get("confidence", "")).lower()
    if status in {"unresolved", "ambiguous", "conflict", "candidate"} and (
        confidence != "reaction-matched"
    ):
        return False
    return confidence in {"authoritative", "strong", "reaction-matched"}


@dataclass(frozen=True)
class GprSelection:
    """Selected GPR data returned without workflow or filesystem state."""

    gpr: str
    genes: tuple[str, ...]
    selected_source: str
    status: str
    conflicts: tuple[Mapping[str, object], ...] = ()
    subunit_stoichiometry: tuple[tuple[str, object], ...] = ()
    candidate_sgpr: str | None = None
    sgpr_structure: Mapping[str, object] | None = None
    sgpr_status: str | None = None
    sgpr_sources: tuple[str, ...] = ()
    sgpr_warnings: tuple[str, ...] = ()

    def to_record(self) -> dict[str, object]:
        result: dict[str, object] = {
            "gpr": self.gpr,
            "genes": list(self.genes),
            "subunit_stoichiometry": dict(self.subunit_stoichiometry),
            "valid": bool(self.gpr),
            "conflicts": [dict(item) for item in self.conflicts],
            "status": self.status,
        }
        if self.candidate_sgpr is not None:
            result.update(
                {
                    "candidate_sgpr": self.candidate_sgpr,
                    "sgpr_structure": dict(self.sgpr_structure or {}),
                    "sgpr_status": self.sgpr_status,
                    "sgpr_sources": list(self.sgpr_sources),
                    "sgpr_warnings": list(self.sgpr_warnings),
                }
            )
        return result


def _candidate_key(
    candidate: tuple[str, tuple[str, ...], Mapping[str, object]]
) -> tuple[str, ...]:
    gpr, _, record = candidate
    return (
        gpr,
        str(record.get("source", "")),
        str(record.get("ec", "")),
        json.dumps(dict(record), sort_keys=True, default=str),
    )


def select_reaction_gpr(
    *,
    model_gpr: object,
    model_genes: Iterable[object],
    evidence: Iterable[Mapping[str, object]],
    configured_stoichiometry: Mapping[str, object] | None = None,
) -> GprSelection:
    """Select one reaction GPR while preserving conflicts and sGPR metadata."""
    selected_model_gpr, selected_model_genes = usable_gpr(model_gpr)
    candidates = []
    for record in evidence:
        candidate, candidate_genes = usable_gpr(record.get("candidate_gpr"))
        if candidate:
            candidates.append((candidate, tuple(candidate_genes), dict(record)))
    candidates.sort(key=_candidate_key)
    accepted = [item for item in candidates if _accepted_external_gpr(item[2])]

    sgpr_resolution = None
    mergeable: list[Mapping[str, object]] = []
    for _, _, record in candidates:
        try:
            SgprEvidence.from_mapping(dict(record))
        except (TypeError, ValueError):
            continue
        mergeable.append(record)
    if mergeable:
        sgpr_resolution = merge_sgpr_evidence(mergeable)

    selected = selected_model_gpr
    selected_genes = selected_model_genes or [str(gene) for gene in model_genes]
    selected_source = "model" if selected else "none"
    conflicts: list[Mapping[str, object]] = []
    selected_external = False
    if candidates and sgpr_resolution and sgpr_resolution.status == "conflict":
        conflicts.extend(item[2] for item in candidates)
    if not selected and sgpr_resolution and sgpr_resolution.sgpr:
        selected = to_gpr(sgpr_resolution.sgpr)
        selected_genes = list(genes_in_sgpr(sgpr_resolution.sgpr))
        selected_source = "external-sgpr"
        selected_external = True
    elif not selected and accepted:
        selected, selected_genes, record = accepted[0]
        selected_source = str(record.get("source", "external"))
        selected_external = True
    elif selected:
        conflicts.extend(
            record for candidate, _, record in candidates if candidate != selected
        )

    stoichiometry = dict(configured_stoichiometry or {})
    candidate_sgpr = None
    sgpr_structure = None
    sgpr_status = None
    sgpr_sources: tuple[str, ...] = ()
    sgpr_warnings: tuple[str, ...] = ()
    if sgpr_resolution is not None and sgpr_resolution.sgpr is not None:
        resolution = sgpr_resolution.to_dict()
        candidate_sgpr = str(resolution["sgpr"])
        sgpr_structure = resolution["sgpr_structure"]
        sgpr_status = sgpr_resolution.status
        sgpr_sources = tuple(str(item) for item in resolution["sources"])
        sgpr_warnings = tuple(str(item) for item in resolution["warnings"])
        if not stoichiometry:
            derived = unambiguous_stoichiometry(sgpr_resolution.sgpr)
            if derived is not None:
                stoichiometry = derived
    if selected and not selected_external and candidate_sgpr is None:
        try:
            selected_node = parse_sgpr(selected)
        except ValueError:
            sgpr_warnings = ("model-gpr-not-representable-as-sgpr",)
        else:
            candidate_sgpr = to_sgpr(selected_node)
            sgpr_structure = sgpr_to_dict(selected_node)
            sgpr_status = "candidate"
            sgpr_sources = ("model",)

    status = "conflict" if conflicts else ("resolved" if selected else "unresolved")
    return GprSelection(
        selected,
        tuple(selected_genes),
        selected_source,
        status,
        tuple(conflicts),
        tuple((str(key), value) for key, value in stoichiometry.items()),
        candidate_sgpr,
        sgpr_structure,
        sgpr_status,
        sgpr_sources,
        sgpr_warnings,
    )


__all__ = ["GprSelection", "select_reaction_gpr", "usable_gpr"]
