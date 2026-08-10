# THGβ2 — Expand by GPR and location

## Workflow scope

THGβ2 consumes a verified β1 artifact, resolves GPR and localization evidence,
plans compartment expansion, applies explicit decisions, and validates a
candidate model.

β2 consumes either a checksum-verified `export-beta1` model artifact or an
explicitly declared external β1-equivalent input. It normalizes recorded
catalysis and localization evidence, evaluates canonical GPR branches, writes
the complete expansion plan and proposals, then mutates a copied model.

For a direct external input, the configuration must include:

```json
{
  "format_version": 2,
  "workflow": "beta2",
  "run": {"name": "example-beta2", "output_dir": "../runs/example-beta2"},
  "beta2": {
    "input_model": "../inputs/models/beta1-equivalent.json",
    "external_beta1_equivalent": true,
    "mode": "apply-all",
    "gene_locations": {
      "GENE_A": ["mitochondrion"],
      "GENE_B": ["cytosol"]
    },
    "compartments": {"c": "cytosol", "m": "mitochondria"}
  }
}
```

For a maintained run, reference the β1 export:

```json
"upstream": {
  "run_dir": "../runs/beta1",
  "stage_id": "export-beta1",
  "role": "model"
}
```

`A or B` is localized by union and `A and B` by intersection. Unsupported
complex branches are retained in the evidence report rather than assigned to
an implicit cytosol. `fallback_location` and `uncertainty_policy` are explicit
configuration choices. Exchange, demand, sink, biomass, pseudo, spontaneous,
transport, and multi-compartment reactions are reported and excluded from
generic cloning.

The resumable DAG is:

```text
load-beta1 → collect-catalysis-evidence → resolve-gprs
  → collect-location-evidence → normalize-compartments
  → infer-complex-and-isoenzyme-locations → generate-expansion-plan
  → apply-expansion-decisions → apply-expansion
  → consolidate-expanded-model → validate-beta2 → export-beta2
```

The export contains JSON/SBML candidates, expansion plan, shared-schema
proposals, deterministic ID registry, change ledger, location evidence,
validation, semantic β1-to-β2 diff, unresolved records, provenance, and a
summary. Resume reuses valid attempts; forcing a stage invalidates that stage
and its descendants while preserving previous attempt directories.

Python release API:

- [`thg_protocol.curation.beta2.resolve_gpr_locations`](../api/workflows.md#thg_protocol.curation.beta2.resolve_gpr_locations)
- [`thg_protocol.curation.beta2.generate_expansion_plan`](../api/workflows.md#thg_protocol.curation.beta2.generate_expansion_plan)
- [`thg_protocol.curation.beta2.apply_expansion_plan`](../api/workflows.md#thg_protocol.curation.beta2.apply_expansion_plan)
- [`thg_protocol.curation.beta2.beta2_release_gate`](../api/workflows.md#thg_protocol.curation.beta2.beta2_release_gate)
- [`thg_protocol.curation.beta2.release_beta2`](../api/workflows.md#thg_protocol.curation.beta2.release_beta2)

```python
from thg_protocol.curation.beta2 import beta2_release_gate, release_beta2

gate = beta2_release_gate("runs/example-beta2/artifacts/export-beta2/attempt-0001")
if gate["passed"]:
    release_beta2("runs/example-beta2/artifacts/export-beta2/attempt-0001")
```

## Candidate and release-gate lifecycle

The workflow writes candidate JSON/SBML artifacts and supporting evidence.
`beta2_release_gate` checks the required upstream and validation conditions;
`release_beta2` promotes the candidate only after the gate passes. An external
β1-equivalent input must be explicitly declared and its evidence preserved.
