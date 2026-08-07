"""Injectable BioCyc/KEGG GPR lookup workflow."""

from __future__ import annotations

import re
from typing import Any

from thg_protocol.services.biocyc import BioCycClient, BioCycClientProtocol
from thg_protocol.services.kegg import KeggClient, KeggClientProtocol


def parse_gene_pairs(page: str) -> list[tuple[str, str]]:
    """Extract gene symbol/identifier pairs from common BioCyc HTML forms."""
    patterns = (
        r"<b>Gene:</b>\s*([A-Za-z0-9_-]+).*?([A-Za-z0-9:_-]+)<br>",
        r"&lt;b&gt;Gene:&lt;/b&gt;\s*([A-Za-z0-9_-]+)\s+([A-Za-z0-9:_-]+)",
    )
    pairs: set[tuple[str, str]] = set()
    for pattern in patterns:
        pairs.update(
            (symbol.strip(), identifier.strip())
            for symbol, identifier in re.findall(pattern, page, re.I)
        )
    return sorted(pairs)


def _kegg_genes(page: str) -> list[str]:
    return sorted(set(re.findall(r"(?:hsa:)?(\d{3,})", page)))


def _safe_gpr(symbols: list[str]) -> str:
    return " or ".join(f"({symbol})" for symbol in symbols)


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
    if biocyc_client is None:
        biocyc_client = BioCycClient(session=session)
    pairs: list[tuple[str, str]] = []
    for organization in ("HUMAN", "META"):
        try:
            pairs = parse_gene_pairs(biocyc_client.get_ec_html(ec_number, organization))
        except Exception:
            pairs = []
        if pairs:
            break

    symbols = [symbol for symbol, _ in pairs]
    identifiers = [identifier for _, identifier in pairs]
    if not symbols:
        kegg_client = kegg_client or KeggClient()
        try:
            page = kegg_client.get_page(f"https://rest.kegg.jp/link/hsa/ec:{ec_number}")
            if not page:
                page = kegg_client.get_ec_html(ec_number)
            symbols = _kegg_genes(page)
            identifiers = list(symbols)
        except Exception:
            symbols, identifiers = [], []
    if not symbols:
        return [], "", "", "", ""
    gpr = _safe_gpr(symbols)
    stoichiometric_gpr = " or ".join(f"({symbol}*1)" for symbol in symbols)
    return symbols, ", ".join(symbols), ", ".join(identifiers), stoichiometric_gpr, gpr


__all__ = ["get_gpr", "parse_gene_pairs"]
