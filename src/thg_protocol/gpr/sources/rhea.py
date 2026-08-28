"""Rhea reaction-level sGPR evidence adapter."""

from __future__ import annotations

from collections.abc import Mapping

from ..evidence import SgprEvidence
from ..stoichiometry import GeneNode, OrNode, normalize_sgpr


def rhea_sgpr_evidence(ec: str, *, rhea_client: object) -> SgprEvidence:
    matches = list(rhea_client.reactions_for_ec(ec))
    if len(matches) != 1:
        return SgprEvidence(
            "rhea",
            ec,
            None,
            "reaction-matched",
            "unresolved",
            warnings=("ambiguous-rhea-reaction" if matches else "no-rhea-reaction",),
        )
    match = matches[0]
    rhea_id = str(match.get("rhea_id", match.get("id", "")))
    proteins = list(rhea_client.proteins_for_reaction(rhea_id))
    if not proteins and isinstance(match.get("proteins"), list):
        proteins = list(match["proteins"])
    genes = []
    identifiers = []
    for protein in proteins:
        if not isinstance(protein, Mapping):
            continue
        organism = str(protein.get("organism", protein.get("taxon", ""))).lower()
        if organism and not any(
            marker in organism for marker in ("human", "9606", "homo sapiens")
        ):
            continue
        gene = protein.get("gene", protein.get("gene_symbol", protein.get("symbol")))
        if gene:
            genes.append(GeneNode(str(gene), None, "unknown", "rhea", (rhea_id,)))
        identifier = protein.get("uniprot", protein.get("protein_id"))
        if identifier:
            identifiers.append(str(identifier))
    node = normalize_sgpr(OrNode(tuple(genes))) if genes else None
    return SgprEvidence(
        "rhea",
        ec,
        node,
        "reaction-matched",
        "candidate" if node else "unresolved",
        tuple(sorted(set(identifiers))),
        (rhea_id,),
        () if node else ("no-human-protein-association",),
    )


__all__ = ["rhea_sgpr_evidence"]
