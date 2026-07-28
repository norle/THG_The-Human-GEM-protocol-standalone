"""Import-safe metabolite and reaction annotation workflow."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from thg_protocol.annotation.model import annotate_cobra_model
from thg_protocol.annotation.metabolites import (
    PubChemClientProtocol,
    gather_metabolites,
    generate_met_annotation,
    process_annotation,
)
from thg_protocol.annotation.reactions import (
    execute_jaccard,
    gather_kegg_metabolites,
    process_jaccard,
    process_reac,
    replace_met_id_by_met_kegg,
)
from thg_protocol.services.pubchem import PubChemClient

__all__ = [
    "MetaboliteReactionResult",
    "run_metabolite_reaction_identification",
]


@dataclass(frozen=True)
class MetaboliteReactionResult:
    """Paths and counts produced by an annotation workflow run."""

    annotation_path: Path
    failure_path: Path
    model_output_path: Path
    normalized_model_output_path: Path
    metabolite_count: int
    annotated_metabolite_count: int
    unannotated_metabolite_count: int
    annotated_reaction_count: int


def run_metabolite_reaction_identification(
    model_path: str | Path,
    database_path: str | Path,
    output_dir: str | Path,
    *,
    model_output_path: str | Path | None = None,
    normalized_model_output_path: str | Path | None = None,
    pubchem_client: PubChemClientProtocol | None = None,
    annotation_delay: float = 1.0,
) -> MetaboliteReactionResult:
    """Annotate one model using explicit inputs and output locations.

    The workflow performs the historical single-pass metabolite annotation,
    reaction matching against ``database_path``, and model annotation. A
    supplied ``pubchem_client`` is passed to every metabolite lookup; static
    clients can therefore run the workflow without network access. COBRA is
    imported only when this function is called.
    """
    from cobra.io import read_sbml_model

    model_path = Path(model_path).expanduser()
    database_path = Path(database_path).expanduser()
    output_dir = Path(output_dir).expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)

    model_output = Path(model_output_path or output_dir / "THG-beta1.1.1.xml")
    normalized_output = Path(
        normalized_model_output_path or output_dir / "THG-beta1.1.xml"
    )
    annotation_path = output_dir / "met_annotation.tsv"
    failure_path = output_dir / "met_annotation_failures.tsv"

    cobra_model = read_sbml_model(str(model_path))
    client = pubchem_client or PubChemClient()
    metabolites = gather_metabolites(cobra_model)
    annotated, unannotated = generate_met_annotation(
        metabolites,
        out=annotation_path,
        delay_between_requests=annotation_delay,
        client=client,
    )
    met_annotation = process_annotation(annotation_path)

    reactions = process_reac(
        str(model_path), "[A-Z]+[0-9]+[a-z]+[0-9]*", "MAM02040", "MAM02039"
    )
    reactions = replace_met_id_by_met_kegg(
        reactions, gather_kegg_metabolites(str(model_path))
    )
    database_reactions = process_reac(
        str(database_path), "([A-Z][0-9]+_?[a-z]+[0-9]*)", "C00080", "C00001"
    )
    matches = execute_jaccard(database_reactions, reactions)
    reaction_annotation = process_jaccard(
        database_reactions, reactions, matches
    )
    annotate_cobra_model(
        cobra_model,
        met_annotation,
        reaction_annotation,
        model_output,
        normalized_output,
    )

    return MetaboliteReactionResult(
        annotation_path=annotation_path,
        failure_path=failure_path,
        model_output_path=model_output,
        normalized_model_output_path=normalized_output,
        metabolite_count=len(metabolites),
        annotated_metabolite_count=len(annotated),
        unannotated_metabolite_count=len(unannotated),
        annotated_reaction_count=len(reaction_annotation),
    )
