"""Compatibility boundary for model merge operations."""

from __future__ import annotations

from thg_protocol.merge import MergeReport, merge_models, merge_models_from_paths


def delete_isolated_metabolites(model):
    """Remove metabolites without reactions from a copied model."""
    result = model.copy()
    isolated = [metabolite for metabolite in result.metabolites if not metabolite.reactions]
    result.remove_metabolites(isolated, destructive=False)
    return result


def delete_not_used_reactions(model):
    result = model.copy()
    result.remove_reactions([reaction for reaction in result.reactions if not reaction.metabolites])
    return result


def delete_not_used_genes(model):
    result = model.copy()
    for gene in list(result.genes):
        if not gene.reactions:
            result.genes.remove(gene)
    return result


def _deferred(*_args, **_kwargs):
    raise NotImplementedError(
        "historical multi-stage merge variants are deferred; use "
        "thg_protocol.merge.merge_models"
    )


network_metabolites_merge = network_metabolites_merge_2 = network_metabolites_merge_3 = _deferred
network_genes_merge = network_genes_merge_2 = _deferred
network_reactions_merge = network_reactions_merge_2 = network_reactions_merge_3 = _deferred
network_reactions_merge_4 = network_reactions_merge_5 = network_reactions_merge_6 = _deferred
network_reactions_merge_7 = _deferred

__all__ = [
    "MergeReport",
    "merge_models",
    "merge_models_from_paths",
    "delete_isolated_metabolites",
    "delete_not_used_reactions",
    "delete_not_used_genes",
]
