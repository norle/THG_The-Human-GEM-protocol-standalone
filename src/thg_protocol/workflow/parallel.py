"""Small deterministic helpers for bounded CPU parallelism."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from concurrent.futures import ProcessPoolExecutor
from typing import TypeVar

Item = TypeVar("Item")
Result = TypeVar("Result")


def parallel_map(
    function: Callable[[Item], Result],
    items: Iterable[Item],
    *,
    n_jobs: int = 1,
) -> tuple[Result, ...]:
    """Map a module-level pure function in input order."""
    if isinstance(n_jobs, bool) or not isinstance(n_jobs, int) or n_jobs < 1:
        raise ValueError("n_jobs must be a positive integer")
    values = tuple(items)
    if n_jobs == 1 or len(values) < 2:
        return tuple(function(item) for item in values)
    workers = min(n_jobs, len(values))
    chunksize = max(1, len(values) // (workers * 8))
    with ProcessPoolExecutor(max_workers=workers) as executor:
        return tuple(executor.map(function, values, chunksize=chunksize))


__all__ = ["parallel_map"]
