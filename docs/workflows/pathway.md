# Pathway implementation

!!! info "Status: Supported"
    `implement_pathway` and `implement_pathway_files`, plus the installed
    `thg-pathway` CLI, are maintained and covered by current tests.

## Outcome

Add a defined pathway's compartments, metabolites, and reactions to a JSON
model from explicit configuration and identifier data.

## Place in the THG protocol

Supporting model-enrichment operation; it is not mandatory in every THG
construction and is not a substitute for Human Database harvesting.

## When to use it

Use it when pathway content and the metabolite-ID mapping are already prepared.

## When not to use it

Use [model reconstruction](database.md) for normalized records or [gapfill](gapfill.md)
for deterministic transport candidates.

## Inputs

Provide a JSON model, pathway configuration, and metabolite-ID mapping. The
minimal repository examples are `quickstart_model.json`, `pathway_config.json`,
and `metabolite_ids.json`.

## Requirements

Local JSON inputs only; no network, credentials, or solver. The in-memory API
mutates its model mapping. The file wrapper writes a separate explicit output.

## Run from the command line

```bash
thg-pathway --model docs/examples/quickstart_model.json \
  --config docs/examples/pathway_config.json \
  --database docs/examples/metabolite_ids.json \
  --output runs/pathway/model.json
```

## Run from Python

```python
from thg_protocol.pathway import implement_pathway_files

result = implement_pathway_files(
    "docs/examples/quickstart_model.json",
    "docs/examples/pathway_config.json",
    "docs/examples/metabolite_ids.json",
    "runs/pathway/model.json",
)
print(result["compartments_added"])
```

## Outputs

The wrapper returns counts and writes one JSON model. It does not write caches or
reports and does not mutate the input file. The in-memory mapping is mutated;
make a copy when that is not desired.

## Inspect the result

Check added compartment/metabolite/reaction counts and inspect the resulting
JSON. Run [network analysis](network-analysis.md) and a model comparison.

## Common problems

Missing IDs usually indicate an incomplete lookup mapping or compartment
abbreviation mismatch. Invalid equations and duplicate IDs should be corrected
in the configuration.

## Next step

Use [network analysis](network-analysis.md), [comparison](comparison.md), or
the [Human Database protocol route](../protocol/human-database.md).

## API references

[`implement_pathway_files`][thg_protocol.pathway.workflow.implement_pathway_files],
[`implement_pathway`][thg_protocol.pathway.workflow.implement_pathway], and
[`list_pathway_reactions`][thg_protocol.pathway.kegg_listing.list_pathway_reactions].

## Differences from the historical workflow

The current operation consumes explicit local configuration and does not imply
that online pathway discovery or the complete branch from the 2023 protocol
paper occurred.
