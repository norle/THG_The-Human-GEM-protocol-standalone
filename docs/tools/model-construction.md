# Model construction and enrichment

Use reconstruction when you have normalized records; use enrichment when you
already own a model and need explicit additions or corrections. Reconstruction
does not silently call external services. Inject service clients and retain
their caches when evidence is collected online.

```python
from thg_protocol.database import reconstruct_model_from_json
from thg_protocol.model_build import build_model

model = reconstruct_model_from_json("records.json")
report = build_model(model, config={})
```

Inputs and outputs are described in the [I/O reference](../reference/io-and-config.md).
For Human Database orchestration, see the [workflow guide](../workflows/human-database.md).
Exact signatures live in the [construction API](../api/construction.md).

Canonical APIs: [`reconstruct_model`][thg_protocol.database.reconstruct_model],
[`reconstruct_model_from_json`][thg_protocol.database.reconstruct_model_from_json],
and [`build_model`][thg_protocol.model_build.build_model].
