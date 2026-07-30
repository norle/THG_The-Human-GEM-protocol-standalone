"""Compatibility adapter for package-owned location resolution."""

from __future__ import annotations

from typing import Any

from thg_protocol.gpr.location import resolve_locations
from thg_protocol.services.location import LocationClient, LocationClientProtocol


def get_html(
    request_url: str,
    session: Any | None = None,
    *,
    location_client: LocationClientProtocol | None = None,
) -> str:
    client = location_client or LocationClient(session=session)
    return client.get_page(request_url)


def create_dict(gene, value):
    """Preserve the small historical gene cache helper."""
    cache = getattr(create_dict, "cache", {})
    if gene and value:
        cache[gene] = value
    result = cache.get(gene, "") if gene and not value else ""
    create_dict.cache = cache
    return cache, result


def multiple_replace_new(dictionary, text):
    value = text.strip().lower()
    return dictionary.get(value, value)


def getLocationnew(
    gpr,
    genelist1,
    genelist2,
    impose_locations,
    location_dict_file,
    session=None,
    ensembl_cache=None,
    ensembl_client=None,
    *,
    location_client: LocationClientProtocol | None = None,
):
    del impose_locations, ensembl_cache
    return resolve_locations(
        gpr,
        list(genelist1 or []),
        list(genelist2 or []),
        location_client=location_client,
        ensembl_client=ensembl_client,
        session=session,
        location_dict_file=location_dict_file,
    )


getLocation = getLocationnew

__all__ = [
    "create_dict",
    "getLocation",
    "getLocationnew",
    "get_html",
    "multiple_replace_new",
]
