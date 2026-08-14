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
from .go import GOALoader, GOALoaderProtocol, StaticGOALoader
from .goa import GOAAnnotation, GOAClient, GOAClientProtocol, StaticGOAClient, parse_gaf
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
from .reactome import ReactomeClient, ReactomeClientProtocol, StaticReactomeClient
from .rhea import RheaClient, RheaClientProtocol, StaticRheaClient
from .uniprot import (
    StaticUniProtClient,
    UniProtAnnotation,
    UniProtClient,
    UniProtClientProtocol,
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
    "GOAAnnotation",
    "GOALoader",
    "GOALoaderProtocol",
    "StaticGOALoader",
    "GOAClient",
    "GOAClientProtocol",
    "StaticGOAClient",
    "parse_gaf",
    "RheaClientProtocol",
    "RheaClient",
    "StaticRheaClient",
    "ReactomeClientProtocol",
    "ReactomeClient",
    "StaticReactomeClient",
    "StaticUniProtClient",
    "UniProtAnnotation",
    "UniProtClientProtocol",
    "UniProtClient",
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
