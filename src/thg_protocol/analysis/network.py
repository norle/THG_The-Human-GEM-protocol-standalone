"""Network-component analysis for COBRA models."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:  # Keep package imports and CLI help safe in a no-dependencies wheel check.
    import networkx as nx
except ImportError:  # pragma: no cover - exercised by clean-wheel smoke tests
    nx = None  # type: ignore[assignment]


def find_network_components(model: Any) -> dict[str, Any]:
    """Return weakly connected metabolite/reaction components.

    The input model is copied before analysis. The returned graph is directed:
    consumed metabolites point to reactions and reactions point to products.
    Solver-backed blocked-reaction cleanup and HTML visualization remain
    separate legacy operations.
    """
    if nx is None:
        raise RuntimeError("Network analysis requires the 'networkx' dependency")

    model_copy = model.copy()
    graph = nx.DiGraph()
    metabolite_ids = {("metabolite", met.id) for met in model_copy.metabolites}
    reaction_ids = {("reaction", reaction.id) for reaction in model_copy.reactions}

    for metabolite in model_copy.metabolites:
        graph.add_node(("metabolite", metabolite.id), bipartite="metabolite")
    for reaction in model_copy.reactions:
        reaction_node = ("reaction", reaction.id)
        graph.add_node(reaction_node, bipartite="reaction")
        for metabolite, coefficient in reaction.metabolites.items():
            metabolite_node = ("metabolite", metabolite.id)
            if coefficient < 0:
                graph.add_edge(metabolite_node, reaction_node)
            elif coefficient > 0:
                graph.add_edge(reaction_node, metabolite_node)

    components = sorted(nx.weakly_connected_components(graph), key=len, reverse=True)
    component_info = []
    compartments = {
        ("metabolite", metabolite.id): getattr(metabolite, "compartment", None)
        for metabolite in model_copy.metabolites
    }
    reaction_compartments = {
        ("reaction", reaction.id): set(getattr(reaction, "compartments", ()))
        for reaction in model_copy.reactions
    }
    for index, component in enumerate(components, start=1):
        reaction_count = len(component & reaction_ids)
        component_compartments = {
            compartments[node]
            for node in component & metabolite_ids
            if compartments[node]
        }
        for reaction_node in component & reaction_ids:
            component_compartments.update(reaction_compartments[reaction_node])
        component_info.append(
            {
                "index": index,
                "total_nodes": len(component),
                "reaction_count": reaction_count,
                "metabolite_count": len(component) - reaction_count,
                "compartments": sorted(component_compartments),
                "nodes": sorted(component),
            }
        )

    largest = components[0] if components else set()
    return {
        "model": model_copy,
        "graph": graph,
        "components": components,
        "largest_component": largest,
        "is_fully_connected": len(largest) == graph.number_of_nodes(),
        "component_info": component_info,
    }


def write_component_report(results: dict[str, Any], output_path: str | Path) -> Path:
    """Write JSON-serializable component information to ``output_path``."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "is_fully_connected": results["is_fully_connected"],
        "component_info": results["component_info"],
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


__all__ = ["find_network_components", "write_component_report"]
