"""Archived-test compatibility exports for reaction annotation."""

from thg_protocol.annotation.reactions import (
    execute_jaccard,
    gather_kegg_metabolites,
    identify_reaction,
    jaccard,
    process_jaccard,
    process_reac,
    replace_met_id_by_met_kegg,
)

__all__ = [
    "execute_jaccard",
    "gather_kegg_metabolites",
    "identify_reaction",
    "jaccard",
    "process_jaccard",
    "process_reac",
    "replace_met_id_by_met_kegg",
]
