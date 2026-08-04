# Model operations

Use this page as a conceptual input-to-output map. Operations can be run
independently. A model or report written by one operation can be used as input
to another where the format is supported. Use the [task guides](usage.md) to
choose a specific operation.

## Construct or enrich a model

| Starting input | Operation | Result |
| --- | --- | --- |
| Normalized metabolite and reaction records | [Model reconstruction](workflows/database.md) | A JSON or SBML model |
| JSON or SBML model | [Model enrichment](workflows/model-build.md) | An enriched model, optional caches, and an error report |
| JSON or SBML model with incomplete identifiers or GPRs | [Annotation](workflows/annotation.md) | Annotation inventory, updated information, or GPR candidates |

Model reconstruction works from local normalized records. Model enrichment and
some annotation operations can use external biological databases; those guides
state when clients, network access, or credentials are required.

## Change model content

| Starting input | Operation | Result |
| --- | --- | --- |
| JSON model and pathway configuration | [Pathway implementation](workflows/pathway.md) | A model with the configured reactions and compartments |
| JSON model with compartment-specific dead ends | [Gapfill](workflows/gapfill.md) | Transport candidates, selection reports, and a revised model |
| Two compatible JSON or SBML models | [Merge](workflows/merge.md) | A merged model and merge report |

## Inspect, compare, or derive output

| Starting input | Operation | Result |
| --- | --- | --- |
| Loaded COBRA model | [Network analysis](workflows/network-analysis.md) | Connectivity, balance, and compaction results |
| Two JSON or SBML models | [Model comparison](workflows/comparison.md) | CSV reports of reaction and stoichiometry differences |
| Model and activity or expression data | [Cell-specific models](workflows/cell-specific.md) | A reduced model and reduction report |
| Models or report tables | [Figures and reports](workflows/figures.md) | Summaries and optional SVG figures |
| Model and optional solver setup | [MEMOTE and task analysis](workflows/memote.md) | MEMOTE and task-analysis reports |

Network analysis runs locally for connectivity and formula-balance checks.
Solver-backed checks, cell-specific methods, MEMOTE, and rendering are optional
capabilities; see [installation](installation.md) before using them.

## First example

The [five-minute quickstart](quickstart.md) reconstructs a small model from
normalized records and checks its balance.
