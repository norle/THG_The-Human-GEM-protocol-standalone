"""Compatibility exports for package-owned GPR lookup and parsing."""

from __future__ import annotations

from typing import Any

from functions.gpr.auth_gpr import setup_biocyc_session
from thg_protocol.gpr.lookup import get_gpr, parse_gene_pairs
from thg_protocol.services.biocyc import BioCycClient, BioCycClientProtocol


def get_html(
    request_url: str,
    session: Any | None = None,
    timeout: int = 30,
    *,
    biocyc_client: BioCycClientProtocol | None = None,
) -> str:
    del timeout
    client = biocyc_client or BioCycClient(session=session)
    return client.get_page(request_url)


def getGPR(
    ec_number: str,
    session: Any | None = None,
    *,
    biocyc_client: BioCycClientProtocol | None = None,
    kegg_client=None,
):
    return get_gpr(
        ec_number,
        session,
        biocyc_client=biocyc_client,
        kegg_client=kegg_client,
    )


def pattern_match_org(page: str, org: str = ""):
    del org
    return parse_gene_pairs(page)


def match_biocyc_page(page: str, humancyc: bool = False):
    del humancyc
    return parse_gene_pairs(page)

__all__ = [
    "getGPR",
    "get_html",
    "match_biocyc_page",
    "pattern_match_org",
    "parse_gene_pairs",
    "setup_biocyc_session",
]
