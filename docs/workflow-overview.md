# Workflow overview

Classify the workflow by its available inputs. THG operations can be called
independently. To study the published construction strategy, follow the staged
protocol shown in the [complete workflow](protocol/index.md).

| Input class | Workflow branch | Main output | Typical external requirements |
| --- | --- | --- | --- |
| Existing JSON/SBML human GEM | [Curate and expand a reference GEM](protocol/reference-model.md) | THGβ1-like/THGβ2-like revised model and reports | Biological services; BioCyc credentials for applicable lookups |
| Human pathway/database records | [Construct the Human Database](protocol/human-database.md) | Human-specific network or reconstructed model | Normalized records or supported service clients |
| Two prepared model branches | [Merge and validate](protocol/merge-and-validate.md) | Merged model and validation reports | Solver and MEMOTE for selected checks |
| One local task | [Individual operations](usage.md) | Operation-specific model/report | Depends on the operation |

## Available workflows

1. **Existing GEM:** preserve the input, inspect identifiers, apply the
   supported annotation/model-build building blocks, then check balances and
   GPR/location changes.
2. **Pathway/database information:** normalize records first, reconstruct a
   model locally, and use the Human Database page to distinguish that operation
   from historical live harvesting.
3. **One operation:** use the operation chooser for a focused task such as
   pathway implementation, gapfill, comparison, or a downstream cell-specific
   model.

The [practical quickstart](quickstart.md) demonstrates a small offline workflow
through inspection, deterministic enrichment, checks, and comparison. It is a
software demonstration, not a research-quality human reconstruction. The
[API smoke test](api-smoke-test.md) retains the minimal two-metabolite example
for installation checks.
