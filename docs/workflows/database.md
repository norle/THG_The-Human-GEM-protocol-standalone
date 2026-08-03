# Database generation

Use database reconstruction when normalized records, JSON bundles, or a
historical pickle checkpoint are the authoritative input.

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
output path. KEGG, BioCyc, and Ensembl record collection remains behind
injectable service clients.

BioCyc compartment caches can be summarized without COBRA or file-system side
effects by passing their loaded mappings to `summarize_biocyc_compartments`:

```python
from thg_protocol.database import summarize_biocyc_compartments

summary = summarize_biocyc_compartments(location_cache, name_cache)
print(summary.unique_names)
```

KEGG pathway pages can be parsed independently of the orchestrator:

```python
from thg_protocol.database_parsing import parse_pathway_links

compound_links, reaction_links = parse_pathway_links(
    kgml_text, client=static_kegg_client
)
```

For a file-based workflow, use a JSON bundle containing `model_id`,
`metabolites`, `reactions`, optional `genes`, and optional `pathways`, then:

```python
from thg_protocol.database import reconstruct_model_from_json

reconstruct_model_from_json("records.json", output_path="results/model.xml")
```

Historical database checkpoints can be reconstructed without importing a
credentialed harvesting workflow:

```bash
python -m pip install "thg-protocol[database]"
```

```python
from thg_protocol.database import reconstruct_model_from_pickle

reconstruct_model_from_pickle("pre_sbml_pos_comp.pk", output_path="results/model.xml")
```

The pickle adapter accepts the historical `mets_cl`, `reactions_cl`, `genes`,
`pathways`, and `loc` bundle keys. Standard pickle is preferred; the
`database` extra installs `dill` for historical checkpoints. It performs no
network access.

Before running the workflow, provide the required reference tables and an
explicit output location. Do not commit generated database files, caches, or
credentials.

## Prerequisites, output, and troubleshooting

The normalized API requires record IDs and stoichiometry that reference known
metabolites. It returns a COBRA model and, when requested, writes JSON or SBML
to the explicit output path. Malformed bundles raise a validation error before
output is written.
