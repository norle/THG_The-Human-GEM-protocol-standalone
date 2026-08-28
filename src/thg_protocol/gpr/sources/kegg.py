"""Low-structure KEGG sGPR fallback."""

from __future__ import annotations

import re

from ..evidence import SgprEvidence
from ..stoichiometry import GeneNode, OrNode, normalize_sgpr


def kegg_sgpr_evidence(
    ec: str, *, kegg_client: object, kegg_genes: list[str] | None = None
) -> SgprEvidence:
    genes = list(kegg_genes) if kegg_genes is not None else []
    if kegg_genes is None:
        try:
            linked = kegg_client.link_ecs_to_genes([ec])
            genes = list(linked.get(ec, []))
        except (AttributeError, RuntimeError):
            page = kegg_client.get_ec_html(ec)
            genes = re.findall(r"(?:hsa:)?(\d{3,})", page)
    genes = sorted(set(str(gene) for gene in genes if str(gene).strip()))
    node = (
        normalize_sgpr(
            OrNode(tuple(GeneNode(gene, None, "unknown", "kegg") for gene in genes))
        )
        if genes
        else None
    )
    return SgprEvidence(
        "kegg",
        ec,
        node,
        "weak",
        "candidate" if node else "unresolved",
        tuple(genes),
        warnings=() if node else ("no-kegg-gene-evidence",),
    )


__all__ = ["kegg_sgpr_evidence"]
