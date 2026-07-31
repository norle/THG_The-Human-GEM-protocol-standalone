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


def _merge_pair(network_1, network_2):
    """Adapt the historical mutating merge contract to the package API."""
    merged, _report = merge_models(network_1, network_2)
    metabolite_mapping = {
        source.id: source.id
        for source in network_2.metabolites
        if merged.metabolites.has_id(source.id)
    }
    reaction_overlap = [
        reaction.id
        for reaction in network_2.reactions
        if network_1.reactions.has_id(reaction.id)
    ]
    reaction_new = [
        reaction.id
        for reaction in network_2.reactions
        if not network_1.reactions.has_id(reaction.id)
    ]
    return merged, metabolite_mapping, reaction_overlap, reaction_new


def _merge_metabolites(network_1, network_2):
    merged, mapping, _overlap, _new = _merge_pair(network_1, network_2)
    return merged, mapping


def network_metabolites_merge(network_1, network_2):
    return _merge_metabolites(network_1, network_2)


network_metabolites_merge_2 = network_metabolites_merge
network_metabolites_merge_3 = network_metabolites_merge


def network_genes_merge(network_1, network_2):
    return _merge_pair(network_1, network_2)[0]


def network_genes_merge_2(network_1, network_2):
    merged = network_genes_merge(network_1, network_2)
    equivalent = [gene.id for gene in network_1.genes if network_2.genes.has_id(gene.id)]
    return merged, equivalent


def _merge_reactions(network_1, network_2, *_args):
    merged, _mapping, overlap, new = _merge_pair(network_1, network_2)
    return merged, overlap, new


def _merge_reactions_with_consistency(network_1, network_2, *_args):
    merged, overlap, new = _merge_reactions(network_1, network_2)
    return merged, overlap, new, []


network_reactions_merge = _merge_reactions
network_reactions_merge_2 = _merge_reactions
network_reactions_merge_3 = _merge_reactions
network_reactions_merge_4 = _merge_reactions_with_consistency
network_reactions_merge_5 = _merge_reactions_with_consistency
network_reactions_merge_6 = _merge_reactions_with_consistency
network_reactions_merge_7 = _merge_reactions_with_consistency

__all__ = [
    "MergeReport",
    "merge_models",
    "merge_models_from_paths",
    "delete_isolated_metabolites",
    "delete_not_used_reactions",
    "delete_not_used_genes",
    "network_metabolites_merge",
    "network_metabolites_merge_2",
    "network_metabolites_merge_3",
    "network_genes_merge",
    "network_genes_merge_2",
    "network_reactions_merge",
    "network_reactions_merge_2",
    "network_reactions_merge_3",
    "network_reactions_merge_4",
    "network_reactions_merge_5",
    "network_reactions_merge_6",
    "network_reactions_merge_7",
]
