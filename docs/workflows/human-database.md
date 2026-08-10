# Human Database

## Workflow scope

The Human Database workflow reconstructs a model from normalized human
metabolite, reaction, gene, and pathway records. Offline reconstruction is a
first-class supported path and does not perform network access.

## Inputs and modes

Use a JSON record bundle with `metabolites` and `reactions`; `genes`,
`pathways`, and `model_name` are optional. Live or adapted collection is
performed through an injected adapter such as `harvest_snapshot`. Credentials,
network access, rate limits, and caches are caller-owned. A paper-specific
pathway-list adapter is not implied by workflow verification.

```python
from thg_protocol.database import reconstruct_model_from_json

model = reconstruct_model_from_json(
    "docs/examples/records.json",
    output_path="runs/human-database/network.json",
)
```

## Run with the CLI

The generic runner is intentional:

```json
{"format_version": 2, "workflow": "human-database",
 "run": {"name": "human-db", "output_dir": "runs/human-db"},
 "human_database": {"records": "docs/examples/records.json"}}
```

```bash
thg-run start human-database-config.json
```

## Outputs and validation

Keep the normalized input, reconstructed JSON/SBML model, pathway membership,
source/cache manifest, unresolved records, provenance, and validation report.
Run structural, formula-balance, connectivity, and comparison checks before
using the model as a merge input. Historical pickle input is compatibility
support, not evidence of a live harvesting pipeline.

See the [construction tool guide](../tools/model-construction.md) and
[construction API](../api/construction.md) for exact schemas and signatures.

Canonical APIs: [`reconstruct_model_from_json`][thg_protocol.database.reconstruct_model_from_json]
and [`harvest_snapshot`][thg_protocol.database_workflow.harvest_snapshot].
