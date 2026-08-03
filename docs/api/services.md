# External services

Each service module defines a protocol, a static/offline client, and (where
supported) a network client. Pass a caller-owned session when authentication or
custom transport is required. Service errors are explicit and network calls
are never made merely by importing the package.

::: thg_protocol.services

## BioCyc

::: thg_protocol.services.biocyc

## KEGG

::: thg_protocol.services.kegg

## Ensembl

::: thg_protocol.services.ensembl

## PubChem

::: thg_protocol.services.pubchem

## Location

::: thg_protocol.services.location
