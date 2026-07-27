"""External-service client protocols and adapters."""

from .pubchem import (
    PubChemClient,
    PubChemClientProtocol,
    PubChemCompound,
    PubChemError,
    StaticPubChemClient,
)

__all__ = [
    "PubChemClient",
    "PubChemClientProtocol",
    "PubChemCompound",
    "PubChemError",
    "StaticPubChemClient",
]
