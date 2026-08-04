# Package architecture and data boundaries

This maintainer-oriented page describes software boundaries, not a second
scientific workflow. The [protocol overview](protocol/index.md) is the single
canonical end-to-end story.

```text
caller-owned records/models/configuration
                 |
                 v
  explicit package APIs and injected service clients
                 |
                 v
 caller-selected models, reports, caches, and figures
```

## Boundaries

- `thg_protocol.database` reconstructs COBRA models from normalized records;
  service enrichment is explicit and client-injectable.
- `annotation`, `gpr`, and `model_build` provide curation and enrichment
  building blocks with explicit paths and cache/error ownership.
- `merge` returns a copied model and structured report; `analysis` provides
  local connectivity, balance, comparison, and compaction operations.
- `pathway`, `gapfill`, `cell_specific`, and `figures` are modular supporting or
  downstream operations, not mandatory stages of every THG construction.

Inputs are not silently loaded from repository-relative locations. Service
clients own network, retries, credentials, and response normalization;
static-client adapters support offline tests. See [API contracts](api-contracts.md)
and the [service boundary audit](service-boundary-audit.md) for details.
