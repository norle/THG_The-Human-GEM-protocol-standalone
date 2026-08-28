"""Reactome sGPR evidence adapter."""

from __future__ import annotations

from collections.abc import Mapping

from thg_protocol.services.reactome import catalyst_sgpr

from ..evidence import SgprEvidence


def reactome_sgpr_evidence(
    record: Mapping[str, object], *, ec: str = ""
) -> SgprEvidence:
    return catalyst_sgpr(record, ec=ec)


__all__ = ["reactome_sgpr_evidence"]
