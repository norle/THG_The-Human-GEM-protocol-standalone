"""Compatibility wrapper for metabolite identification helpers.

New code should import from :mod:`thg_protocol.annotation.metabolites`.
"""

import os
from pathlib import Path

from thg_protocol.annotation.metabolites import (
    PubChemClient,
    PubChemClientProtocol,
    atom,
    formula_similarity,
    gather_metabolites,
    global_met_annotation_file,
    identify_metabolite,
    remove_null_value,
    setup_proxy,
)
from thg_protocol.annotation.metabolites import (
    generate_met_annotation as _generate_met_annotation,
)
from thg_protocol.annotation.metabolites import (
    process_annotation as _process_annotation,
)

__all__ = [
    "PubChemClient",
    "PubChemClientProtocol",
    "atom",
    "formula_similarity",
    "gather_metabolites",
    "generate_met_annotation",
    "global_met_annotation_file",
    "identify_metabolite",
    "process_annotation",
    "remove_null_value",
    "setup_proxy",
]


def _legacy_annotation_file() -> str:
    """Return the historical repository-relative annotation output path."""
    return os.fspath(
        Path(__file__).resolve().parents[1]
        / "metabolite_reac_identification"
        / "reports"
        / "met_annotation.tsv"
    )


def generate_met_annotation(
    met_list,
    out: str | Path | None = None,
    delay_between_requests: float = 1.0,
    checkpoint_interval: int = 10,
    resume: bool = True,
    client: PubChemClientProtocol | None = None,
):
    """Preserve the legacy default while delegating to the package API."""
    return _generate_met_annotation(
        met_list,
        out=out or _legacy_annotation_file(),
        delay_between_requests=delay_between_requests,
        checkpoint_interval=checkpoint_interval,
        resume=resume,
        client=client,
    )


def process_annotation(annotation_file=None):
    """Preserve the legacy default while delegating to the package API."""
    return _process_annotation(annotation_file or _legacy_annotation_file())
