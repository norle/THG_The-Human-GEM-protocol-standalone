"""Compatibility wrapper for exchange-reaction matching."""

from __future__ import annotations

from typing import Any


def match_exch_rxns(
    model_new: Any,
    model_base: Any,
    tol: float = 1e-9,
    add_rs: bool = False,
) -> tuple[Any, list[tuple[str, str]], list[str], list[str]]:
    """Delegate to :func:`thg_protocol.cell_specific.match_exchange_reactions`.

    ``tol`` remains accepted for source compatibility; matching is
    deterministic and does not require a solver.
    """
    del tol
    from thg_protocol.cell_specific.exchange import match_exchange_reactions

    return match_exchange_reactions(model_new, model_base, add_reactions=add_rs)


__all__ = ["match_exch_rxns"]
