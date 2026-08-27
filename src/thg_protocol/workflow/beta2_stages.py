"""Compatibility facade for the β2 workflow package."""

from .beta2._stages import (
    DETAILED_BETA2_STAGE_IDS,
    DetailedBeta2Stage,
    detailed_beta2_stages,
)

__all__ = ["DETAILED_BETA2_STAGE_IDS", "DetailedBeta2Stage", "detailed_beta2_stages"]
