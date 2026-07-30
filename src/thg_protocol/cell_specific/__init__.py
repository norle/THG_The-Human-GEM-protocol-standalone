"""Dependency-light cell-specific model tailoring utilities."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ActivityReductionReport:
    """Summary returned by :func:`reduce_model_by_activity`."""

    total_reactions: int
    retained_reactions: int
    removed_reactions: int
    orphan_metabolites_removed: int
    orphan_genes_removed: int
    output_path: Path | None = None


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


def _write_model(model: Any, output_path: Path) -> None:
    from cobra.io import save_json_model, write_sbml_model

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.suffix.lower() == ".json":
        save_json_model(model, str(output_path))
    else:
        write_sbml_model(model, str(output_path))


def reduce_model_by_activity(
    model: Any,
    activity: Any,
    *,
    presence_threshold: float = 0.0,
    preserve_reactions: Sequence[str] = (),
    matrix_key: str = "all_Solutions_matrix5",
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

    matrix = np.atleast_2d(_activity_matrix(activity, matrix_key=matrix_key))
    reaction_ids = [reaction.id for reaction in model.reactions]
    if matrix.shape[0] != len(reaction_ids):
        raise ValueError(
            "activity rows must match model reactions: "
            f"{matrix.shape[0]} != {len(reaction_ids)}"
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


from .exchange import match_exchange_reactions

__all__ = [
    "ActivityReductionReport",
    "reduce_model_by_activity",
    "match_exchange_reactions",
]
