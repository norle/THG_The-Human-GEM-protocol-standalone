# Pathway implementation

## What this workflow is for

Add a defined biological pathway to a JSON model from an explicit pathway
configuration and metabolite-ID lookup table.

## When not to use it

Use [model reconstruction](database.md) for normalized records, or
[gapfill](gapfill.md) when the missing content is a transport candidate rather
than a defined pathway.

## Prerequisites and inputs

Provide a compatible JSON model, a configuration with compartment and reaction
definitions, and the ID database selected by that configuration.

## Python API

Apply file inputs with [`implement_pathway_files`][thg_protocol.pathway.workflow.implement_pathway_files]:

```python
from thg_protocol.pathway import implement_pathway_files

implement_pathway_files(
    "model.json", "pathway.json", "metabolite_ids.json", "results/model.json"
)
```

For in-memory data use [`implement_pathway`][thg_protocol.pathway.workflow.implement_pathway].
For a small KEGG reaction listing use
[`list_pathway_reactions`][thg_protocol.pathway.kegg_listing.list_pathway_reactions].

## CLI

```bash
thg-pathway --model model.json --config pathway.json \
  --database metabolite_ids.json --output results/pathway.json
```

## Outputs

The workflow writes the modified JSON model and returns counts of added
content. It does not select hidden repository-relative inputs.

## Common errors

A missing metabolite usually means its name is absent from the lookup database
or its compartment abbreviation does not match the model.

## Next workflow

Run [network analysis](network-analysis.md) to inspect the revised model, or
[model comparison](comparison.md) to review the change.
