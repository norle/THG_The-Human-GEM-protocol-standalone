# Network analysis

Use network analysis to inspect connectivity, identify formula-balance issues,
and compact redundant reactions. Run it after constructing, merging, or
curating a model to understand the consequences of your changes.

Find connected components in a loaded COBRA model:

```python
from thg_protocol.analysis import find_network_components, write_component_report

results = find_network_components(model)
write_component_report(results, "results/network/components.json")
```

Component analysis does not change the model. Solver-backed cleanup and HTML
visualization are optional operations for larger investigations.

Proportional-reaction compaction is available separately:

```python
from thg_protocol.analysis import full_compaction

compacted, removed = full_compaction(model)
```

Blocked-reaction filtering is solver-dependent and only runs when explicitly
requested.

Formula-based consistency checks are also available without MEMOTE:

```python
from thg_protocol.analysis import reaction_balance, unbalanced_reactions

reaction_balance(model.reactions[0])
unbalanced_reactions(model)
```

## Prerequisites, output, and troubleshooting

Provide a loaded COBRA model and an explicit JSON report path when persistence
is needed. Component analysis returns a graph and connectivity summary without
mutation. An unexpectedly disconnected model usually indicates missing
transport reactions or compartment-specific IDs; inspect `component_info`.
