"""Gene-protein-reaction parsing and sanitization helpers."""

def __getattr__(name: str):
    """Load legacy GPR helpers lazily because they require optional COBRA deps."""
    if name not in __all__:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    from thg_protocol.gpr import ast_gpr

    return getattr(ast_gpr, name)


from .evidence import SgprEvidence  # noqa: E402
from .lookup import (  # noqa: E402
    get_gpr,
    get_gpr_evidence,
    get_sgpr_evidence,
    parse_gene_pairs,
    resolve_sgpr,
)
from .merge import SgprResolution, merge_sgpr_evidence  # noqa: E402
from .selection import GprSelection, select_reaction_gpr, usable_gpr  # noqa: E402
from .stoichiometry import (  # noqa: E402
    AndNode,
    GeneNode,
    OrNode,
    default_sgpr_coefficients,
    genes_in_sgpr,
    normalize_sgpr,
    parse_sgpr,
    sgpr_from_dict,
    sgpr_to_dict,
    strip_stoichiometry,
    to_gpr,
    to_legacy_sgpr,
    to_sgpr,
    unambiguous_stoichiometry,
    validate_sgpr,
)

__all__ = [
    "compare_ast",
    "deduplicate_gpr",
    "divide_gpr_in_ors",
    "reduce_gpr",
    "sanitize_gpr",
    "get_gpr",
    "get_gpr_evidence",
    "get_sgpr_evidence",
    "parse_gene_pairs",
    "resolve_sgpr",
    "AndNode",
    "default_sgpr_coefficients",
    "GeneNode",
    "OrNode",
    "SgprEvidence",
    "SgprResolution",
    "GprSelection",
    "genes_in_sgpr",
    "merge_sgpr_evidence",
    "normalize_sgpr",
    "parse_sgpr",
    "sgpr_from_dict",
    "sgpr_to_dict",
    "strip_stoichiometry",
    "to_gpr",
    "to_legacy_sgpr",
    "to_sgpr",
    "select_reaction_gpr",
    "unambiguous_stoichiometry",
    "usable_gpr",
    "validate_sgpr",
]
