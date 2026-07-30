"""Archived-test compatibility exports for the maintained GPR API."""

from thg_protocol.gpr.ast_gpr import (
    compare_ast,
    deduplicate_gpr,
    divide_gpr_in_ors,
    is_or,
    naive_reduce_or,
    reduce_gpr,
    remove_empty,
    sanitize_gpr,
)

__all__ = [
    "compare_ast",
    "deduplicate_gpr",
    "divide_gpr_in_ors",
    "is_or",
    "naive_reduce_or",
    "reduce_gpr",
    "remove_empty",
    "sanitize_gpr",
]
