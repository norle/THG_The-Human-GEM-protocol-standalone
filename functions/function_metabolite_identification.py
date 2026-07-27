"""Compatibility wrapper for metabolite identification helpers.

New code should import from :mod:`thg_protocol.annotation.metabolites`.
"""

from thg_protocol.annotation.metabolites import (
    PubChemClient,
    PubChemClientProtocol,
    atom,
    formula_similarity,
    gather_metabolites,
    generate_met_annotation,
    global_met_annotation_file,
    identify_metabolite,
    process_annotation,
    remove_null_value,
    setup_proxy,
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
