# External services

Each service module defines a protocol, a static/offline client, and (where
supported) a network client. Pass a caller-owned session when authentication or
custom transport is required. Service errors are explicit and network calls
are never made merely by importing the package.

## Recommended entry points

Use [`StaticBioCycClient`][thg_protocol.services.biocyc.StaticBioCycClient],
[`StaticKeggClient`][thg_protocol.services.kegg.StaticKeggClient], or the
corresponding static client for deterministic tests and examples.

## BioCyc

::: thg_protocol.services.biocyc
    options:
      members:
        - BioCycError
        - BioCycClientProtocol
        - StaticBioCycClient
        - BioCycClient

## KEGG

::: thg_protocol.services.kegg
    options:
      members:
        - KeggError
        - KeggClientProtocol
        - StaticKeggClient
        - KeggClient

## Ensembl

::: thg_protocol.services.ensembl
    options:
      members:
        - EnsemblError
        - EnsemblAnnotation
        - EnsemblClientProtocol
        - StaticEnsemblClient
        - EnsemblClient

## PubChem

::: thg_protocol.services.pubchem
    options:
      members:
        - PubChemError
        - PubChemCompound
        - PubChemClientProtocol
        - StaticPubChemClient
        - PubChemClient

## Location

::: thg_protocol.services.location
    options:
      members:
        - LocationError
        - LocationClientProtocol
        - StaticLocationClient
        - LocationClient
