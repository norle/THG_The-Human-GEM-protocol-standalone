"""Pure parsers for KEGG database-builder responses."""

from __future__ import annotations

import re

from thg_protocol.services.kegg import KeggClient, KeggClientProtocol


def parse_pathway_links(
    page: str,
    *,
    follow_maps: bool = True,
    client: KeggClientProtocol | None = None,
) -> tuple[list[tuple[str, str]], list[tuple[tuple[str, str], str]]]:
    """Parse compound and reaction links from KGML/KEGG pathway text."""
    kegg = client or KeggClient()
    reactions: set[tuple[str, str]] = set()
    compounds: set[tuple[str, str]] = set()
    for tag in re.findall(r"<entry\b[^>]*>", page):
        entry_type = re.search(r'type="([^"]+)"', tag)
        kind = entry_type.group(1) if entry_type else ""
        names = re.search(r'name="([^"]+)"', tag)
        if not names:
            continue
        for identifier in names.group(1).split():
            if identifier.startswith("rn:"):
                reactions.add((identifier[3:], kind))
            elif identifier.startswith("cpd:"):
                compounds.add((identifier[4:], kind))
    if not reactions:
        pathway_id = _pathway_id(page)
        if pathway_id:
            try:
                flat = kegg.get_page(f"https://rest.kegg.jp/get/{pathway_id}")
            except Exception:
                flat = ""
            reactions.update((value, "") for value in re.findall(r"R\d{5,6}", flat))
    if follow_maps and not reactions:
        for linked_id in set(re.findall(r"path:(hsa\d{5})", page)):
            try:
                linked = kegg.get_page(f"https://rest.kegg.jp/get/{linked_id}/kgml")
            except Exception:
                continue
            nested, _ = parse_pathway_links(linked, follow_maps=False, client=kegg)
            reactions.update(nested)
    compound_links = [
        (item, f"https://www.kegg.jp/dbget-bin/www_bget?{item[0]}")
        for item in sorted(compounds)
    ]
    reaction_links = [
        (item, f"https://www.kegg.jp/dbget-bin/www_bget?{item[0]}")
        for item in sorted(reactions)
    ]
    return compound_links, reaction_links


def _pathway_id(page: str) -> str | None:
    match = re.search(r"path:(hsa\d{5})", page) or re.search(r"\b(hsa\d{5})\b", page)
    return match.group(1) if match else None


def parse_kegg_compound_entry_fields(flat_file_text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    current = ""
    for raw_line in str(flat_file_text).splitlines():
        if raw_line.startswith(" ") and current:
            fields[current] = fields.get(current, "") + " " + raw_line.strip()
            continue
        key, value = raw_line[:12].strip(), raw_line[12:].strip()
        if key:
            current = key
            fields[key] = value
    return fields


def parse_kegg_compound_entry(
    flat_file_text: str,
    identifier: str,
    *,
    client: KeggClientProtocol | None = None,
) -> tuple:
    """Parse a KEGG compound flat-file entry into the legacy tuple shape."""
    fields = parse_kegg_compound_entry_fields(flat_file_text)
    primary_identifier = identifier
    original_formula = fields.get("FORMULA", "").strip()
    formula = original_formula
    name = fields.get("NAME", identifier).split(";", 1)[0].strip()
    same_as = re.search(r"Same as:\s*([CDG]\d+)", fields.get("REMARK", ""))
    if same_as and client is not None:
        primary_identifier = same_as.group(1)
        try:
            primary = client.get_page(
                f"https://rest.kegg.jp/get/{primary_identifier}"
            )
            primary_fields = parse_kegg_compound_entry_fields(primary)
            name = primary_fields.get("NAME", name).split(";", 1)[0].strip()
            formula = primary_fields.get("FORMULA", formula).strip()
        except Exception:
            pass
    links = fields.get("DBLINKS", "")
    reactions = [
        [(f"http://www.genome.jp/entry/{reaction}", reaction)]
        for reaction in fields.get("REACTION", "").split()
        if reaction.startswith("R")
    ]
    return (
        [(primary_identifier, identifier)],
        [(formula, original_formula)],
        reactions,
        [name],
        re.findall(r"PubChem:\s*(\d+)", links),
        re.findall(r"ChEBI:\s*(\d+)", links),
        [],
        [],
        [],
        [],
        "0",
        "",
        "",
        "",
        "",
    )


__all__ = [
    "parse_kegg_compound_entry",
    "parse_kegg_compound_entry_fields",
    "parse_pathway_links",
]
