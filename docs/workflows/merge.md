# Merge and network consistency

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
inputs. The legacy solver/MEMOTE consistency routines remain separate and
should be run through their opt-in workflow.

The merge and network-consistency workflow combines a reconstructed network
with an existing GEM and checks the resulting model. It remains a deferred
legacy workflow and is not currently exposed as an installed CLI.

Use small toy models for unit tests; reserve full GEMs and solver-backed
consistency checks for marked integration or solver jobs.
