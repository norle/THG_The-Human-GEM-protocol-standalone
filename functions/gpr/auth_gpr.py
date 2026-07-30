"""Compatibility exports for the package-owned GPR service boundary."""

from __future__ import annotations

import os
import re
from typing import Any

from thg_protocol.gpr.lookup import get_gpr, parse_gene_pairs
from thg_protocol.services.biocyc import BioCycClient, BioCycClientProtocol
from thg_protocol.services.kegg import KeggClient, KeggClientProtocol


def read_env_biocyc() -> tuple[str, str]:
    """Read BioCyc credentials from environment variables."""
    return os.environ["BIOCYC_EMAIL"], os.environ["BIOCYC_PASSWORD"]


def setup_biocyc_session(email: str | None = None, password: str | None = None):
    """Create and authenticate a requests session when credentials exist."""
    import requests

    email, password = (
        (email, password) if email is not None and password is not None else read_env_biocyc()
    )
    session = requests.Session()
    session.post(
        "https://websvc.biocyc.org/credentials/login/",
        data={"email": email, "password": password},
    )
    return session


def get_ecnumber_biocyc_html(
    ec_number: str,
    session: Any | None = None,
    org: str = "META",
    *,
    biocyc_client: BioCycClientProtocol | None = None,
) -> str:
    client = biocyc_client or BioCycClient(session=session)
    return client.get_ec_html(ec_number, org=org)


def get_html(
    request_url: str,
    session: Any | None = None,
    *,
    biocyc_client: BioCycClientProtocol | None = None,
) -> str:
    client = biocyc_client or BioCycClient(session=session)
    return client.get_page(request_url)


def getGPR(
    ec_number: str,
    session: Any | None = None,
    *,
    kegg_client: KeggClientProtocol | None = None,
    biocyc_client: BioCycClientProtocol | None = None,
):
    return get_gpr(
        ec_number,
        session,
        biocyc_client=biocyc_client,
        kegg_client=kegg_client,
    )


def _fetch_kegg_from_ec_html(
    ec_number: str, *, kegg_client: KeggClientProtocol | None = None
):
    client = kegg_client or KeggClient()
    page = client.get_page(f"https://rest.kegg.jp/link/hsa/ec:{ec_number}")
    if not page:
        page = client.get_ec_html(ec_number)
    identifiers = sorted(set(re.findall(r"hsa:(\d+)", page)))
    genes = [f"G{identifier}" for identifier in identifiers]
    return identifiers, genes, identifiers, "", ""


def pattern_match_org(page: str, org: str = ""):
    del org
    return parse_gene_pairs(page)


def match_biocyc_page(page: str, humancyc: bool = False):
    del humancyc
    return parse_gene_pairs(page)


__all__ = [
    "_fetch_kegg_from_ec_html",
    "getGPR",
    "get_ecnumber_biocyc_html",
    "get_html",
    "match_biocyc_page",
    "pattern_match_org",
    "read_env_biocyc",
    "setup_biocyc_session",
]
