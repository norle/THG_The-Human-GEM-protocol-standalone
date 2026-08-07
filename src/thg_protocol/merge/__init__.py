"""Explicit, non-mutating model merge workflow."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class MergeReport:
    """Counts and output metadata produced by
    [`merge_models`][thg_protocol.merge.merge_models]."""

    added_metabolites: int
    added_reactions: int
    overlapping_metabolites: int
    overlapping_reactions: int
    removed_isolated_metabolites: int
    output_path: Path | None = None


def _merge_annotation(target: Any, source: Any) -> None:
    """Copy non-empty incoming annotations without sharing mutable values."""
    for key, value in source.annotation.items():
        if value not in (None, "", [], {}, ()):
            target.annotation[key] = copy.deepcopy(value)


def _write_model(model: Any, output_path: Path) -> None:
    from cobra.io import save_json_model, write_sbml_model

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.suffix.lower() == ".json":
        save_json_model(model, str(output_path))
    else:
        write_sbml_model(model, str(output_path))


def merge_models(
    base_model: Any,
    incoming_model: Any,
    *,
    output_path: str | Path | None = None,
    remove_isolated_metabolites: bool = False,
) -> tuple[Any, MergeReport]:
    """Merge ``incoming_model`` into a copy of ``base_model``.

    Existing objects retain their stoichiometry and bounds; incoming names,
    non-empty annotations, and missing GPRs enrich overlaps. New reactions
    and metabolites are copied by identifier, so neither input model is
    mutated and the returned model owns all of its objects.
    """
    from cobra import Reaction

    result = base_model.copy()
    added_metabolites = 0
    overlapping_metabolites = 0
    for incoming in incoming_model.metabolites:
        if result.metabolites.has_id(incoming.id):
            target = result.metabolites.get_by_id(incoming.id)
            overlapping_metabolites += 1
            if not target.name and incoming.name:
                target.name = incoming.name
            if target.formula is None and incoming.formula:
                target.formula = incoming.formula
            if target.charge is None and incoming.charge is not None:
                target.charge = incoming.charge
            _merge_annotation(target, incoming)
            continue
        result.add_metabolites([copy.deepcopy(incoming)])
        added_metabolites += 1

    added_reactions = 0
    overlapping_reactions = 0
    for incoming in incoming_model.reactions:
        if result.reactions.has_id(incoming.id):
            target = result.reactions.get_by_id(incoming.id)
            overlapping_reactions += 1
            if not target.name and incoming.name:
                target.name = incoming.name
            if not target.gene_reaction_rule and incoming.gene_reaction_rule:
                target.gene_reaction_rule = incoming.gene_reaction_rule
            _merge_annotation(target, incoming)
            continue

        reaction = Reaction(
            incoming.id,
            name=incoming.name,
            lower_bound=incoming.lower_bound,
            upper_bound=incoming.upper_bound,
        )
        reaction.add_metabolites(
            {
                result.metabolites.get_by_id(metabolite.id): coefficient
                for metabolite, coefficient in incoming.metabolites.items()
            }
        )
        reaction.gene_reaction_rule = incoming.gene_reaction_rule
        reaction.annotation.update(copy.deepcopy(incoming.annotation))
        result.add_reactions([reaction])
        added_reactions += 1

    removed_isolated = 0
    if remove_isolated_metabolites:
        isolated = [
            metabolite for metabolite in result.metabolites if not metabolite.reactions
        ]
        result.remove_metabolites(isolated, destructive=False)
        removed_isolated = len(isolated)

    destination = Path(output_path) if output_path is not None else None
    if destination is not None:
        _write_model(result, destination)
    return result, MergeReport(
        added_metabolites=added_metabolites,
        added_reactions=added_reactions,
        overlapping_metabolites=overlapping_metabolites,
        overlapping_reactions=overlapping_reactions,
        removed_isolated_metabolites=removed_isolated,
        output_path=destination,
    )


def merge_models_from_paths(
    base_path: str | Path,
    incoming_path: str | Path,
    output_path: str | Path,
    *,
    remove_isolated_metabolites: bool = False,
) -> tuple[Any, MergeReport]:
    """Load two SBML/JSON models and merge them to an explicit output path."""
    from cobra.io import load_json_model, read_sbml_model

    def load(path: Path) -> Any:
        return (
            load_json_model(str(path))
            if path.suffix.lower() == ".json"
            else read_sbml_model(str(path))
        )

    return merge_models(
        load(Path(base_path)),
        load(Path(incoming_path)),
        output_path=output_path,
        remove_isolated_metabolites=remove_isolated_metabolites,
    )


__all__ = ["MergeReport", "merge_models", "merge_models_from_paths"]
