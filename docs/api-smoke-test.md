# API smoke test

This smoke test verifies installation, model reconstruction, output writing,
and a local balance check. It does not represent the complete THG scientific
workflow.

```python
from pathlib import Path

from thg_protocol.analysis.consistency import unbalanced_reactions
from thg_protocol.database import MetaboliteRecord, ReactionRecord, reconstruct_model

output = Path("results/api-smoke-test/model.json")
model = reconstruct_model(
    "api-smoke-test",
    [
        MetaboliteRecord("a_c", compartment="c", name="A", formula="C1H2"),
        MetaboliteRecord("b_c", compartment="c", name="B", formula="C1H2"),
    ],
    [ReactionRecord("R_A_to_B", {"a_c": -1, "b_c": 1}, name="A to B")],
    output_path=output,
)
print(model.id, output, unbalanced_reactions(model))
```

The command writes `results/api-smoke-test/model.json` and prints an empty
unbalanced-reaction list. For a representative offline journey, use the
[practical quickstart](quickstart.md). For the scientific workflow, use the
[protocol overview](protocol/index.md).
