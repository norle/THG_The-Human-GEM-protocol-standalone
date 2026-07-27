"""Pathway helper APIs exposed from the package namespace."""

from __future__ import annotations

import copy
import re
from typing import Any

__all__ = [
    "add_compartment",
    "check_pathway_exists",
    "create_compartment_metabolites",
    "create_compartment_reactions",
    "build_reaction_from_config",
    "find_metabolite_by_annotation",
    "find_metabolite_robust",
    "get_next_metabolite_id",
    "get_next_reaction_id",
    "parse_reaction_equation",
    "parse_universal_reaction",
    "select_pathway_metabolites",
    "substitute_compartment_abbreviations",
]


def substitute_compartment_abbreviations(
    equation: str, abbrev_map: dict[str, str] | None = None
) -> str:
    """Replace bracketed config compartments with model abbreviations."""
    if not abbrev_map:
        return equation
    for config_abbrev, model_abbrev in abbrev_map.items():
        if config_abbrev != model_abbrev:
            equation = equation.replace(f"[{config_abbrev}]", f"[{model_abbrev}]")
    return equation


def select_pathway_metabolites(
    config: dict[str, Any],
    pathway_key: str | tuple[str, str],
    compartment: str,
    abbrev_map: dict[str, str] | None = None,
) -> dict[str, dict[str, Any]]:
    """Select configured metabolite definitions for one model compartment."""
    if isinstance(pathway_key, tuple):
        parent_key, child_key = pathway_key
        definitions = config.get(parent_key, {}).get(child_key)
    else:
        definitions = config.get("metabolites", {}).get(pathway_key)
        if definitions is None:
            definitions = config.get(pathway_key)
    if not isinstance(definitions, dict):
        return {}

    return {
        name: data
        for name, data in definitions.items()
        if isinstance(data, dict)
        and (abbrev_map or {}).get(
            data.get("compartment", compartment), data.get("compartment", compartment)
        )
        == compartment
    }


def build_reaction_from_config(
    reaction_config: dict[str, Any], reaction_data: dict[str, Any]
) -> dict[str, Any]:
    """Build a serializable reaction dictionary from parsed data and config."""
    reaction = {
        "id": reaction_config.get("id"),
        "name": reaction_config.get("name", ""),
        "metabolites": reaction_data["metabolites"],
        "lower_bound": reaction_config.get("lower_bound", 0.0),
        "upper_bound": reaction_config.get("upper_bound", 1000.0),
        "gene_reaction_rule": reaction_config.get("gpr", ""),
        "subsystem": reaction_config.get("subsystem", ""),
    }
    if "notes" in reaction_config or "description" in reaction_config:
        reaction["notes"] = {
            "description": reaction_config.get(
                "description", reaction_config.get("notes", "")
            )
        }

    annotation = {}
    if reaction_config.get("ec"):
        annotation["ec-code"] = reaction_config["ec"]
    if "sbo" in reaction_config:
        annotation["sbo"] = reaction_config["sbo"]
    if annotation:
        reaction["annotation"] = annotation
    return reaction


def parse_reaction_equation(equation: str) -> dict[str, Any] | None:
    """Parse a universal reaction equation without resolving metabolites."""
    if "-->" in equation:
        arrow = "-->"
        reversible = False
    elif "<=>" in equation:
        arrow = "<=>"
        reversible = True
    else:
        return None

    parts = equation.split(arrow)
    if len(parts) != 2:
        return None

    terms: list[dict[str, Any]] = []
    term_pattern = re.compile(r"^(?:(\d+(?:\.\d+)?)\s+)?(.+?)\[(\w+)\]$")
    for side, sign in ((parts[0], -1.0), (parts[1], 1.0)):
        # Splitting only on a spaced plus preserves names such as H+.
        for raw_term in side.split(" + "):
            term = raw_term.strip()
            if not term:
                continue
            match = term_pattern.match(term)
            if not match:
                continue
            stoich_text, name, compartment = match.groups()
            name = name.strip()
            compartment = compartment.strip()
            if not name or not compartment:
                continue
            stoich = float(stoich_text) if stoich_text else 1.0
            terms.append(
                {
                    "name": name,
                    "compartment": compartment,
                    "stoich": sign * stoich,
                }
            )

    if not terms:
        return None
    return {"terms": terms, "reversible": reversible}


