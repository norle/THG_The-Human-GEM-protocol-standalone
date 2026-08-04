# Merge and network consistency

## What this workflow is for

Combine compatible model content while keeping both input models unchanged and
recording what was added, retained, or removed.

## When not to use it

Use [model comparison](comparison.md) when you only need a diff, or
[pathway implementation](pathway.md) when one explicit pathway is being
added.

## Prerequisites and inputs

Inputs are compatible COBRA models or JSON/SBML files. Select an explicit
output path and decide whether isolated metabolites should be removed.

## Python API

Use [`merge_models`][thg_protocol.merge.merge_models] for loaded models:

```python
from thg_protocol.merge import merge_models

merged, report = merge_models(
    base_model, incoming_model, output_path="results/merged.xml",
    remove_isolated_metabolites=True,
)
```

Use [`merge_models_from_paths`][thg_protocol.merge.merge_models_from_paths] for
file inputs. The result is summarized by
[`MergeReport`][thg_protocol.merge.MergeReport].

## Outputs

The result is a copied merged model and a merge report. Overlapping IDs retain
base stoichiometry and receive non-empty incoming metadata.

## Common errors

Incompatible model formats or IDs should be resolved before merging. Inspect
the report before enabling isolated-metabolite removal.

## Next workflow

Run [network analysis](network-analysis.md) to check connectivity and balance,
then use [figures and reports](figures.md) if a summary is needed.
