"""Normalized sGPR evidence records."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .stoichiometry import (
    SgprNode,
    genes_in_sgpr,
    parse_sgpr,
    sgpr_from_dict,
    sgpr_to_dict,
    to_gpr,
    to_sgpr,
)


@dataclass(frozen=True)
class SgprEvidence:
    source: str
    ec: str
    sgpr: SgprNode | None
    confidence: str = "weak"
    status: str = "candidate"
    identifiers: tuple[str, ...] = ()
    provenance: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "source", str(self.source))
        object.__setattr__(self, "ec", str(self.ec))
        for field in ("identifiers", "provenance", "warnings"):
            object.__setattr__(
                self, field, tuple(str(item) for item in getattr(self, field))
            )

    @property
    def genes(self) -> tuple[str, ...]:
        return genes_in_sgpr(self.sgpr) if self.sgpr is not None else ()

    def to_dict(self) -> dict[str, object]:
        result: dict[str, object] = {
            "source": self.source,
            "ec": self.ec,
            "confidence": self.confidence,
            "status": self.status,
            "identifiers": list(self.identifiers),
            "provenance": list(self.provenance),
            "warnings": list(self.warnings),
            "gene_symbols": list(self.genes),
            "candidate_gpr": to_gpr(self.sgpr) if self.sgpr is not None else "",
            "candidate_sgpr": to_sgpr(self.sgpr) if self.sgpr is not None else "",
            "sgpr_structure": (
                sgpr_to_dict(self.sgpr) if self.sgpr is not None else None
            ),
        }
        return result

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> SgprEvidence:
        node = value.get("sgpr")
        structure = value.get("sgpr_structure", value.get("structure"))
        if node is None and structure is not None:
            node = sgpr_from_dict(structure)
        if node is None and value.get("candidate_sgpr"):
            node = parse_sgpr(str(value["candidate_sgpr"]))
        if node is None and value.get("candidate_gpr"):
            node = parse_sgpr(str(value["candidate_gpr"]))
        identifiers = value.get("identifiers", value.get("gene_identifiers", ()))
        if isinstance(identifiers, str):
            identifiers = (identifiers,)
        return cls(
            source=str(value.get("source", "unknown")),
            ec=str(value.get("ec", "")),
            sgpr=node,
            confidence=str(value.get("confidence", "weak")),
            status=str(value.get("status", "candidate")),
            identifiers=tuple(identifiers),
            provenance=tuple(value.get("provenance", ())),
            warnings=tuple(value.get("warnings", ())),
        )


__all__ = ["SgprEvidence"]
