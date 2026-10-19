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
  "workflow": "beta2",
  "run": {"name": "example-beta2", "output_dir": "../runs/example-beta2"},
  "beta2": {
    "n_jobs": 1,
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

Save the configuration as `configs/beta2.json` and run:

```bash
thg-run beta2 configs/beta2.json
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
an implicit cytosol. When same-precedence sources disagree about sGPR
structure, all candidates are retained and the more conservative structure is
selected while the conflict is reported. An existing model GPR remains
preferred; database evidence supplies a GPR only when the model has none and
the evidence is `authoritative`, `strong` or `reaction-matched`.
`fallback_location` is an explicit configuration choice. Exchange, demand,
sink, biomass, pseudo, spontaneous, transport, and multi-compartment reactions
are reported and excluded from generic cloning. Set `n_jobs` above 1 to
parallelize GPR and localization resolution; expansion application and solver
work remain serial.

## Compartment expansion

1. **Gene locations.** Locations set by hand in `gene_locations` override every
   other source. Otherwise each gene pools the annotations from
   `location_sources` (GOA and UniProt in the shipped configs). Neither source
   takes precedence. The gene record lists every contributor in `sources`,
   each raw location keeps its own `source`, and `confidence` is `strong` when
   GOA contributed. In live mode, genes with nothing from these sources fall
   back to an older UniProt text lookup. `goa_excluded_evidence_codes` drops
   GOA annotations by evidence code (empty by default).
2. **Location to compartment.** When `compartment_go_terms` ties each
   compartment to a GO term, an annotation starts at its GO ID, or at the GO
   term whose name or synonym matches its text exactly. The resolver walks up
   GO through `is_a` and `part_of` and keeps **every** configured compartment
   it reaches, dropping a compartment that contains another one reached. For
   example, axonemal microtubule resolves to cilium and cytoskeleton, and
   mitochondrial inner membrane resolves to `i` rather than `m`.
   `compartment_go_aliases` maps a term to a compartment only when an
   annotation names exactly that term (the shipped config maps cytoplasm to
   cytosol). Without `compartment_go_terms`, locations are matched against
   compartment names and the BioCyc CCO graph, which picks the nearest single
   compartment.
3. **Per gene.** A gene keeps the union of its compartments. A gene in several
   compartments is dual-located, not in conflict. `uncertainty_policy`
   (`reject-conflicts` or `allow-conflicts`) applies only to gene records that
   arrive already marked `conflicting`, for example from a snapshot.
4. **Per reaction.** `A or B` takes the union of the genes' compartments, and
   `A and B` the intersection, so a complex is placed only where every subunit
   is present. If the genes give no compartment, the reaction's own location
   from `reaction_sources` (for example Reactome) is used.
5. **Expansion.** Only internal reactions with a GPR are eligible. Each
   resolved compartment becomes a proposal to copy the reaction there with
   compartment-specific metabolites. The original reaction is always kept, and
   no copy is made when an equivalent reaction already exists in the target
   compartment. A reaction with no compartment evidence keeps its original
   compartment.

## Stages

The resumable DAG is:

```text
load-beta1 → collect-catalysis-evidence → collect-gpr-evidence → resolve-gprs
  → normalize-compartments
  → collect-location-evidence → collect-reaction-location-evidence
  → resolve-compartment-evidence
  → infer-complex-and-isoenzyme-locations → generate-expansion-plan
  → apply-expansion-decisions → apply-expansion
  → consolidate-expanded-model → validate-beta2 → export-beta2
```

The export contains JSON/SBML candidates, expansion plan, shared-schema
proposals, deterministic ID registry, change ledger, location evidence,
validation, semantic β1-to-β2 diff, unresolved records, provenance, and a
summary. Resume reuses valid attempts; forcing a stage invalidates that stage
and its descendants while preserving previous attempt directories.

## Required canonical gapfill and standalone use

For the reproducible scientific pipeline, use the first-class `reference` or
`gapfill` workflow. The direct command below remains useful for ad-hoc
algorithm work and does not select the downstream model automatically.

Gap filling is separate from the β2 stage, but it is the required next
model-construction step in the canonical THG pipeline. Optional Human Database
integration occurs before it. The lower-level command can also be used
independently for ad-hoc work. For example:

```bash
thg-gapfill --model runs/beta2/artifacts/export-beta2/attempt-0001/thg-beta2-candidate.json --method greedy --output-dir runs/beta2-gapfill
```

The same command accepts external JSON or SBML models. In standalone use, the
caller chooses whether downstream work consumes its original model or the
gapfilled output; canonical construction always continues with the gapfilled
output.

Python callers can use the release-gate and promotion helpers documented in the
[workflow API reference](../api/workflows.md), including
[`resolve_gpr_locations`][thg_protocol.curation.beta2.resolve_gpr_locations],
[`generate_expansion_plan`][thg_protocol.curation.beta2.generate_expansion_plan],
[`apply_expansion_plan`][thg_protocol.curation.beta2.apply_expansion_plan],
[`beta2_release_gate`][thg_protocol.curation.beta2.beta2_release_gate] and
[`release_beta2`][thg_protocol.curation.beta2.release_beta2].

## Candidate and release-gate lifecycle

The workflow writes candidate JSON/SBML artifacts and supporting evidence.
`beta2_release_gate` checks the required upstream and validation conditions;
`release_beta2` promotes the candidate only after the gate passes. An external
β1-equivalent input must be explicitly declared and its evidence preserved.
