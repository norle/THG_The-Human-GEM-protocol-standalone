# Model construction and enrichment

Use reconstruction when you have normalized records; use enrichment when you
already own a model and need explicit additions or corrections. Reconstruction
does not silently call external services.

## Run with the CLI

For normalized records, save a Human Database configuration and run the
resumable workflow:

```bash
thg-run start configs/human-database.json
```

For a direct pathway enrichment, use the standalone command:

```bash
thg-pathway \
  --model inputs/models/model.json \
  --config inputs/pathway/config.json \
  --database inputs/pathway/metabolite-ids.json \
  --output runs/pathway/enriched-model.json
```

Low-level reconstruction and batch model building do not have separate CLI
commands; use the [Python construction API](../api/construction.md) for those
library operations. Inject service clients and retain their caches when
evidence is collected online.

Inputs and outputs are described in the [I/O reference](../reference/io-and-config.md).
For Human Database orchestration, see the [workflow guide](../workflows/human-database.md).
Exact signatures live in the [construction API](../api/construction.md).

Canonical APIs: [`reconstruct_model`][thg_protocol.database.reconstruct_model],
[`reconstruct_model_from_json`][thg_protocol.database.reconstruct_model_from_json],
and [`build_model`][thg_protocol.model_build.build_model].
