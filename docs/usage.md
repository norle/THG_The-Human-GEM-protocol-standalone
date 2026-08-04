# Choose an individual operation

Use this page when you have one local task rather than following the staged
[THG protocol](protocol/index.md). Operations can be called independently; the
status column describes the current interface, not the publication's complete
workflow.

| Goal | Operation | Input | Output | Status | Network/solver needs |
| --- | --- | --- | --- | --- | --- |
| Reconstruct a model | [Model reconstruction](workflows/database.md) | Normalized JSON/records | JSON/SBML model | Supported | Local; injected clients for enrichment |
| Enrich an existing model | [Model enrichment](workflows/model-build.md) | JSON/SBML model | Model, caches, errors | Supported building block | Service clients may need network/credentials |
| Inspect or resolve identifiers/GPRs | [Annotation and identification](workflows/annotation.md) | Model/records and targets | Inventories, annotations, rules | Supported building blocks | Static clients offline; live services vary |
| Add a defined pathway | [Pathway implementation](workflows/pathway.md) | JSON model, config, ID map | Revised JSON model | Supported | Local; no solver |
| Find transport candidates | [Gapfill](workflows/gapfill.md) | JSON model | Candidate CSVs and revised model | Supported | Local; solver not implicit |
| Combine two models | [Merge](workflows/merge.md) | Two COBRA JSON/SBML models | Model and `MergeReport` | Supported with differences | Local |
| Compare versions | [Model comparison](workflows/comparison.md) | Two JSON/SBML models | Mapping and optional CSVs | Supported | Local; blocked filtering may use solver |
| Check connectivity/balance | [Network analysis](workflows/network-analysis.md) | Loaded COBRA model | Component and consistency reports | Supported | Local; solver only for selected checks |
| Derive a cell-specific model | [Cell-specific models](workflows/cell-specific.md) | Model and CSV/MAT activity | Copied model and reduction report | Partial | `cell-specific` extra; method-dependent solver |
| Create figures/reports | [Figures and reports](workflows/figures.md) | Models or report tables | Summaries and SVGs | Supported building blocks | `figures` extra for rendering |
| Assess model quality/tasks | [MEMOTE and task analysis](workflows/memote.md) | Model file | MEMOTE HTML/task record | External / Archived | External MEMOTE; historical tasks Archived |

Use the [practical quickstart](quickstart.md) for a small offline combination of
these operations. Use the [route chooser](workflow-overview.md) when your goal
is a complete construction branch.
