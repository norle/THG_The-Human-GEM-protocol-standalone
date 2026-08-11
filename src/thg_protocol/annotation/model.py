"""COBRA model annotation and SBML output helpers.

The COBRA dependency is intentionally imported inside the write function so
that package discovery, documentation builds, and CLI help remain safe in
environments that do not install the model runtime.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

LOGGER = logging.getLogger(__name__)

__all__ = ["annotate_cobra_model"]


def annotate_cobra_model(
    model: Any,
    met_annotation: Mapping[str, Mapping[str, Any]],
    reac_annotation: Mapping[str, Mapping[str, Any]],
    out_file1: str | Path,
    out_file2: str | Path,
) -> None:
    """Apply annotations and write the regular and normalized SBML files.

    ``model`` is mutated only inside COBRA's model context and therefore
    retains the caller's in-memory state. Both output paths are required and
    their parent directories are created explicitly. The second file retains
    the legacy identifier normalization used by THG model consumers.
    """
    from cobra.io import write_sbml_model

    first_path = Path(out_file1).expanduser().resolve()
    second_path = Path(out_file2).expanduser().resolve()
    first_path.parent.mkdir(parents=True, exist_ok=True)
    second_path.parent.mkdir(parents=True, exist_ok=True)

    with model:
        for metabolite in model.metabolites:
            annotation = met_annotation.get(str(metabolite)[:-1])
            if annotation:
                metabolite.annotation.update(annotation)
        for reaction_id, annotation in reac_annotation.items():
            model.reactions.get_by_id(reaction_id).annotation["kegg.reaction"] = (
                annotation["kegg.reaction"]
            )

        LOGGER.info("Writing SBML model to %s...", first_path)
        write_sbml_model(model, str(first_path))

    replacements = (
        ('fbc:label="G_', 'fbc:label="'),
        ('name="G_', 'name="'),
        ('="meta_G_', '="'),
        ('="#?meta_[MGR]_', '="'),
        ('id="[MGR]_', 'id="'),
        ('species="M_', 'species="'),
        ('fbc:geneProduct="G_', 'fbc:geneProduct="'),
        ('idRef="R_', 'idRef="'),
        ('groups:name=".+?" ', ""),
        ('rdf:about="', 'rdf:about="#'),
    )
    normalized = first_path.read_text()
    for pattern, replacement in replacements:
        normalized = re.sub(pattern, replacement, normalized)
    second_path.write_text(normalized)
    LOGGER.info("SBML annotation complete.")
