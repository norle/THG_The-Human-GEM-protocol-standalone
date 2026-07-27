"""Compatibility wrapper for GPR AST helpers.

New code should import from :mod:`thg_protocol.gpr.ast_gpr`.
"""

import sys
from pathlib import Path

src_path = Path(__file__).resolve().parents[2] / "src"
if src_path.exists() and str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from thg_protocol.gpr.ast_gpr import (  # noqa: E402,F401
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
