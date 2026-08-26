"""Validation rules for the documented scientific capability registry."""

from __future__ import annotations

from collections.abc import Iterable, Mapping


class CapabilityRegistryError(ValueError):
    """Raised when a scientific capability lacks reproducibility coverage."""


_SCIENTIFIC_EFFECTS = {"none", "analysis", "evidence", "mutation", "selection"}
_WORKFLOW_TIERS = {"release-supported", "research-supported"}
_REQUIRED = (
    "workflow_coverage",
    "configuration_contract",
    "verification",
    "provenance_output",
    "validation_output",
)


def validate_capability_registry(
    capabilities: Iterable[Mapping[str, object]],
) -> None:
    """Enforce workflow evidence for supported mutation/selection capabilities."""
    for capability in capabilities:
        identifier = str(capability.get("id", "<unknown>"))
        effect = capability.get("scientific_effect", "none")
        if effect not in _SCIENTIFIC_EFFECTS:
            raise CapabilityRegistryError(
                f"{identifier}: invalid scientific_effect {effect!r}"
            )
        if effect not in {"mutation", "selection"} or capability.get(
            "support_tier"
        ) not in _WORKFLOW_TIERS:
            continue
        missing = [
            key
            for key in _REQUIRED
            if not isinstance(capability.get(key), str)
            or not str(capability[key]).strip()
        ]
        if missing:
            raise CapabilityRegistryError(
                f"{identifier}: missing scientific coverage: {', '.join(missing)}"
            )


__all__ = ["CapabilityRegistryError", "validate_capability_registry"]
