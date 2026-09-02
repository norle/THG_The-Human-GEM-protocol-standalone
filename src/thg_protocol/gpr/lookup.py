"""Injectable BioCyc/KEGG GPR lookup workflow."""

from __future__ import annotations

import re
from html import unescape
from html.parser import HTMLParser
from typing import Any
from urllib.parse import parse_qs, urlparse

from thg_protocol.services.biocyc import BioCycClient, BioCycClientProtocol
from thg_protocol.services.kegg import KeggClient, KeggClientProtocol

from .evidence import SgprEvidence
from .merge import merge_sgpr_evidence
from .stoichiometry import (
    GeneNode,
    OrNode,
    default_sgpr_coefficients,
    genes_in_sgpr,
    sgpr_from_dict,
    sgpr_to_dict,
    to_legacy_sgpr,
    to_sgpr,
)

PARSER_VERSION = "biocyc-gene-anchor-v1"


class _GenePageParser(HTMLParser):
    """Read visible BioCyc gene blocks; HTML attributes are never content."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._bold = False
        self._pending = False
        self._in_gene = False
        self._anchor_depth = 0
        self._anchor_text: list[str] = []
        self._anchor_href = ""
        self._tokens: list[str] = []
        self._pairs: set[tuple[str, str]] = set()

    @staticmethod
    def _identifier(href: str) -> str:
        values = parse_qs(urlparse(href).query).get("object", [])
        return values[0].strip() if values else ""

    def _finish(self) -> None:
        if not self._in_gene:
            return
        if self._anchor_text:
            symbol = "".join(self._anchor_text).strip()
            identifier = self._identifier(self._anchor_href)
            if symbol and identifier:
                self._pairs.add((symbol, identifier))
        values = re.findall(r"[A-Za-z0-9_-]+", " ".join(self._tokens))
        if len(values) >= 2:
            self._pairs.add((values[0], values[1]))
        self._in_gene = False
        self._pending = False
        self._anchor_depth = 0
        self._anchor_text = []
        self._anchor_href = ""
        self._tokens = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag == "b":
            self._bold = True
        elif tag == "a" and (self._pending or self._in_gene):
            if not self._in_gene:
                self._in_gene = True
                self._pending = False
            self._anchor_depth += 1
            if self._anchor_depth == 1:
                self._anchor_href = dict(attrs).get("href") or ""
        elif tag in {"br", "p", "div", "li", "tr"}:
            self._finish()

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "b":
            self._bold = False
        elif tag == "a" and self._anchor_depth:
            self._anchor_depth -= 1
        elif tag in {"p", "div", "li", "tr"}:
            self._finish()

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if self._bold and text.lower() == "gene:":
            self._pending = True
            return
        if self._pending and not text:
            return
        if self._pending:
            self._in_gene = True
            self._pending = False
        if not self._in_gene:
            return
        if self._anchor_depth:
            self._anchor_text.append(data)
        else:
            self._tokens.append(data)

    def pairs(self) -> list[tuple[str, str]]:
        self._finish()
        return sorted(self._pairs)


def parse_gene_pairs(page: str) -> list[tuple[str, str]]:
    """Extract visible gene symbol/identifier pairs from BioCyc HTML."""
    for value in (page, unescape(page)):
        parser = _GenePageParser()
        parser.feed(value)
        parser.close()
        pairs = parser.pairs()
        if pairs:
            return pairs
    return []


def _kegg_genes(page: str) -> list[str]:
    return sorted(set(re.findall(r"(?:hsa:)?(\d{3,})", page)))


def _gpr_for_node(node: GeneNode | OrNode | object) -> str:
    if isinstance(node, GeneNode):
        return f"({node.gene})"
    if isinstance(node, OrNode):
        return " or ".join(_gpr_for_node(child) for child in node.children)
    return " and ".join(_gpr_for_node(child) for child in node.children)


def _access_warning(page: str, organization: str) -> str | None:
    title = re.search(r"<title[^>]*>(.*?)</title>", page, re.I | re.S)
    marker = re.sub(r"\s+", " ", title.group(1)).strip().lower() if title else ""
    if marker in {"subscription required", "create account", "biocyc login"}:
        return f"{organization.lower()}cyc-access-required:{marker.replace(' ', '-')}"
    return None


def get_gpr(
    ec_number: str,
    session: Any | None = None,
    *,
    biocyc_client: BioCycClientProtocol | None = None,
    kegg_client: KeggClientProtocol | None = None,
) -> tuple[list[str], str, str, str, str]:
    """Resolve an EC number to a five-field legacy GPR tuple.

    The lookup tries HumanCyc, then MetaCyc, then a KEGG EC page. All network
    access is behind injectable clients, making an empty/static lookup fully
    offline and deterministic.
    """
    evidence = get_gpr_evidence(
        ec_number,
        session,
        biocyc_client=biocyc_client,
        kegg_client=kegg_client,
    )
    symbols = list(evidence["gene_symbols"])
    identifiers = list(evidence["gene_identifiers"])
    if not symbols:
        return [], "", "", "", ""
    structure = evidence.get("sgpr_structure")
    node = (
        sgpr_from_dict(structure)
        if isinstance(structure, dict)
        else OrNode(
            tuple(
                GeneNode(symbol, None, "unknown", str(evidence.get("source", "")))
                for symbol in symbols
            )
        )
    )
    gpr = _gpr_for_node(node)
    stoichiometric_gpr = to_legacy_sgpr(node)
    return symbols, ", ".join(symbols), ", ".join(identifiers), stoichiometric_gpr, gpr


def get_gpr_evidence(
    ec_number: str,
    session: Any | None = None,
    *,
    biocyc_client: BioCycClientProtocol | None = None,
    kegg_client: KeggClientProtocol | None = None,
    kegg_genes: list[str] | None = None,
) -> dict[str, object]:
    """Resolve an EC number and retain source/fallback provenance."""
    from datetime import datetime, timezone

    # Keep the historical positional ``get_gpr(ec, client)`` usage working;
    # ordinary requests sessions do not expose ``get_ec_html``.
    if biocyc_client is None and hasattr(session, "get_ec_html"):
        biocyc_client, session = session, None
    if biocyc_client is None:
        biocyc_client = BioCycClient(session=session)
    pairs: list[tuple[str, str]] = []
    canonical_node = None
    structured = None
    source = ""
    warnings: list[str] = []
    try:
        from .sources.biocyc import biocyc_sgpr_evidence

        structured = biocyc_sgpr_evidence(str(ec_number), biocyc_client=biocyc_client)
        if structured.sgpr is not None:
            canonical_node = structured.sgpr
            source = structured.source
            warnings.extend(structured.warnings)
    except Exception as error:
        warnings.append(f"biocyc-structured-parse-failed:{type(error).__name__}")
    for organization in ("HUMAN", "META"):
        if canonical_node is not None:
            break
        try:
            page = biocyc_client.get_ec_html(ec_number, organization)
            warning = _access_warning(page, organization)
            if warning:
                warnings.append(warning)
            pairs = parse_gene_pairs(page)
        except Exception as error:
            warnings.append(
                f"{organization.lower()}cyc-lookup-failed:{type(error).__name__}"
            )
            pairs = []
        if pairs:
            source = "biocyc" if organization == "HUMAN" else "metacyc"
            warnings.append("biocyc-gene-list-no-complex-structure")
            break

    symbols = list(genes_in_sgpr(canonical_node)) if canonical_node is not None else [
        symbol for symbol, _ in pairs
    ]
    identifiers = [identifier for _, identifier in pairs]
    if canonical_node is not None and not identifiers:
        identifiers = list(structured.identifiers) or list(symbols)
    if not symbols:
        kegg_client = kegg_client or KeggClient()
        try:
            if kegg_genes is None:
                page = kegg_client.get_page(
                    f"https://rest.kegg.jp/link/hsa/ec:{ec_number}"
                )
                if not page:
                    page = kegg_client.get_ec_html(ec_number)
                symbols = _kegg_genes(page)
            else:
                symbols = sorted(set(kegg_genes))
            identifiers = list(symbols)
            source = "kegg" if symbols else ""
        except Exception as error:
            warnings.append(f"kegg-lookup-failed:{type(error).__name__}")
            symbols, identifiers = [], []
    node = canonical_node or (
        OrNode(
            tuple(
                GeneNode(
                    symbol,
                    None,
                    "unknown",
                    source or None,
                    (identifiers[index] if index < len(identifiers) else symbol,),
                )
                for index, symbol in enumerate(symbols)
            )
        )
        if symbols
        else None
    )
    result = {
        "ec": str(ec_number),
        "source": source or "none",
        "retrieved_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source_version": "unknown",
        "parser_version": PARSER_VERSION,
        "gene_symbols": symbols,
        "gene_identifiers": identifiers,
        "candidate_gpr": _gpr_for_node(node) if node is not None else "",
        "candidate_sgpr": to_sgpr(node) if node is not None else "",
        "sgpr_structure": sgpr_to_dict(node) if node is not None else None,
        "legacy_sgpr_structure": (
            sgpr_to_dict(default_sgpr_coefficients(node))
            if node is not None
            else None
        ),
        "legacy_coefficients_defaulted": bool(node),
        "sgpr_status": (
            structured.status
            if canonical_node is not None and structured is not None
            else ("candidate" if symbols else "unresolved")
        ),
        "sgpr_sources": [source] if source else [],
        "sgpr_warnings": warnings or ([]) if symbols else ["no-gpr-evidence"],
        "confidence": (
            structured.confidence
            if canonical_node is not None and structured is not None
            else ("weak" if source == "kegg" else ("candidate" if symbols else "weak"))
        ),
        "status": (
            structured.status
            if canonical_node is not None and structured is not None
            else ("candidate" if symbols else "unresolved")
        ),
        "warnings": warnings or (["no-gpr-evidence"] if not symbols else []),
    }
    return result


def get_sgpr_evidence(
    ec_number: str,
    session: Any | None = None,
    *,
    biocyc_client: BioCycClientProtocol | None = None,
    kegg_client: KeggClientProtocol | None = None,
    kegg_genes: list[str] | None = None,
) -> dict[str, object]:
    """Explicit canonical-evidence API; retained separately from legacy ``get_gpr``."""
    return get_gpr_evidence(
        ec_number,
        session,
        biocyc_client=biocyc_client,
        kegg_client=kegg_client,
        kegg_genes=kegg_genes,
    )


def resolve_sgpr(
    ec_number: str,
    session: Any | None = None,
    *,
    biocyc_client: BioCycClientProtocol | None = None,
    kegg_client: KeggClientProtocol | None = None,
    kegg_genes: list[str] | None = None,
) -> dict[str, object]:
    evidence = get_sgpr_evidence(
        ec_number,
        session,
        biocyc_client=biocyc_client,
        kegg_client=kegg_client,
        kegg_genes=kegg_genes,
    )
    resolution = merge_sgpr_evidence([SgprEvidence.from_mapping(evidence)])
    return {"ec": str(ec_number), **resolution.to_dict()}


__all__ = [
    "PARSER_VERSION",
    "get_gpr",
    "get_gpr_evidence",
    "get_sgpr_evidence",
    "parse_gene_pairs",
    "resolve_sgpr",
]
