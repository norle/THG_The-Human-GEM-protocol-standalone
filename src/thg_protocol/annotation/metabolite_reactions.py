"""Import-safe metabolite and reaction annotation workflow."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from thg_protocol.annotation.metabolites import (
    PubChemClientProtocol,
    gather_metabolites,
    generate_met_annotation,
    identify_metabolite,
    process_annotation,
)
from thg_protocol.annotation.model import annotate_cobra_model
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
    "MetaboliteRetryResult",
    "retry_metabolite_annotations",
    "run_metabolite_reaction_identification",
]


@dataclass(frozen=True)
class MetaboliteRetryResult:
    """Outcome of retrying previously unannotated metabolite records."""

    annotated: tuple[tuple, ...]
    unannotated: tuple[tuple, ...]
    rounds_executed: int


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
    retry_rounds_executed: int = 0


def retry_metabolite_annotations(
    metabolites: list[tuple],
    annotation_path: str | Path,
    failure_path: str | Path,
    *,
    pubchem_client: PubChemClientProtocol,
    max_rounds: int = 10,
    stop_threshold: float = 0.1,
    total_metabolite_count: int | None = None,
) -> MetaboliteRetryResult:
    """Retry failed metabolite lookups through an injected PubChem client.

    Successful tab-separated annotation records are appended to
    ``annotation_path``. ``failure_path`` is replaced with the metabolites
    still unresolved after the final round. Inputs are not mutated.

    Args:
        metabolites: Legacy ``(name, formula, annotation, identifier)`` records.
        annotation_path: Existing annotation report to append to.
        failure_path: Failure report to replace with final unresolved records.
        pubchem_client: Explicit service adapter; no direct network fallback is
            used.
        max_rounds: Maximum retry passes.
        stop_threshold: Stop when unresolved records are at or below this
            fraction of the complete model metabolite count.
        total_metabolite_count: Complete model count used by the threshold.

    Returns:
        Immutable successful/unresolved records and number of passes executed.

    Raises:
        ValueError: If retry configuration is outside its supported range.
    """
    if max_rounds < 0:
        raise ValueError("max_rounds must be non-negative")
    if not 0 <= stop_threshold <= 1:
        raise ValueError("stop_threshold must be between 0 and 1")

    annotation_path = Path(annotation_path)
    failure_path = Path(failure_path)
    annotation_path.parent.mkdir(parents=True, exist_ok=True)
    remaining = list(metabolites)
    retried_annotations: list[tuple] = []
    rounds_executed = 0
    total_count = total_metabolite_count or len(remaining)

    for _ in range(max_rounds):
        if not remaining:
            break
        rounds_executed += 1
        round_successes: list[tuple] = []
        round_failures: list[tuple] = []

        with annotation_path.open("a", encoding="utf-8") as annotation_file:
            for record in remaining:
                name, formula, _annotation, identifier = record
                try:
                    result = identify_metabolite(
                        name,
                        formula,
                        identifier,
                        client=pubchem_client,
                    )
                except Exception:
                    result = None
                if result is None:
                    round_failures.append(record)
                else:
                    annotation_file.write(result)
                    annotation_file.flush()
                    round_successes.append(record)

        retried_annotations.extend(round_successes)
        remaining = round_failures
        if not round_successes:
            break
        if total_count and len(remaining) / total_count <= stop_threshold:
            break

    failure_path.parent.mkdir(parents=True, exist_ok=True)
    with failure_path.open("w", encoding="utf-8") as failure_file:
        failure_file.write("name\tformula\tidentifier\tfailure_reason\n")
        for name, formula, _annotation, identifier in remaining:
            failure_file.write(f"{name}\t{formula}\t{identifier}\tretry_exhausted\n")

    return MetaboliteRetryResult(
        annotated=tuple(retried_annotations),
        unannotated=tuple(remaining),
        rounds_executed=rounds_executed,
    )


def run_metabolite_reaction_identification(
    model_path: str | Path,
    database_path: str | Path,
    output_dir: str | Path,
    *,
    model_output_path: str | Path | None = None,
    normalized_model_output_path: str | Path | None = None,
    pubchem_client: PubChemClientProtocol | None = None,
    annotation_delay: float = 1.0,
    max_retry_rounds: int = 0,
    retry_stop_threshold: float = 0.1,
) -> MetaboliteReactionResult:
    """Annotate one model using explicit inputs and output locations.

    The workflow performs the historical single-pass metabolite annotation,
    reaction matching against ``database_path``, and model annotation. A
    supplied ``pubchem_client`` is passed to every metabolite lookup, including
    optional retry rounds; static clients can therefore run the workflow
    without network access. COBRA is imported only when this function is
    called.
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
    retry_rounds_executed = 0
    if max_retry_rounds and unannotated:
        retry_result = retry_metabolite_annotations(
            unannotated,
            annotation_path,
            failure_path,
            pubchem_client=client,
            max_rounds=max_retry_rounds,
            stop_threshold=retry_stop_threshold,
            total_metabolite_count=len(metabolites),
        )
        annotated.extend(retry_result.annotated)
        unannotated = list(retry_result.unannotated)
        retry_rounds_executed = retry_result.rounds_executed
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
    reaction_annotation = process_jaccard(database_reactions, reactions, matches)
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
        retry_rounds_executed=retry_rounds_executed,
    )
