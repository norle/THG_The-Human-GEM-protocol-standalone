# Task guides

Use these guides as the canonical task chooser. For the usual input-to-output
order after choosing a task, see [the workflow overview](workflow-overview.md).

| I want to... | Guide | Main result |
| --- | --- | --- |
| Create a model from normalized records or a saved record bundle | [Model reconstruction](workflows/database.md) | JSON or SBML model |
| Enrich a model with external biological information | [Model enrichment](workflows/model-build.md) | Annotated model, caches, and error report |
| Check or add identifiers and GPR information | [Annotation](workflows/annotation.md) | Annotation inventory or updated information |
| Add a defined pathway | [Pathway implementation](workflows/pathway.md) | Revised JSON model |
| Find transport candidates for compartment-specific dead ends | [Gapfill](workflows/gapfill.md) | Candidate and selection reports plus revised model |
| Combine two models | [Merge and consistency](workflows/merge.md) | Merged model and merge report |
| Compare model versions or references | [Model comparison](workflows/comparison.md) | CSV comparison reports |
| Inspect connectivity, balance, or redundant reactions | [Network analysis](workflows/network-analysis.md) | Analysis results and optional report |
| Derive a model for a cell type | [Cell-specific models](workflows/cell-specific.md) | Tailored model and reduction report |
| Present model or report summaries | [Figures and reports](workflows/figures.md) | SVG figures and summaries |
| Run broader quality diagnostics | [MEMOTE and task analysis](workflows/memote.md) | MEMOTE/task reports |

## Command-line workflows

Three common workflows are also available from the command line:

```bash
thg-gapfill --model model.json --output-dir results/gapfill
thg-pathway --model model.json --config pathway.json \
  --database metabolite_ids.json --output results/pathway.json
thg-compare model_a.json model_b.json --output-dir results/compare
```

Each guide describes the expected inputs, generated files, and common issues.
For Python automation, use the corresponding functions in the [API
reference](api/index.md).
