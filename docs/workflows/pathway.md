# Pathway implementation

Use this workflow to apply a caller-authored pathway configuration to a JSON
model. It does not discover or silently download pathway definitions.

The import-safe pathway API transforms JSON model mappings without network
access or repository-relative output paths:

```python
from thg_protocol.pathway import implement_pathway_files

implement_pathway_files(
    "model.json", "pathway.json", "metabolite_ids.json", "results/model.json"
)
```

The equivalent installed CLI is `thg-pathway`; run `thg-pathway --help` for the
explicit input and output arguments.

```bash
thg-pathway --model model.json --config pathway.json \
  --database metabolite_ids.json --output results/pathway.json
```

KEGG pathway reaction listings are also available as an explicit, injectable
workflow:

```python
from thg_protocol.pathway import list_pathway_reactions

list_pathway_reactions("pathways.tsv", "results/pathway-reactions.tsv", limit=5)
```

## Prerequisites, output, and troubleshooting

Provide a compatible JSON model, a configuration with compartment and reaction
definitions, and the ID database selected by that configuration. The output is
the modified JSON model plus returned counts. A missing metabolite usually
means its name is absent from the lookup database or its compartment
abbreviation does not match the model.
