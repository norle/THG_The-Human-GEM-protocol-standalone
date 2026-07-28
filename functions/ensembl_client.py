"""Compatibility wrapper for the package-owned Ensembl client."""

from __future__ import annotations

from collections.abc import Iterable

from thg_protocol.services.ensembl import EnsemblClient


def fetch_ensembl_annotations(
    gene_identifiers: Iterable[str],
    batch_size: int = 50,
    max_workers: int = 8,
    timeout: int = 5,
):
    """Fetch annotations using the package client.

    ``batch_size`` and ``max_workers`` are retained for legacy call
    compatibility. Requests are now serialized through the client so retry,
    timeout, caching, and normalization have one owner.
    """
    del batch_size, max_workers
    annotations = EnsemblClient(timeout=timeout).annotate(gene_identifiers)
    return {identifier: annotation.as_dict() for identifier, annotation in annotations.items()}
