# Metabolite and reaction identification

The former `metabolite_reac_identification` workflow annotated a reference
model and matched reactions against the reference database. Its maintained
replacement is `thg_protocol.annotation.metabolite_reactions`.

JSON model annotation inventories are available through dependency-light APIs:

```python
from thg_protocol.annotation import (
    analyze_model_annotations,
    extract_metabolite_annotations,
)

counts = analyze_model_annotations("inputs/model.json")
annotations, missing = extract_metabolite_annotations(
    "inputs/model.json", ["ATP", "H2O"]
)
```

The package annotation APIs require explicit model and target inputs and can
write an optional JSON report.

Use explicit model, database, report, and SBML output paths. PubChem lookups
are owned by the injectable package client; tests should use a static client
and must not require network access.

EC-number GPR lookup is available through an injectable BioCyc/KEGG boundary:

```python
from thg_protocol.gpr import get_gpr

result = get_gpr("1.2.3.4", biocyc_client=static_biocyc, kegg_client=static_kegg)
```

The result preserves the five-field legacy shape while avoiding network access
when static clients are supplied.

Subcellular GPR rules use the analogous injectable location boundary:

```python
from thg_protocol.gpr.location import resolve_locations

rules = resolve_locations(
    gpr, gene_names, gene_ids, location_client=static_location_client
)
```
