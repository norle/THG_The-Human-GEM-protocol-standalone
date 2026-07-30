# Database generation

The normalized reconstruction core is available without network access:

```python
from thg_protocol.database import (
    MetaboliteRecord,
    ReactionRecord,
    reconstruct_model,
)

model = reconstruct_model(
    "toy",
    [MetaboliteRecord("a_c", compartment="c", formula="C1H2")],
    [ReactionRecord("R1", {"a_c": -1}, name="example")],
    output_path="results/toy.json",
)
```

For service-backed enrichment of normalized records, use
`reconstruct_model_with_services` and pass static clients in tests. It fetches
only the KEGG/BioCyc/Ensembl annotations represented by the supplied records,
then delegates to the same deterministic reconstruction core.

The API accepts normalized records and writes only to the caller-provided
output path. KEGG, BioCyc, and Ensembl record collection remains in the
deferred legacy orchestrator and must use injectable service clients.

For a file-based workflow, use a JSON bundle containing `model_id`,
`metabolites`, `reactions`, optional `genes`, and optional `pathways`, then:

```python
from thg_protocol.database import reconstruct_model_from_json

reconstruct_model_from_json("records.json", output_path="results/model.xml")
```

Legacy database-generator checkpoints can be reconstructed without importing
the credentialed harvesting workflow:

```python
from thg_protocol.database import reconstruct_model_from_pickle

reconstruct_model_from_pickle("pre_sbml_pos_comp.pk", output_path="results/model.xml")
```

The pickle adapter accepts the historical `mets_cl`, `reactions_cl`, `genes`,
`pathways`, and `loc` bundle keys. Standard pickle is preferred; historical
`dill` pickles require the optional `dill` package. It performs no network
access.

Before running the workflow, provide the required reference tables and an
explicit output location. Do not commit generated database files, caches, or
credentials.
