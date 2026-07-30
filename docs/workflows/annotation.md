# Metabolite and reaction identification

The legacy `metabolite_reac_identification` workflow annotates a reference
model and matches reactions against the reference database. Its characterized
package entry point is `thg_protocol.annotation.metabolite_reactions`.

Use explicit model, database, report, and SBML output paths. PubChem lookups
are owned by the injectable package client; tests should use a static client
and must not require network access.

The retry compatibility script remains available for existing checkouts:

```bash
python metabolite_reac_identification/metabolite_reac_identification_with_retry.py --help
```

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
