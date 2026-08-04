# Model reconstruction

## What this workflow is for

Reconstruct a COBRA model when normalized records, a JSON record bundle, or a
historical pickle checkpoint is the authoritative input.

## When not to use it

Use [model enrichment](model-build.md) for an existing model, or
[pathway implementation](pathway.md) when the input is a pathway
configuration rather than records.

## Prerequisites and inputs

The normalized API needs metabolite IDs and reaction stoichiometry that refer
to known metabolites. JSON bundles contain `model_id`, `metabolites`, and
`reactions`, with optional `genes` and `pathways`. Pickle support is a
compatibility adapter and may require the `database` extra for `dill`.

## Python API

The deterministic entry point is [`reconstruct_model`][thg_protocol.database.reconstruct_model]:

```python
from thg_protocol.database import MetaboliteRecord, ReactionRecord, reconstruct_model

model = reconstruct_model(
    "toy",
    [MetaboliteRecord("a_c", compartment="c", formula="C1H2")],
    [ReactionRecord("R1", {"a_c": -1}, name="example")],
    output_path="results/toy.json",
)
```

For file and service boundaries use
[`reconstruct_model_from_json`][thg_protocol.database.reconstruct_model_from_json],
[`reconstruct_model_from_pickle`][thg_protocol.database.reconstruct_model_from_pickle],
and [`reconstruct_model_with_services`][thg_protocol.database.reconstruct_model_with_services].
Use [`summarize_biocyc_compartments`][thg_protocol.database.summarize_biocyc_compartments]
for loaded cache mappings and
[`parse_pathway_links`][thg_protocol.database_parsing.parse_pathway_links] for
independent KEGG parsing.

## Outputs

The functions return a COBRA model and write JSON or SBML only when an
explicit output path is supplied. Service enrichment uses injectable clients;
it does not hide network access. Pickle reconstruction performs no network
access.

## Common errors

Malformed bundles fail before output is written. A reaction referring to an
unknown metabolite indicates incomplete records. Do not commit generated
models, caches, or credentials.

## Next workflow

Run [network analysis](network-analysis.md) to check connectivity and balance,
or [model enrichment](model-build.md) to add external annotations.
