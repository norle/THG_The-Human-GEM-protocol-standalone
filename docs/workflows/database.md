# Model reconstruction

!!! info "Status: Supported"
    The maintained `thg_protocol.database` API reconstructs models from
    normalized records. The Phase 4 `database_workflow` API adds explicit
    snapshot caching, error ledgers, and a registered offline workflow.

## Outcome

Create a COBRA model from explicit metabolite, reaction, gene, and pathway
records. This is the deterministic core of the Human Database branch; it does
not harvest online services by itself.

## Place in the THG protocol

Core building block for the Human Database branch or a standalone local task.
It is not proof that the 2023 protocol paper's live pathway-harvesting stage
has been reproduced.

## When to use it

Normalized records, `docs/examples/records.json`, or a supported JSON record
bundle provide the reproducible model-construction input.

## When not to use it

Use [model enrichment](model-build.md) for an existing model. A pathway list
and online sources alone require the [Human Database protocol page](../protocol/human-database.md)
because complete live harvesting is outside the maintained reconstruction API.

## Inputs

`MetaboliteRecord` requires `id`; `ReactionRecord` requires `id` and a
stoichiometry mapping whose IDs exist in the metabolite set. Optional records
carry annotations, bounds, GPRs, genes, and pathways. The JSON schema is
described in [Inputs and file formats](../data-and-model-files.md).

## Requirements

Core reconstruction is local and needs no credentials, network, or solver. The
`database` extra is required only for historical pickle input. Inject service
clients into `reconstruct_model_with_services` when enrichment is intentional.

## Run from the command line

No installed model-reconstruction CLI exists. Use the Python API or a caller
script with explicit paths.

## Run from Python

```python
from pathlib import Path

from thg_protocol.database import reconstruct_model_from_json

model = reconstruct_model_from_json(
    Path("docs/examples/records.json"),
    output_path=Path("results/reconstruction/model.json"),
)
print(model.id, len(model.reactions))
```

## Outputs

The function returns a new COBRA model and writes JSON for a `.json` output
path; other suffixes are written as SBML. Inputs are not mutated. Pure
reconstruction creates no cache or report.

## Inspect the result

Check model ID/counts, reaction metabolite IDs, pathway groups, formulas, and
GPRs. Then run [network analysis](network-analysis.md) and
`unbalanced_reactions` for structural checks.

## Common problems

`KeyError` means a reaction references a missing metabolite. Duplicate IDs are
rejected. A pickle import failure usually means the optional `database` extra
or the historical payload shape is missing.

## Next step

Continue to the [Human Database protocol branch](../protocol/human-database.md)
or [model enrichment](model-build.md).

## API references

[`reconstruct_model`][thg_protocol.database.reconstruct_model],
[`reconstruct_model_from_json`][thg_protocol.database.reconstruct_model_from_json],
[`reconstruct_model_from_pickle`][thg_protocol.database.reconstruct_model_from_pickle],
[`reconstruct_model_with_services`][thg_protocol.database.reconstruct_model_with_services],
[`summarize_biocyc_compartments`][thg_protocol.database.summarize_biocyc_compartments],
[`harvest_snapshot`][thg_protocol.database_workflow.harvest_snapshot],
[`normalize_records`][thg_protocol.database_workflow.normalize_records],
[`reconstruct_snapshot`][thg_protocol.database_workflow.reconstruct_snapshot],
and [`parse_pathway_links`][thg_protocol.database_parsing.parse_pathway_links].

## Differences from the historical workflow

The package consumes normalized records at its boundary and does not claim to
perform the paper's complete online pathway harvest.
