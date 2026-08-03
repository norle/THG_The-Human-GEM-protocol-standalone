# Architecture and data flow

The package is organized around explicit data boundaries:

```text
normalized records / model files / configs
                │
                ▼
construction ──► annotation ──► curation and workflows
     │              │                   │
     └──────────────┴──────────────┬────┘
                                   ▼
                         merge / analysis / figures
                                   │
                                   ▼
                         caller-owned reports and models
```

Construction APIs in `database` and `model_build` turn normalized records or
reference models into COBRA models. Annotation and GPR modules enrich model
entities. Pathway, gapfill, merge, and cell-specific modules transform models
or JSON mappings. Analysis modules inspect structure, consistency, connected
components, compaction, and differences. Figure modules consume explicit
models or report rows and write caller-selected image files.

## Service boundary

BioCyc, KEGG, Ensembl, PubChem, and location lookups live in
`thg_protocol.services`. Production clients can use network access, while
static clients provide deterministic tests and offline examples. Service-aware
functions accept a client explicitly; importing the package does not make a
live request. See the [service boundary audit](service-boundary-audit.md).

## Ownership and mutation

The API reference identifies mutation behavior per function. In general,
normalized reconstruction returns a new model, pathway implementation mutates
the supplied JSON mapping, merge returns a copied merged model, and analysis
functions inspect without mutation. Files, caches, reports, and credentials
belong to the caller and must be passed as explicit paths or clients.

## Optional dependencies

The base package supports dependency-light JSON, structural, and service-boundary
workflows. The `database` extra supports historical pickle compatibility;
`solver` and `memote` are opt-in; `cell-specific` enables Troppo/pathos
workflows; and `figures` enables rendering. The docs CI does not require these
optional capabilities.
