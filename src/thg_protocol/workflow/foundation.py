"""Offline fixture stages and their small workflow-facing adapters."""

from ._foundation import (
    Beta1ScientificStage,
    FoundationStage,
    ValidationScientificStage,
    _stages,
)


def fixture_stages(prefix: str) -> tuple[object, ...]:
    return _stages(prefix)


__all__ = [
    "Beta1ScientificStage",
    "FoundationStage",
    "ValidationScientificStage",
    "fixture_stages",
]
