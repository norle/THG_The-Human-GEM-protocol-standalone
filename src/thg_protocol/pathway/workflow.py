"""Import-safe pathway implementation workflow for JSON model files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .core import (
    add_compartment,
    create_compartment_metabolites,
    create_compartment_reactions,
)


def implement_pathway(
    model: dict[str, Any],
    config: dict[str, Any],
    id_database: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Implement configured pathway components in a JSON model mapping.

    The input ``model`` is mutated in place and returned in the result. The
    result contains the model and counts of newly added metabolites,
    reactions, and compartments. No files, network services, or global state
    are accessed.
    """
    compartments = config.get("compartments", [])
    abbreviation_map: dict[str, str] = {}
    resolved: list[tuple[str, str]] = []

    for compartment in compartments:
        config_abbreviation = compartment["abbreviation"]
        name = compartment["name"]
        model_abbreviation = config_abbreviation
        for abbreviation, existing_name in model.get("compartments", {}).items():
            if abbreviation.lower() == config_abbreviation.lower() or (
                isinstance(existing_name, str) and existing_name.lower() == name.lower()
            ):
                model_abbreviation = abbreviation
                break
        abbreviation_map[config_abbreviation] = model_abbreviation
        resolved.append((model_abbreviation, name))

    original_compartments = len(model.get("compartments", {}))
    for abbreviation, name in resolved:
        add_compartment(model, abbreviation, name)

    pathway_name = (
        str(config.get("pathway_name", "")).replace(" ", "_").replace("-", "_")
    )
    candidate_keys = [
        f"{pathway_name}_specific" if pathway_name else "",
        "pathway_specific",
        "cytoskeleton_specific",
        "glycocalyx_specific",
    ]
    metabolite_keys = set(config.get("metabolites", {}))

    def choose_key() -> str | tuple[str, str] | None:
        for key in candidate_keys:
            if key and (key in config or key in metabolite_keys):
                return ("metabolites", key) if key in metabolite_keys else key
        if "metabolites" in config and isinstance(config["metabolites"], dict):
            return "metabolites"
        return None

    pathway_key = choose_key()
    metabolites_added = 0
    for abbreviation, _ in resolved:
        metabolites_added += create_compartment_metabolites(
            model,
            id_database,
            abbreviation,
            config,
            pathway_key,
            abbreviation_map,
        )

    reactions_added = 0
    for abbreviation, _ in resolved:
        reactions_added += create_compartment_reactions(
            model, id_database, abbreviation, config, abbreviation_map
        )

    return {
        "model": model,
        "compartments_added": (
            len(model.get("compartments", {})) - original_compartments
        ),
        "metabolites_added": metabolites_added,
        "reactions_added": reactions_added,
    }


def implement_pathway_files(
    model_path: str | Path,
    config_path: str | Path,
    id_database_path: str | Path,
    output_path: str | Path,
) -> dict[str, Any]:
    """Load JSON inputs, run
    [`implement_pathway`][thg_protocol.pathway.workflow.implement_pathway], and write
    the result."""
    paths = [Path(model_path), Path(config_path), Path(id_database_path)]
    with paths[0].open() as handle:
        model = json.load(handle)
    with paths[1].open() as handle:
        config = json.load(handle)
    with paths[2].open() as handle:
        id_database = json.load(handle)

    result = implement_pathway(model, config, id_database)
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w") as handle:
        json.dump(result["model"], handle, indent=2)
        handle.write("\n")
    return result
