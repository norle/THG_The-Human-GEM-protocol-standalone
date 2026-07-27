# Pathway implementation

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
