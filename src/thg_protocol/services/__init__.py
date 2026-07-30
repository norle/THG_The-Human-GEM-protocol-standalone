"""External-service client protocols and adapters."""

from .biocyc import (
    BioCycClient,
    BioCycClientProtocol,
    BioCycError,
    StaticBioCycClient,
)
from .ensembl import (
    EnsemblAnnotation,
    EnsemblClient,
    EnsemblClientProtocol,
    EnsemblError,
    StaticEnsemblClient,
)
from .kegg import KeggClient, KeggClientProtocol, KeggError, StaticKeggClient
from .location import (
    LocationClient,
    LocationClientProtocol,
    LocationError,
    StaticLocationClient,
)
from .pubchem import (
    PubChemClient,
    PubChemClientProtocol,
    PubChemCompound,
    PubChemError,
    StaticPubChemClient,
)

__all__ = [
    "EnsemblAnnotation",
    "EnsemblClient",
    "EnsemblClientProtocol",
    "EnsemblError",
    "StaticEnsemblClient",
    "BioCycClient",
    "BioCycClientProtocol",
    "BioCycError",
    "StaticBioCycClient",
    "KeggClient",
    "KeggClientProtocol",
    "KeggError",
    "StaticKeggClient",
    "PubChemClient",
    "PubChemClientProtocol",
    "PubChemCompound",
    "PubChemError",
    "StaticPubChemClient",
    "LocationClient",
    "LocationClientProtocol",
    "LocationError",
    "StaticLocationClient",
]
