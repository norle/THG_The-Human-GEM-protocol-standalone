"""Supporting UniProt protein-to-gene evidence for sGPR resolution."""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from ..evidence import SgprEvidence
from ..stoichiometry import GeneNode, OrNode, normalize_sgpr


def uniprot_sgpr_evidence(
    ec: str, *, proteins: Iterable[Mapping[str, object]]
) -> SgprEvidence:
    """Add UniProt protein mappings without treating free text as stoichiometry."""
    nodes = []
    identifiers = []
    for protein in proteins:
        gene = protein.get("gene", protein.get("gene_symbol", protein.get("gene_id")))
        if not gene:
            continue
        identifier = protein.get("uniprot", protein.get("protein_id", ""))
        evidence = (str(identifier),) if identifier else ()
        nodes.append(GeneNode(str(gene), None, "unknown", "uniprot", evidence))
        if identifier:
            identifiers.append(str(identifier))
    node = normalize_sgpr(OrNode(tuple(nodes))) if nodes else None
    return SgprEvidence(
        "uniprot", ec, node, "supporting", "candidate" if node else "unresolved",
        tuple(sorted(set(identifiers))), warnings=("uniprot-supporting-only",),
    )


__all__ = ["uniprot_sgpr_evidence"]
