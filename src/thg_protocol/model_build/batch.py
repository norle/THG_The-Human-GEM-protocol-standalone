"""Package-native batch model annotation workflow."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from . import ModelBuildReport

__all__ = ["build_model_batch"]


def build_model_batch(
    input_path: str | Path,
    output_path: str | Path,
    *,
    output_errors: str | Path | None = None,
    cache_dir: str | Path | None = None,
    biocyc_client: Any | None = None,
    kegg_client: Any | None = None,
    ensembl_client: Any | None = None,
) -> ModelBuildReport:
    """Annotate a model with batch-oriented service and cache boundaries.

    The model, output, cache, and error paths are explicit. Service clients
    are injectable for offline tests and production adapters are instantiated
    lazily by [`build_model`][thg_protocol.model_build.build_model]. Package-owned
    JSON caches are the source of annotation state.
    """
    from . import build_model

    destination = Path(output_path)
    cache_root = (
        Path(cache_dir) if cache_dir is not None else destination.parent / "cache"
    )
    report = build_model(
        input_path,
        destination,
        cache_dir=cache_root,
        biocyc_client=biocyc_client,
        kegg_client=kegg_client,
        ensembl_client=ensembl_client,
    )
    if output_errors is not None:
        error_path = Path(output_errors)
        error_path.parent.mkdir(parents=True, exist_ok=True)
        error_path.write_text(
            "service\terror\n"
            + "".join(f"unknown\t{error}\n" for error in report.errors),
            encoding="utf-8",
        )
    return report
