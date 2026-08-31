"""Deterministic merging of complete sGPR evidence structures."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from .evidence import SgprEvidence
from .stoichiometry import (
    AndNode,
    GeneNode,
    OrNode,
    SgprNode,
    normalize_sgpr,
    sgpr_to_dict,
    to_gpr,
    to_sgpr,
)

DEFAULT_SOURCE_PRECEDENCE = {
    "reactome": 50,
    "biocyc": 50,
    "metacyc": 50,
    "model": 40,
    "existing-model": 40,
    "rhea": 30,
    "uniprot": 20,
    "kegg": 10,
}
_CONFIDENCE = {
    "weak": 0,
    "supporting": 1,
    "reaction-matched": 2,
    "strong": 3,
    "authoritative": 4,
}


@dataclass(frozen=True)
class SgprResolution:
    sgpr: SgprNode | None
    status: str
    confidence: str
    candidates: tuple[SgprEvidence, ...] = ()
    sources: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    @property
    def node(self) -> SgprNode | None:
        return self.sgpr

    def to_dict(self) -> dict[str, object]:
        return {
            "gpr": to_gpr(self.sgpr) if self.sgpr is not None else "",
            "sgpr": to_sgpr(self.sgpr) if self.sgpr is not None else "",
            "structure": sgpr_to_dict(self.sgpr) if self.sgpr is not None else None,
            "sgpr_structure": (
                sgpr_to_dict(self.sgpr) if self.sgpr is not None else None
            ),
            "status": self.status,
            "confidence": self.confidence,
            "sources": list(self.sources),
            "warnings": list(self.warnings),
            "candidates": [item.to_dict() for item in self.candidates],
        }


def _key(node: SgprNode) -> tuple[object, ...]:
    return tuple(_flatten(item) for item in (sgpr_to_dict(node),))


def _flatten(value: object) -> object:
    if isinstance(value, dict):
        return tuple(
            (key, _flatten(item))
            for key, item in sorted(value.items())
            if key not in {"source", "evidence", "coefficient_status"}
        )
    if isinstance(value, list):
        return tuple(_flatten(item) for item in value)
    return value


def _conservative_score(node: SgprNode) -> tuple[int, int, int]:
    """Rank structures from most to least restrictive.

    More required genes, fewer alternatives, and larger known coefficients
    make a rule more conservative.  Structurally incomparable rules fall
    through to the deterministic serialized-expression tie-breaker below.
    """
    if isinstance(node, GeneNode):
        return (1, 0, node.coefficient or 1)
    child_scores = [_conservative_score(child) for child in node.children]
    if isinstance(node, AndNode):
        return (
            sum(score[0] for score in child_scores),
            sum(score[1] for score in child_scores),
            sum(score[2] for score in child_scores),
        )
    if isinstance(node, OrNode):
        return (
            max(score[0] for score in child_scores),
            sum(score[1] for score in child_scores) + len(node.children) - 1,
            max(score[2] for score in child_scores),
        )
    raise TypeError(f"unsupported sGPR node: {type(node).__name__}")


def merge_sgpr_evidence(
    evidence: Iterable[SgprEvidence | Mapping[str, object]],
    *,
    source_precedence: Mapping[str, int] | None = None,
) -> SgprResolution:
    """Merge evidence without unioning genes or hiding structural conflicts."""
    precedence = {**DEFAULT_SOURCE_PRECEDENCE, **(source_precedence or {})}
    records = [
        (
            item
            if isinstance(item, SgprEvidence)
            else SgprEvidence.from_mapping(dict(item))
        )
        for item in evidence
    ]
    records.sort(
        key=lambda item: (-precedence.get(item.source.lower(), 0), item.source, item.ec)
    )
    usable = [item for item in records if item.sgpr is not None]
    sources = tuple(sorted({item.source for item in records}))
    warnings = tuple(sorted({warning for item in records for warning in item.warnings}))
    if not usable:
        return SgprResolution(
            None, "unresolved", "weak", tuple(records), sources, warnings
        )
    highest_precedence = max(precedence.get(item.source.lower(), 0) for item in usable)
    comparable = [
        item
        for item in usable
        if precedence.get(item.source.lower(), 0) == highest_precedence
    ]
    groups: dict[tuple[object, ...], list[SgprEvidence]] = {}
    for item in comparable:
        normalized = normalize_sgpr(item.sgpr)  # type: ignore[arg-type]
        groups.setdefault(_key(normalized), []).append(
            SgprEvidence(
                item.source,
                item.ec,
                normalized,
                item.confidence,
                item.status,
                item.identifiers,
                item.provenance,
                item.warnings,
            )
        )
    best = min(
        groups.values(),
        key=lambda group: (
            -_conservative_score(group[0].sgpr)[0],
            _conservative_score(group[0].sgpr)[1],
            -_conservative_score(group[0].sgpr)[2],
            to_sgpr(group[0].sgpr),
        ),
    )
    selected = best[0].sgpr
    confidence = max(
        (item.confidence for item in comparable),
        key=lambda value: _CONFIDENCE.get(value, -1),
    )
    status = (
        "conflict"
        if len(groups) > 1
        else (
            "resolved"
            if any(item.status == "resolved" for item in best)
            else best[0].status
        )
    )
    if len(groups) > 1:
        warnings = tuple(sorted({*warnings, "conflicting-sgpr-structures"}))
    return SgprResolution(
        selected, status, confidence, tuple(records), sources, warnings
    )


__all__ = ["DEFAULT_SOURCE_PRECEDENCE", "SgprResolution", "merge_sgpr_evidence"]
