# Metabolite and reaction identification

Use annotation to inventory model identifiers, enrich metabolites or reactions,
and resolve gene–protein–reaction (GPR) rules. This is useful when you need to
understand how complete a model is before using it for curation or analysis.

For a JSON model, start by checking the annotations already present:

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

The annotation functions can write an optional JSON report. Provide the model,
annotation targets, and any output path needed for your project. PubChem and
other external lookups require an appropriate client and may need network
access or credentials.

Resolve GPR candidates from an EC number with BioCyc and KEGG:

```python
from thg_protocol.gpr import get_gpr

result = get_gpr("1.2.3.4", biocyc_client=static_biocyc, kegg_client=static_kegg)
```

For subcellular GPR rules, resolve locations separately:

```python
from thg_protocol.gpr.location import resolve_locations

rules = resolve_locations(
    gpr, gene_names, gene_ids, location_client=static_location_client
)
```

## Prerequisites, output, and troubleshooting

Provide a model, annotation targets, and optional report/output paths. Live
clients may require credentials, network access, and service-specific rate
limits. Missing fields are reported as unmatched targets; check identifier
namespaces and compartment metadata when a lookup returns no result.
