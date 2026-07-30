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

    ``cleanup`` and ``visualize`` are retained for call compatibility. They
    raise a clear error instead of silently running the old solver-backed and
    HTML side effects; callers should use explicit package workflows for those
    operations.
    """
    if cleanup or visualize:
        raise NotImplementedError(
            "cleanup/visualize are legacy options; use "
            "thg_protocol.analysis.network for analysis and reporting"
        )
    from thg_protocol.analysis.network import find_network_components as analyze

    result = analyze(model)
    if verbose:
        print(
            f"Number of weakly connected components: "
            f"{len(result['components'])}"
        )
    return result


__all__ = ["find_network_components"]
