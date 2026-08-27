"""Validation workflow adapters."""

from ._foundation import ValidationScientificStage


def validation_stages() -> tuple[ValidationScientificStage, ...]:
    return (
        ValidationScientificStage("validate-input"),
        ValidationScientificStage("validate-checks", ("validate-input",)),
        ValidationScientificStage("validate-memote", ("validate-checks",)),
    )


__all__ = ["ValidationScientificStage", "validation_stages"]
