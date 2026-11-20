"""Choice of the LP/MILP solver for gap-filling.

Gurobi is the default where it is installed. HiGHS, through optlang's
``hybrid`` interface (``pip install highspy osqp``), is the open-source
alternative and the fallback when Gurobi cannot be used, for example because
its license has expired. GLPK remains available but is slow on large MILPs.

A run never switches solver silently: the solver is chosen once, named in the
stage fingerprints and recorded in the gap-filling plan.
"""

from __future__ import annotations

import functools
from collections.abc import Iterator
from contextlib import contextmanager

#: Values accepted by the ``gapfill.solver`` setting.
SOLVER_CHOICES = ("auto", "gurobi", "highs", "glpk")

#: optlang/cobra interface name for each solver choice.
_INTERFACE = {"gurobi": "gurobi", "highs": "hybrid", "glpk": "glpk"}


@functools.lru_cache(maxsize=1)
def gurobi_usable() -> bool:
    """Whether Gurobi is installed and its license lets it build a model."""
    try:
        import gurobipy

        with gurobipy.Env(params={"OutputFlag": 0}) as env:
            gurobipy.Model(env=env).dispose()
    except Exception:
        return False
    return True


def resolve_solver(requested: str | None) -> str:
    """The cobra interface name to use for ``requested``.

    ``None`` keeps cobra's configured default. ``"auto"`` means Gurobi when it
    is usable and HiGHS otherwise. An explicit choice that cannot be used
    raises ``ValueError`` instead of falling back.
    """
    from cobra import Configuration
    from cobra.util.solver import interface_to_str, solvers

    if requested is None:
        return interface_to_str(Configuration().solver)
    if requested not in SOLVER_CHOICES:
        raise ValueError(
            f"unknown gapfill solver {requested!r}; use one of "
            + ", ".join(SOLVER_CHOICES)
        )
    if requested == "auto":
        requested = "gurobi" if gurobi_usable() else "highs"
    interface = _INTERFACE[requested]
    if interface not in solvers:
        hint = " (install highspy and osqp)" if requested == "highs" else ""
        raise ValueError(f"gapfill solver {requested!r} is not available{hint}")
    if interface == "gurobi" and not gurobi_usable():
        raise ValueError("gapfill solver 'gurobi' cannot start; check its license")
    return interface


@contextmanager
def default_solver(interface: str) -> Iterator[None]:
    """Make ``interface`` cobra's default solver for the duration of the block.

    Models loaded inside the block are built on that solver directly, so a
    configured but unlicensed default solver is never touched.
    """
    from cobra import Configuration

    configuration = Configuration()
    previous = configuration.solver
    configuration.solver = interface
    try:
        yield
    finally:
        configuration.solver = previous
