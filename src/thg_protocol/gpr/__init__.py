"""Gene-protein-reaction parsing and sanitization helpers."""

__all__ = [
    "compare_ast",
    "deduplicate_gpr",
    "divide_gpr_in_ors",
    "reduce_gpr",
    "sanitize_gpr",
]


def __getattr__(name: str):
    """Load legacy GPR helpers lazily because they require optional COBRA deps."""
    if name not in __all__:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    from thg_protocol.gpr import ast_gpr

    return getattr(ast_gpr, name)
from .lookup import get_gpr, parse_gene_pairs

__all__ = [
    "compare_ast",
    "deduplicate_gpr",
    "divide_gpr_in_ors",
    "reduce_gpr",
    "sanitize_gpr",
    "get_gpr",
    "parse_gene_pairs",
]
