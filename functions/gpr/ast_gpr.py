"""Compatibility wrapper for GPR AST helpers.

New code should import from :mod:`thg_protocol.gpr.ast_gpr`.
"""

from thg_protocol.gpr.ast_gpr import (
    compare_ast,
    deduplicate_gpr,
    divide_gpr_in_ors,
    reduce_gpr,
    sanitize_gpr,
)

__all__ = [
    "compare_ast",
    "deduplicate_gpr",
    "divide_gpr_in_ors",
    "reduce_gpr",
    "sanitize_gpr",
]
