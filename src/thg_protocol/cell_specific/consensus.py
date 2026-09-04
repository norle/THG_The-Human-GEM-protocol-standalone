"""Consensus evidence for independently solved GIMME samples."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .gimme import GimmeResult


@dataclass(frozen=True)
class ConsensusResult:
    successful_samples: tuple[str, ...]
    failed_samples: tuple[str, ...]
    support: dict[str, float]
    activity: dict[str, bool]
    passed: bool


def consensus_from_gimme(
    results: Sequence[GimmeResult],
    *,
    presence_threshold: float,
    minimum_successful_sample_fraction: float,
) -> ConsensusResult:
    """Exclude failed samples from the denominator and expose their identities."""
    if (
        not 0 <= presence_threshold <= 1
        or not 0 <= minimum_successful_sample_fraction <= 1
    ):
        raise ValueError("consensus and successful-sample thresholds must be in [0, 1]")
    passed = [item for item in results if item.status == "passed"]
    failed = [item for item in results if item.status != "passed"]
    ids = sorted({reaction for item in passed for reaction in item.reaction_active})
    support = {
        reaction: (
            sum(item.reaction_active.get(reaction, False) for item in passed)
            / len(passed)
            if passed
            else 0.0
        )
        for reaction in ids
    }
    return ConsensusResult(
        tuple(item.sample_id for item in passed),
        tuple(item.sample_id for item in failed),
        support,
        {key: value > presence_threshold for key, value in support.items()},
        (
            len(passed) / len(results) >= minimum_successful_sample_fraction
            if results
            else False
        ),
    )


__all__ = ["ConsensusResult", "consensus_from_gimme"]