def parse_universal_reaction(
    equation: str,
    model: dict[str, Any],
    id_database: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    """Resolve a universal reaction equation into model metabolite IDs."""
    parsed = parse_reaction_equation(equation)
    if parsed is None:
        return None

    metabolites: dict[str, float] = {}
    for term in parsed["terms"]:
        metabolite = find_metabolite_robust(
            model,
            term["name"],
            id_database,
            term["compartment"],
            auto_create=True,
        )
        if metabolite is None:
            continue
        metabolite_id = metabolite["id"]
        metabolites[metabolite_id] = metabolites.get(metabolite_id, 0.0) + term[
            "stoich"
        ]

    if not metabolites:
        return None
    return {"metabolites": metabolites, "reversible": parsed["reversible"]}


def create_compartment_metabolites(
    model: dict[str, Any],
    id_database: dict[str, dict[str, Any]],
    compartment_abbrev: str,
    config: dict[str, Any],
    pathway_key: str | tuple[str, str] | None = None,
    abbrev_map: dict[str, str] | None = None,
) -> int:
    """Create configured metabolites in a model dictionary.

    The model is mutated in place.  Existing metabolites are preserved and
    the return value is the number of newly appended metabolites.  Missing
    base metabolites are skipped, matching the legacy workflow behavior.
    """
    new_metabolites: list[dict[str, Any]] = []
    existing_ids = {metabolite["id"] for metabolite in model.get("metabolites", [])}

    targets = config.get("metabolites", {}).get("targets", {})
    if targets:
        needed_targets: set[str] = set()
        for reaction in config.get("reactions", []):
            parsed = parse_reaction_equation(reaction.get("equation", ""))
            if parsed:
                needed_targets.update(
                    term["name"]
                    for term in parsed["terms"]
                    if term["compartment"] == compartment_abbrev
                    and term["name"] in targets
                )
        for name in needed_targets:
            base = find_metabolite_robust(model, name, id_database, "c")
            if not base:
                continue
            target_id = f"{get_metabolite_id_base(base['id'])}{compartment_abbrev}"
            if target_id not in existing_ids:
                copied = copy.deepcopy(base)
                copied["id"] = target_id
                copied["compartment"] = compartment_abbrev
                new_metabolites.append(copied)
                existing_ids.add(target_id)

    if pathway_key:
        definitions = select_pathway_metabolites(
            config, pathway_key, compartment_abbrev, abbrev_map
        )
        next_id = int(get_next_metabolite_id(model)[3:8])
        for name, data in definitions.items():
            source_compartment = data.get("compartment", compartment_abbrev)
            target_compartment = (abbrev_map or {}).get(
                source_compartment, source_compartment
            )
            metabolite_id = f"MAM{next_id:05d}{target_compartment}"
            next_id += 1
            if metabolite_id in existing_ids or any(
                metabolite.get("name") == name
                and metabolite.get("compartment") == target_compartment
                for metabolite in model.get("metabolites", []) + new_metabolites
            ):
                continue
            annotation = copy.deepcopy(data.get("annotation", {}))
            for key in (
                "bigg.metabolite", "chebi", "hmdb", "inchi", "inchikey",
                "kegg.compound", "metanetx.chemical", "pubchem.compound",
                "uniprot", "vmhmetabolite", "hgnc", "ensembl",
            ):
                if data.get(key):
                    annotation[key] = data[key]
            if data.get("sbo"):
                annotation["sbo"] = data["sbo"]
            metabolite = {
                "id": metabolite_id,
                "name": name,
                "compartment": target_compartment,
                "charge": data.get("charge", 0),
                "formula": data.get("formula", ""),
            }
            if annotation:
                metabolite["annotation"] = annotation
            new_metabolites.append(metabolite)
            existing_ids.add(metabolite_id)

    model.setdefault("metabolites", []).extend(new_metabolites)
    return len(new_metabolites)


def create_compartment_reactions(
    model: dict[str, Any],
    id_database: dict[str, dict[str, Any]],
    compartment_abbrev: str,
    config: dict[str, Any],
    abbrev_map: dict[str, str] | None = None,
) -> int:
    """Create configured reactions in a model dictionary and return its count."""
    del compartment_abbrev  # retained for compatibility with the workflow API
    new_reactions: list[dict[str, Any]] = []
    existing_ids = {reaction["id"] for reaction in model.get("reactions", [])}
    for reaction_config in config.get("reactions", []):
        reaction_id = reaction_config.get("id") or get_next_reaction_id(
            {**model, "reactions": model.get("reactions", []) + new_reactions}
        )
        if reaction_id in existing_ids:
            continue
        equation = substitute_compartment_abbreviations(
            reaction_config.get("equation", ""), abbrev_map
        )
        reaction_data = parse_universal_reaction(equation, model, id_database)
        if not reaction_data:
            continue
        config_entry = {**reaction_config, "id": reaction_id}
        new_reactions.append(build_reaction_from_config(config_entry, reaction_data))
        existing_ids.add(reaction_id)
    model.setdefault("reactions", []).extend(new_reactions)
    return len(new_reactions)


def find_metabolite_by_formula_in_model(
    model: dict[str, Any], formula: str | None, compartment: str | None = None
) -> dict[str, Any] | None:
    """Find the first metabolite with a matching formula and optional compartment."""
    if not formula:
        return None

    for metabolite in model.get("metabolites", []):
        if metabolite.get("formula", "") != formula:
            continue
        if compartment is None or metabolite.get("compartment", "") == compartment:
            return metabolite

    return None


def get_metabolite_id_base(metabolite_id: str) -> str:
    """Return a metabolite identifier without its compartment suffix."""
    match = re.match(r"^([A-Z]+\d+)", metabolite_id)
    if match:
        return match.group(1)
    return metabolite_id


def get_next_metabolite_id(model: dict[str, Any]) -> str:
    """Get the next available metabolite ID in the MAM##### format."""
    max_id = 0
    for metabolite in model["metabolites"]:
        metabolite_id = metabolite["id"]
        if metabolite_id.startswith("MAM") and len(metabolite_id) >= 8:
            try:
                max_id = max(max_id, int(metabolite_id[3:8]))
            except ValueError:
                continue
    return f"MAM{max_id + 1:05d}"


def get_next_reaction_id(model: dict[str, Any]) -> str:
    """Get the next available reaction ID in the MAR##### format."""
    max_id = 0
    for reaction in model["reactions"]:
        reaction_id = reaction["id"]
        if reaction_id.startswith("MAR") and len(reaction_id) >= 8:
            try:
                max_id = max(max_id, int(reaction_id[3:8]))
            except ValueError:
                continue
    return f"MAR{max_id + 1:05d}"


def find_metabolite_by_annotation(
    model: dict[str, Any],
    metabolite_name: str,
    id_database: dict[str, dict[str, Any]],
    compartment: str = "c",
) -> dict[str, Any] | None:
    """Find a metabolite by matching its annotations against an ID database."""
    if metabolite_name not in id_database:
        return None

    known_ids = id_database[metabolite_name]
    priority_weights = {
        "inchikey": 10,
        "inchi": 9,
        "chebi": 8,
        "kegg.compound": 7,
        "bigg.metabolite": 6,
        "pubchem.compound": 5,
        "vmhmetabolite": 4,
        "metanetx.chemical": 3,
    }

    best_match = None
    best_score = 0

    for metabolite in model["metabolites"]:
        if metabolite["compartment"] != compartment:
            continue
        if not metabolite.get("annotation"):
            continue

        match_count = 0
        score = 0
        for key, value in metabolite["annotation"].items():
            if key in known_ids and value == known_ids[key]:
                match_count += 1
                score += priority_weights.get(key, 1)

        if match_count >= 2 and score > best_score:
            best_match = metabolite
            best_score = score

    return best_match


def create_metabolite_in_new_compartment(
    model: dict[str, Any],
    source_metabolite: dict[str, Any],
    target_compartment: str,
) -> str:
    """Create a copy of a metabolite in a different compartment."""
    base_id = get_metabolite_id_base(source_metabolite["id"])
    new_id = f"{base_id}{target_compartment}"

    if any(metabolite["id"] == new_id for metabolite in model.get("metabolites", [])):
        return new_id

    new_metabolite = {
        "id": new_id,
        "name": source_metabolite.get("name", ""),
        "compartment": target_compartment,
        "formula": source_metabolite.get("formula", ""),
        "charge": source_metabolite.get("charge", 0),
        "annotation": copy.deepcopy(source_metabolite.get("annotation", {})),
    }
    model["metabolites"].append(new_metabolite)
    return new_id


def find_metabolite_robust(
    model: dict[str, Any],
    metabolite_name: str,
    id_database: dict[str, dict[str, Any]],
    compartment: str = "c",
    auto_create: bool = False,
) -> dict[str, Any] | None:
    """Find a metabolite by exact, annotation, substring, or formula matching."""
    for metabolite in model["metabolites"]:
        if (
            metabolite["name"] == metabolite_name
            and metabolite["compartment"] == compartment
        ):
            return metabolite

    for metabolite in model["metabolites"]:
        if (
            metabolite["name"].lower() == metabolite_name.lower()
            and metabolite["compartment"] == compartment
        ):
            return metabolite

    metabolite = find_metabolite_by_annotation(
        model, metabolite_name, id_database, compartment
    )
    if metabolite:
        return metabolite

    for metabolite in model["metabolites"]:
        if (
            metabolite_name.lower() in metabolite["name"].lower()
            and metabolite["compartment"] == compartment
        ):
            return metabolite

    if not auto_create:
        return None

    source_metabolite = None
    formula = None
    for metabolite in model["metabolites"]:
        if metabolite["name"].lower() == metabolite_name.lower():
            source_metabolite = metabolite
            formula = metabolite.get("formula")
            if formula:
                break

    if not formula and metabolite_name in id_database:
        database_entry = id_database[metabolite_name]
        if "id" in database_entry:
            base_id = get_metabolite_id_base(database_entry["id"])
            for metabolite in model["metabolites"]:
                if get_metabolite_id_base(metabolite["id"]) == base_id:
                    source_metabolite = metabolite
                    formula = metabolite.get("formula")
                    if formula:
                        break

    if not formula:
        return None

    existing = find_metabolite_by_formula_in_model(model, formula, compartment)
    if existing:
        return existing

    if source_metabolite:
        new_id = create_metabolite_in_new_compartment(
            model, source_metabolite, compartment
        )
        return next(
            (
                metabolite
                for metabolite in model["metabolites"]
                if metabolite["id"] == new_id
            ),
            None,
        )

    return None


def add_compartment(
    model: dict[str, Any], compartment_abbrev: str, compartment_name: str
) -> tuple[dict[str, Any], str, bool]:
    """Add a compartment to a model dictionary."""
    already_existed = False
    if compartment_abbrev in model["compartments"]:
        already_existed = True
    else:
        model["compartments"][compartment_abbrev] = compartment_name

    return model, compartment_abbrev, already_existed


def check_pathway_exists(
    model: dict[str, Any], compartment_abbrev: str, pathway_name: str | None = None
) -> dict[str, Any]:
    """Return counts and IDs for a compartment/pathway in a model dictionary."""
    result: dict[str, Any] = {
        "has_compartment": False,
        "compartment": None,
        "metabolite_count": 0,
        "reaction_count": 0,
        "metabolites": [],
        "reactions": [],
    }

    if compartment_abbrev in model.get("compartments", {}):
        result["has_compartment"] = True
        result["compartment"] = model["compartments"][compartment_abbrev]

    for metabolite in model.get("metabolites", []):
        if metabolite.get("compartment") == compartment_abbrev:
            result["metabolites"].append(metabolite["id"])
            result["metabolite_count"] += 1

    metabolites_by_id = {
        metabolite["id"]: metabolite for metabolite in model.get("metabolites", [])
    }
    for reaction in model.get("reactions", []):
        involves_compartment = any(
            metabolites_by_id.get(metabolite_id, {}).get("compartment")
            == compartment_abbrev
            for metabolite_id in reaction.get("metabolites", {})
        )
        if involves_compartment:
            result["reactions"].append(reaction["id"])
            result["reaction_count"] += 1

    return result
