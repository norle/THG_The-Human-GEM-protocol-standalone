# Network analysis

Network components are available through an import-safe package API. It accepts
a caller-owned COBRA model and does not mutate it:

```python
from thg_protocol.analysis import find_network_components, write_component_report

results = find_network_components(model)
write_component_report(results, "results/network/components.json")
```

The package path performs connectivity analysis only. Solver-backed cleanup and
HTML visualization remain optional legacy operations; full-model runs should be
marked `slow`.
