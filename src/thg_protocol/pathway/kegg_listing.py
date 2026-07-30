"""KEGG pathway reaction listing workflow."""

from __future__ import annotations

import re
from pathlib import Path

from thg_protocol.services.kegg import KeggClient, KeggClientProtocol


def _reaction_ids(kgml: str) -> list[str]:
    values: list[str] = []
    for names in re.findall(r'name="([^"]+)"', kgml):
        values.extend(re.findall(r"rn:(R\d{5})", names))
    return list(dict.fromkeys(values))


def list_pathway_reactions(
    pathways_path: str | Path,
    output_path: str | Path,
    *,
    limit: int | None = 5,
    client: KeggClientProtocol | None = None,
) -> Path:
    """Write pathway IDs, names, and reaction IDs to a TSV file."""
    if limit is not None and limit < 0:
        raise ValueError("limit must be non-negative or None")
    kegg = client or KeggClient()
    source = Path(pathways_path)
    destination = Path(output_path)
    rows = [
        line.split("\t", 1)
        for line in source.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    selected = rows if limit is None else rows[:limit]
    output: list[str] = ["#pathway_id\tpathway_name\treaction_ids"]
    for row in selected:
        if len(row) < 2:
            continue
        pathway_id, pathway_name = row[0].strip(), row[1].strip()
        page = kegg.get_page(f"https://rest.kegg.jp/get/{pathway_id}/kgml")
        reaction_ids = _reaction_ids(page)
        if not reaction_ids:
            linked = set(re.findall(r'name="path:(hsa\d{5})"', page))
            for linked_id in sorted(linked - {pathway_id}):
                reaction_ids.extend(
                    _reaction_ids(
                        kegg.get_page(f"https://rest.kegg.jp/get/{linked_id}/kgml")
                    )
                )
            reaction_ids = list(dict.fromkeys(reaction_ids))
        output.append(f"{pathway_id}\t{pathway_name}\t{' '.join(reaction_ids)}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text("\n".join(output) + "\n", encoding="utf-8")
    return destination


__all__ = ["list_pathway_reactions"]
