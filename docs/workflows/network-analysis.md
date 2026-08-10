# Network analysis

!!! info "Status: Supported"
    Connectivity, component, formula-balance, and compaction APIs are maintained
    and covered by current tests.

## Outcome

Identify disconnected components, formula imbalances, orphan/dead-end
metabolites, and selected redundant reactions.

## Place in the THG protocol

Core assessment building block after curation, reconstruction, or merge; it is
not equivalent to MEMOTE or metabolic-task analysis.

## When to use it

Use it at every documented checkpoint where a structural result must be
reviewed.

## When not to use it

Use [comparison](comparison.md) for differences or [MEMOTE](memote.md) for a
broad external quality assessment.

## Inputs

Most checks accept a loaded COBRA model; report writers accept the returned
mapping and an explicit output path.

## Requirements

Connectivity and formula balance run locally. Selected blocked/unbounded or
optimization checks can require a configured solver; no solver is implicit.

## Run from the command line

No installed network-analysis CLI exists. Use Python.

## Run from Python

```python
from cobra.io import load_json_model
from thg_protocol.analysis import find_network_components, write_component_report
from thg_protocol.analysis.consistency import unbalanced_reactions

model = load_json_model("runs/model.json")
components = find_network_components(model)
write_component_report(components, "runs/validation/components.json")
print(components["is_fully_connected"], unbalanced_reactions(model))
```

## Outputs

Analysis returns mappings/graphs and does not mutate the input. Component JSON
is written only to the explicit report path. Compaction returns a copied model
and removed IDs.

## Inspect the result

Review component counts, isolated nodes, formula atom totals, and any solver
status before deciding on transport, curation, or merge changes.

## Common problems

Disconnected compartments often indicate missing transports or mismatched IDs;
an unbalanced reaction may reflect missing formulas rather than bad
stoichiometry. Investigate before editing.

## Next step

Use [gapfill](gapfill.md) for candidate transports, [merge validation](../protocol/merge-and-validate.md),
or [MEMOTE](memote.md) for broader assessment.

## API references

[`find_network_components`][thg_protocol.analysis.network.find_network_components],
[`write_component_report`][thg_protocol.analysis.network.write_component_report],
[`full_compaction`][thg_protocol.analysis.compaction.full_compaction],
[`reaction_balance`][thg_protocol.analysis.consistency.reaction_balance], and
[`unbalanced_reactions`][thg_protocol.analysis.consistency.unbalanced_reactions].

## Differences from the historical workflow

The maintained structural checks do not restore archived full-model task or
solver-heavy assessment scripts.
