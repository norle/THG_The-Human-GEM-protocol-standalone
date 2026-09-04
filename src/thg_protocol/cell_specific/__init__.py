"""Dependency-light cell-specific model tailoring utilities."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ActivityReductionReport:
    """Summary returned by
    [`reduce_model_by_activity`][thg_protocol.cell_specific.reduce_model_by_activity].
    """

    total_reactions: int
    retained_reactions: int
    removed_reactions: int
    orphan_metabolites_removed: int
    orphan_genes_removed: int
    output_path: Path | None = None


@dataclass(frozen=True)
class CellSpecificReport:
    """Audit information for GPR-driven context-specific reduction."""

    total_reactions: int
    retained_reactions: int
    removed_reactions: int
    unknown_genes: tuple[str, ...]
    preserved_reactions: tuple[str, ...]
    uncertainty: tuple[str, ...] = ()


def evaluate_gpr_activity(
    rule: str, activity: dict[str, float], *, threshold: float = 0.0
) -> tuple[bool, tuple[str, ...]]:
    """Evaluate a boolean GPR and report genes absent from the activity map."""
    from .gpr import reaction_expression_evidence

    evidence = reaction_expression_evidence("activity", rule, activity)
    return (
        not rule.strip()
        or bool(evidence.score is not None and evidence.score > threshold),
        evidence.missing_genes,
    )


def build_cell_specific_model(
    model: Any,
    activity: dict[str, float],
    *,
    threshold: float = 0.0,
    preserve_reactions: Sequence[str] = (),
) -> tuple[Any, CellSpecificReport]:
    """Build a copied COBRA model from gene activity with uncertainty reporting."""
    tailored = model.copy()
    preserve = set(preserve_reactions)
    remove = []
    unknown: set[str] = set()
    uncertainty: list[str] = []
    for reaction in tailored.reactions:
        active, missing = evaluate_gpr_activity(
            reaction.gene_reaction_rule, activity, threshold=threshold
        )
        unknown.update(missing)
        if missing:
            uncertainty.append(reaction.id)
        if not active and reaction.id not in preserve:
            remove.append(reaction)
    tailored.remove_reactions(remove)
    return tailored, CellSpecificReport(
        len(model.reactions),
        len(tailored.reactions),
        len(remove),
        tuple(sorted(unknown)),
        tuple(sorted(preserve)),
        tuple(sorted(uncertainty)),
    )


def _activity_matrix(activity: Any, *, matrix_key: str) -> Any:
    import numpy as np

    if isinstance(activity, (str, Path)):
        path = Path(activity)
        if path.suffix.lower() == ".csv":
            # ``ndmin`` preserves a single column as reaction rows instead of
            # letting ``loadtxt`` collapse it into a one-dimensional vector.
            return np.loadtxt(path, delimiter=",", ndmin=2)
        if path.suffix.lower() == ".mat":
            from scipy.io import loadmat

            payload = loadmat(path)
            if matrix_key not in payload:
                raise KeyError(f"activity matrix key not found: {matrix_key}")
            return payload[matrix_key]
        raise ValueError("activity input must be a CSV, MAT file, or matrix")
    return np.asarray(activity)


def _labeled_csv_activity(path: Path, reaction_ids: list[str]):
    """Read a ``reaction_id`` activity CSV and align it to model order."""
    import csv

    import numpy as np

    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or "reaction_id" not in reader.fieldnames:
            return None
        value_columns = [key for key in reader.fieldnames if key != "reaction_id"]
        if not value_columns:
            raise ValueError("labeled activity matrix requires at least one sample column")
        rows = list(reader)
    ids = [str(row["reaction_id"]) for row in rows]
    if len(ids) != len(set(ids)) or set(ids) != set(reaction_ids):
        raise ValueError("labeled activity matrix reaction IDs must equal model IDs")
    values = {
        row["reaction_id"]: [float(row[key]) for key in value_columns] for row in rows
    }
    return np.asarray([values[reaction_id] for reaction_id in reaction_ids])


def load_activity_matrix(
    model: Any,
    activity: Any,
    *,
    matrix_key: str = "all_Solutions_matrix5",
    legacy_row_order: bool = False,
    model_signature: str | None = None,
):
    """Load an activity matrix, aligning labeled CSV rows by reaction ID.

    Unlabeled file inputs require an explicit legacy row-order acknowledgement
    and a model signature supplied by the calling workflow.
    """
    import numpy as np

    reaction_ids = [reaction.id for reaction in model.reactions]
    matrix = (
        _labeled_csv_activity(Path(activity), reaction_ids)
        if isinstance(activity, (str, Path)) and Path(activity).suffix.lower() == ".csv"
        else None
    )
    if isinstance(activity, (str, Path)) and matrix is None:
        if not legacy_row_order or not model_signature:
            raise ValueError(
                "unlabeled activity files require legacy_row_order=true and "
                "a model_signature"
            )
    matrix = np.atleast_2d(
        matrix
        if matrix is not None
        else _activity_matrix(activity, matrix_key=matrix_key)
    )
    if matrix.shape[0] != len(reaction_ids):
        raise ValueError(
            "activity rows must match model reactions: "
            f"{matrix.shape[0]} != {len(reaction_ids)}"
        )
    return matrix


def _write_model(model: Any, output_path: Path) -> None:
    from thg_protocol.io.models import save_model

    save_model(model, output_path)


def reduce_model_by_activity(
    model: Any,
    activity: Any,
    *,
    presence_threshold: float = 0.0,
    preserve_reactions: Sequence[str] = (),
    matrix_key: str = "all_Solutions_matrix5",
    legacy_row_order: bool = False,
    model_signature: str | None = None,
    output_path: str | Path | None = None,
) -> tuple[Any, ActivityReductionReport]:
    """Tailor a model using the mean non-zero activity per reaction.

    Activity rows must follow ``model.reactions`` order. Reactions whose
    non-zero presence is at or below ``presence_threshold`` are removed,
    except for IDs in ``preserve_reactions``. The input model is copied and
    never mutated. CSV and MAT inputs are supported without importing Troppo.
    """
    if not 0 <= presence_threshold <= 1:
        raise ValueError("presence_threshold must be between 0 and 1")

    import numpy as np

    reaction_ids = [reaction.id for reaction in model.reactions]
    matrix = load_activity_matrix(
        model,
        activity,
        matrix_key=matrix_key,
        legacy_row_order=legacy_row_order,
        model_signature=model_signature,
    )
    presence = np.mean(matrix != 0, axis=1)
    preserve = set(preserve_reactions)
    remove_ids = {
        reaction_id
        for reaction_id, value in zip(reaction_ids, presence, strict=True)
        if value <= presence_threshold and reaction_id not in preserve
    }

    tailored = model.copy()
    tailored.remove_reactions(
        [tailored.reactions.get_by_id(reaction_id) for reaction_id in remove_ids]
    )
    orphan_metabolites = [
        metabolite for metabolite in tailored.metabolites if not metabolite.reactions
    ]
    tailored.remove_metabolites(orphan_metabolites)
    orphan_genes = [gene for gene in tailored.genes if not gene.reactions]
    for gene in orphan_genes:
        tailored.genes.remove(gene)

    destination = Path(output_path) if output_path is not None else None
    if destination is not None:
        _write_model(tailored, destination)
    return tailored, ActivityReductionReport(
        total_reactions=len(reaction_ids),
        retained_reactions=len(tailored.reactions),
        removed_reactions=len(remove_ids),
        orphan_metabolites_removed=len(orphan_metabolites),
        orphan_genes_removed=len(orphan_genes),
        output_path=destination,
    )


from .consensus import ConsensusResult, consensus_from_gimme  # noqa: E402
from .exchange import match_exchange_reactions  # noqa: E402
from .gimme import (  # noqa: E402
    GimmeObjectiveRequirement,
    GimmeResult,
    expression_penalties,
    run_gimme,
)
from .gpr import (  # noqa: E402
    ReactionExpressionEvidence,
    reaction_expression_evidence,
    reaction_expression_for_model,
)
from .transcriptomics import (  # noqa: E402
    extract_ensembl_ids,
    extract_gene_annotation_pairs,
    extract_sgpr_rules,
    replace_gene_symbols,
    replace_index_tokens,
)

__all__ = [
    "ActivityReductionReport",
    "reduce_model_by_activity",
    "load_activity_matrix",
    "CellSpecificReport",
    "evaluate_gpr_activity",
    "build_cell_specific_model",
    "match_exchange_reactions",
    "ConsensusResult",
    "consensus_from_gimme",
    "GimmeObjectiveRequirement",
    "GimmeResult",
    "expression_penalties",
    "run_gimme",
    "ReactionExpressionEvidence",
    "reaction_expression_evidence",
    "reaction_expression_for_model",
    "extract_ensembl_ids",
    "extract_gene_annotation_pairs",
    "extract_sgpr_rules",
    "replace_gene_symbols",
    "replace_index_tokens",
]
