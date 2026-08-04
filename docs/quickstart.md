# Five-minute quickstart

This tutorial reconstructs a tiny model from normalized records, writes it to
a caller-owned directory, and runs a structural consistency check. It uses no
network service, solver, credential, or repository artifact.

## Prerequisites

Install the package in an environment with Python 3.10–3.12:

```bash
python -m pip install -e .
```

## Python workflow

```python
from pathlib import Path

from thg_protocol.analysis.consistency import unbalanced_reactions
from thg_protocol.database import MetaboliteRecord, ReactionRecord, reconstruct_model

output = Path("results/quickstart/model.json")
model = reconstruct_model(
    "quickstart",
    [
        MetaboliteRecord("a_c", compartment="c", name="A", formula="C1H2"),
        MetaboliteRecord("b_c", compartment="c", name="B", formula="C1H2"),
    ],
    [ReactionRecord("R_A_to_B", {"a_c": -1, "b_c": 1}, name="A to B")],
    output_path=output,
)
print(model.id, output, unbalanced_reactions(model))
```

The output is a COBRA JSON model at `results/quickstart/model.json`; the
output directory is created as needed. For a reusable input bundle, use
[`reconstruct_model_from_json`][thg_protocol.database.reconstruct_model_from_json]
as shown in the [database guide](workflows/database.md).

## What to try next

- Add deterministic transport candidates with the [gapfill workflow](workflows/gapfill.md).
- Implement configured reactions with the [pathway workflow](workflows/pathway.md).
- Compare two JSON or SBML models with [model comparison](workflows/comparison.md).
- Read the [API reference](api/index.md) for ownership, optional dependencies,
  exceptions, and file-format details.
- Use the [task guides](usage.md) when you are ready to choose a different
  workflow.

## Troubleshooting

`KeyError` for a reaction metabolite means the normalized reaction refers to an
ID absent from the metabolite records. Add that record or correct the
stoichiometry. If an output file is unexpectedly absent, check that the
caller-selected parent directory is writable and that `output_path` has the
intended `.json` or SBML suffix.
