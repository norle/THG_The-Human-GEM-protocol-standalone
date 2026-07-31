"""Legacy compatibility wrapper for network-component analysis.

The maintained implementation lives in :mod:`thg_protocol.analysis.network`.
This module remains for source-checkout users of the historical import path,
but importing it no longer loads COBRA, NetworkX, or performs filesystem I/O.
Advanced solver cleanup and visualization options are intentionally delegated
to the historical workflow and are not part of the package API.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def find_network_components(
    model: Any,
    cleanup: bool = False,
    cleanup_save_path: str | Path | None = None,
    verbose: bool = True,
    visualize: bool = False,
    viz_output_path: str | Path | None = None,
) -> dict[str, Any]:
    """Analyze connectivity through the maintained package API.

    ``cleanup`` removes isolated metabolites from the returned copy.  When
    ``visualize`` is requested, the maintained JSON component report is
    written to ``viz_output_path``.  These compatibility options are now
    explicit and deterministic; solver-backed cleanup and HTML rendering are
    not performed implicitly.
    """
    from thg_protocol.analysis.network import find_network_components as analyze
    from thg_protocol.analysis.network import write_component_report

    result = analyze(model)
    if cleanup:
        isolated = [
            metabolite
            for metabolite in result["model"].metabolites
            if not metabolite.reactions
        ]
        result["model"].remove_metabolites(isolated, destructive=False)
        result = analyze(result["model"])
    if visualize:
        if viz_output_path is None:
            raise ValueError("viz_output_path is required when visualize=True")
        write_component_report(result, viz_output_path)
    if cleanup and cleanup_save_path is not None:
        from cobra.io import save_json_model, write_sbml_model

        destination = Path(cleanup_save_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.suffix.lower() == ".json":
            save_json_model(result["model"], str(destination))
        else:
            write_sbml_model(result["model"], str(destination))
    if verbose:
        print(
            f"Number of weakly connected components: "
            f"{len(result['components'])}"
        )
    return result


__all__ = ["find_network_components"]
