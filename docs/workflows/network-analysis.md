# Network analysis

Network components are available through an import-safe package API. It accepts
a caller-owned COBRA model and does not mutate it:

```python
from thg_protocol.analysis import find_network_components, write_component_report

results = find_network_components(model)
write_component_report(results, "results/network/components.json")
```

The package path performs connectivity analysis only. Solver-backed cleanup and
HTML visualization are optional operations outside the default package gate;
full-model runs should be marked `slow`.

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
