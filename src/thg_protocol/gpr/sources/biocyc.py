"""BioCyc structural sGPR evidence parsing."""

from __future__ import annotations

from collections.abc import Mapping

from ..evidence import SgprEvidence
from ..stoichiometry import AndNode, GeneNode, OrNode, SgprNode, normalize_sgpr


def _gene(
    value: Mapping[str, object], *, source: str, evidence: str
) -> GeneNode | None:
    name = value.get("gene", value.get("gene_symbol", value.get("symbol")))
    if not name:
        return None
    coefficient = value.get(
        "coefficient", value.get("stoichiometry", value.get("count"))
    )
    try:
        coefficient = int(coefficient) if coefficient is not None else None
    except (TypeError, ValueError):
        coefficient = None
    return GeneNode(
        str(name),
        coefficient,
        "observed" if coefficient is not None else "unknown",
        source,
        (evidence,),
    )


def _enzyme(value: object, *, evidence: str) -> SgprNode | None:
    if not isinstance(value, Mapping):
        return None
    components = value.get(
        "components", value.get("subunits", value.get("members", value.get("proteins")))
    )
    if isinstance(components, list):
        children = tuple(
            child
            for item in components
            if isinstance(item, Mapping)
            for child in (
                _gene(item, source="biocyc", evidence=evidence)
                or _enzyme(item, evidence=evidence),
            )
            if child is not None
        )
        if children:
            return normalize_sgpr(AndNode(children))
    return _gene(value, source="biocyc", evidence=evidence)


def _record_node(record: object, *, evidence: str) -> SgprNode | None:
    if isinstance(record, list):
        children = tuple(
            node
            for item in record
            if (node := _enzyme(item, evidence=evidence)) is not None
        )
        return normalize_sgpr(OrNode(children)) if children else None
    if not isinstance(record, Mapping):
        return None
    alternatives = record.get(
        "enzymes", record.get("enzyme_records", record.get("alternatives"))
    )
    if isinstance(alternatives, list):
        children = tuple(
            node
            for item in alternatives
            if (node := _enzyme(item, evidence=evidence)) is not None
        )
        if children:
            return normalize_sgpr(OrNode(children))
    return _enzyme(record, evidence=evidence)


def biocyc_sgpr_evidence(ec: str, *, biocyc_client: object) -> SgprEvidence:
    """Read structured BioCyc records, falling back to an unstructured gene list."""
    record: object = None
    for name in ("get_ec_records", "get_ec_data", "get_ec_record"):
        method = getattr(biocyc_client, name, None)
        if method is not None:
            record = method(ec)
            break
    node = _record_node(record, evidence=str(ec))
    warnings: list[str] = []
    source = "biocyc"
    identifiers: tuple[str, ...] = ()
    if node is None:
        from ..lookup import parse_gene_pairs

        pairs: list[tuple[str, str]] = []
        for organization in ("HUMAN", "META"):
            try:
                pairs = parse_gene_pairs(
                    str(biocyc_client.get_ec_html(ec, organization))
                )
            except Exception:
                continue
            if pairs:
                break
        if pairs:
            source = "biocyc" if organization == "HUMAN" else "metacyc"
            identifiers = tuple(identifier for _, identifier in pairs)
            node = normalize_sgpr(
                OrNode(
                    tuple(
                        GeneNode(symbol, None, "unknown", source, (identifier,))
                        for symbol, identifier in pairs
                    )
                )
            )
            warnings.append("biocyc-gene-list-no-complex-structure")
    identifier = str(ec)
    return SgprEvidence(
        source,
        str(ec),
        node,
        "strong" if node is not None and not warnings else "candidate",
        (
            "resolved"
            if node is not None and not warnings
            else ("candidate" if node is not None else "unresolved")
        ),
        identifiers=identifiers,
        provenance=(identifier,),
        warnings=tuple(warnings),
    )


__all__ = ["biocyc_sgpr_evidence"]
