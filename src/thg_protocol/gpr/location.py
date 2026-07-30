"""Injectable subcellular-location resolution for GPR workflows."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from thg_protocol.services.ensembl import EnsemblClientProtocol
from thg_protocol.services.location import LocationClient, LocationClientProtocol


_LOCATION_PATTERNS = (
    ("Mitochondria", re.compile(r"mitochondri", re.I)),
    ("Nucleus", re.compile(r"nucle(?:us|ar)", re.I)),
    ("Endoplasmic reticulum", re.compile(r"endoplasmic\s+reticulum|ER", re.I)),
    ("Golgi apparatus", re.compile(r"golgi", re.I)),
    ("Peroxisome", re.compile(r"peroxisom", re.I)),
    ("Plasma membrane", re.compile(r"plasma\s+membrane", re.I)),
    ("Cytosol", re.compile(r"cytosol|cytoplasm", re.I)),
)


def _location_from_page(page: str, allowed: set[str]) -> str:
    for name, pattern in _LOCATION_PATTERNS:
        if name in allowed and pattern.search(page):
            return name
    return "Cytosol" if "Cytosol" in allowed else next(iter(allowed), "Cytosol")


def resolve_locations(
    gpr: str,
    gene_names: list[str] | tuple[str, ...],
    gene_ids: list[str] | tuple[str, ...],
    *,
    allowed_locations: set[str] | None = None,
    location_client: LocationClientProtocol | None = None,
    ensembl_client: EnsemblClientProtocol | None = None,
    session: Any | None = None,
    location_dict_file: str | Path | None = None,
) -> tuple[dict[str, str], dict[str, str], dict[str, str], dict[str, list[str]]]:
    """Resolve genes to locations and return the historical four dictionaries.

    Pages and Ensembl identifiers are optional. When no page matches, genes are
    assigned to Cytosol. ``location_dict_file`` may contain a pickled mapping
    whose values define the allowed location names; it is read only when
    explicitly supplied.
    """
    del ensembl_client
    allowed = set(allowed_locations or {"Cytosol"})
    if location_dict_file is not None:
        import pickle

        with Path(location_dict_file).open("rb") as handle:
            loaded = pickle.load(handle)
        if isinstance(loaded, dict) and loaded:
            allowed = {str(value) for value in loaded.values()}
    client = location_client or LocationClient(session=session)
    names = list(gene_names)
    identifiers = list(gene_ids)
    rule_stoich: dict[str, str] = {}
    rule_plain: dict[str, str] = {}
    rule_ensembl: dict[str, str] = {}
    gene_map: dict[str, list[str]] = {}
    for index, gene in enumerate(names):
        identifier = identifiers[index] if index < len(identifiers) else gene
        page = ""
        try:
            page = client.get_page(
                f"https://www.uniprot.org/uniprotkb/{identifier}_HUMAN.txt"
            )
        except Exception:
            page = ""
        location = _location_from_page(page, allowed)
        rule_stoich[location] = (
            f"{rule_stoich[location]} or ({gene}*1)"
            if location in rule_stoich
            else f"({gene}*1)"
        )
        rule_plain[location] = (
            f"{rule_plain[location]} or ({gene})"
            if location in rule_plain
            else f"({gene})"
        )
        rule_ensembl[location] = (
            f"{rule_ensembl[location]} or ({identifier})"
            if location in rule_ensembl
            else f"({identifier})"
        )
        gene_map.setdefault(identifier, []).append(gene)
    return rule_stoich, rule_plain, rule_ensembl, gene_map


__all__ = ["resolve_locations"]
