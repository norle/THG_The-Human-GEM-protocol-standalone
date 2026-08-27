"""Compatibility facade for :mod:`thg_protocol.workflow.foundation`."""

from ._foundation import (
    Beta1ScientificStage,
    FoundationStage,
    ValidationScientificStage,
    _stages,
)


def register_builtin_workflows(registry: object) -> None:
    """Compatibility hook; built-ins are now bootstrapped by ``registry``."""
    from .registry import REGISTRY

    if registry is REGISTRY:
        return
    for workflow_id in REGISTRY.ids():
        registry.register(REGISTRY.get(workflow_id))


__all__ = [
    "Beta1ScientificStage", "FoundationStage", "ValidationScientificStage",
    "_stages", "register_builtin_workflows",
]
