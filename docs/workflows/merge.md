# Merge and network consistency

Use merge when a base model should be enriched with content from a second
model. The input models remain unchanged, and the merge report shows what was
added or retained.

The package-native merge boundary accepts two COBRA models and returns a
non-mutating merged copy with an explicit report:

```python
from thg_protocol.merge import merge_models

merged, report = merge_models(
    base_model,
    incoming_model,
    output_path="results/merged.xml",
    remove_isolated_metabolites=True,
)
```

For file-based workflows, use `merge_models_from_paths` with SBML or JSON
inputs. Follow the merge with [network analysis](network-analysis.md) to check
the connectivity and balance of the result.

## Prerequisites, output, and troubleshooting

Inputs must be compatible COBRA models or JSON/SBML files. The result is a
copied merged model and a `MergeReport`; optional output is written to the
explicit path. Overlapping IDs retain base stoichiometry and receive non-empty
incoming metadata. Inspect the report before enabling isolated-metabolite
removal.
