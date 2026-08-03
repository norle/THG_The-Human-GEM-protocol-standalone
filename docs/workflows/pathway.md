# Pathway implementation

Use this workflow to add a defined biological pathway to a JSON model. You
provide the pathway configuration and metabolite-ID lookup table, so the
reactions and compartments being added are explicit and reviewable.

In Python, apply the configuration with:

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

If you need a small reaction listing for a set of KEGG pathways, use:

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
