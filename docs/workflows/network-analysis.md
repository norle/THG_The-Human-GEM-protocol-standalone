# Network analysis

## What this workflow is for

Inspect connectivity, identify formula-balance issues, and compact redundant
reactions after constructing, merging, or curating a model.

## When not to use it

Use [model comparison](comparison.md) for differences between two models and
[MEMOTE](memote.md) for broader quality diagnostics.

## Prerequisites and inputs

Provide a loaded COBRA model. Solver-backed cleanup and HTML visualization are
optional; connectivity and formula-balance checks run locally.

## Python API

Find components with [`find_network_components`][thg_protocol.analysis.network.find_network_components]
and persist them with [`write_component_report`][thg_protocol.analysis.network.write_component_report]:

```python
from thg_protocol.analysis import find_network_components, write_component_report

results = find_network_components(model)
write_component_report(results, "results/network/components.json")
```

Use [`full_compaction`][thg_protocol.analysis.compaction.full_compaction] for
proportional reactions, [`reaction_balance`][thg_protocol.analysis.consistency.reaction_balance]
for one reaction, and
[`unbalanced_reactions`][thg_protocol.analysis.consistency.unbalanced_reactions]
for a model-wide check.

## Outputs

Component analysis returns a graph and connectivity summary without mutation.
Compaction returns a copied model and removed IDs. Reports are written only to
explicit paths.

## Common errors

Unexpected disconnection usually indicates missing transport reactions or
compartment-specific IDs; inspect `component_info` before changing bounds.

## Next workflow

Use [gapfill](gapfill.md) for transport candidates, or
[figures and reports](figures.md) to present the results.
