# β2 evidence-driven expansion plan

## Goal

Extend the existing β2 DAG so it follows the legacy principle without porting the legacy batch script: start from a β1 model, collect reproducible GPR and localization evidence, resolve specific evidence locations to the explicitly configured β2 target compartments, then generate compartment-specific copies of eligible reactions.

```text
β1 export
  → extract ECs + existing GPRs
  → resolve missing GPRs from recorded/live evidence
  → normalize the configured β2 compartment registry
  → resolve gene and reaction localization evidence
  → resolve specific BioCyc CCO locations to configured β2 compartments
  → combine localization evidence
  → generate proposal-first β2 expansions
  → validate and export
```

This is not a database-to-model-construction workflow. The Human Database workflow remains a separate reconstruction and merge input.

BioCyc, KEGG, Ensembl, UniProt-style location evidence, and BioCyc Cell Component Ontology data are evidence sources only. They do not define which compartments β2 is allowed to create. The `beta2.compartments` configuration remains authoritative.

---

## 1. Define an offline-first β2 evidence contract

Add these keys to the `beta2` section in `src/thg_protocol/workflow/config.py`:

```json
{
  "evidence_mode": "provided",
  "evidence_file": "../inputs/evidence/beta2.jsonl",
  "gpr_policy": "model-then-ec",
  "location_policy": "provided-then-evidence",
  "compartments": {
    "c": "cytosol",
    "m": "mitochondria"
  }
}
```

Supported evidence modes:

* `provided`

  * Preserve deterministic configuration-only behavior.
  * Use configured `gene_locations`.
  * Use configured aliases and direct compartment matches.
  * Make no external network calls.

* `snapshot`

  * Read a versioned JSONL evidence snapshot.
  * Make no external network calls.
  * Reproduce GPR, location, BioCyc CCO, and compartment-resolution evidence from the recorded snapshot.

* `live`

  * Opt in to external evidence retrieval.
  * Use the existing BioCyc/KEGG, Ensembl, and location-client boundaries.
  * Retrieve BioCyc CCO information when needed for compartment resolution.
  * Write a complete run-owned evidence snapshot that can subsequently be replayed in `snapshot` mode.

Use:

```text
gpr_policy = model-then-ec
```

A valid β1 GPR takes precedence. EC-based evidence is used only when the model GPR is missing, empty, or unparsable.

A valid model rule:

* contains at least one gene; and
* passes the existing GPR parser.

Conflicting external GPR evidence must be recorded as evidence rather than silently replacing a valid model rule.

Use:

```text
location_policy = provided-then-evidence
```

Location evidence is merged according to explicit precedence rules defined below.

The `compartments` mapping is the complete registry of legal β2 expansion targets:

```json
{
  "c": "cytosol",
  "m": "mitochondria"
}
```

Keys are model compartment IDs.

Values are normalized biological display names.

This registry is independent of `model.compartments` and must not be inferred from β1.

Adding a new legal β2 target requires explicitly adding it here.

Do not restore or read the legacy Excel/pickle compartment mappings at runtime.

---

## 2. Add a GPR-evidence stage

Add `collect-gpr-evidence` between `collect-catalysis-evidence` and `resolve-gprs` in `src/thg_protocol/workflow/beta2_stages.py`.

The revised early DAG becomes:

```text
load-beta1
→ collect-catalysis-evidence
→ collect-gpr-evidence
→ resolve-gprs
→ normalize-compartments
```

For reactions without a usable β1 GPR:

1. Extract EC numbers from the catalysis evidence.
2. Group requests by unique EC number.
3. Call the existing `thg_protocol.gpr.lookup.get_gpr` once per unique EC.
4. Associate the resulting candidate GPR evidence back to every applicable reaction.

Persist normalized reaction-level records containing at least:

```json
{
  "reaction_id": "R1",
  "ec": "1.2.3.4",
  "candidate_gpr": "(GENE1) or (GENE2)",
  "gene_symbols": ["GENE1", "GENE2"],
  "gene_identifiers": ["..."],
  "source": "biocyc",
  "status": "candidate",
  "warnings": []
}
```

If both BioCyc and KEGG participate in lookup, preserve the effective source and any fallback information.

`resolve-gprs` then applies `gpr_policy`.

For `model-then-ec`:

* valid β1 GPR → retain model rule;
* missing β1 GPR → use external candidate when usable;
* invalid β1 GPR → external evidence may supply a candidate;
* valid model/external disagreement → retain model rule and record a conflict;
* unusable model and unusable evidence → unresolved.

Do not silently union arbitrary conflicting GPRs.

---

## 3. Normalize the configured β2 compartment registry before resolving evidence

Move `normalize-compartments` ahead of localization resolution.

The purpose of this stage is only to normalize the explicitly configured registry.

For example:

```json
{
  "c": "cytosol",
  "m": "mitochondria",
  "x": "peroxisome"
}
```

becomes a deterministic internal registry such as:

```json
{
  "c": "Cytosol",
  "m": "Mitochondria",
  "x": "Peroxisome"
}
```

Use the existing location alias normalization where appropriate.

The stage must not:

* inspect β1 compartments to discover allowed targets;
* add targets discovered from BioCyc;
* add targets discovered from UniProt or Ensembl;
* infer missing compartment IDs;
* read legacy mapping files.

The resulting registry is the sole authority used by downstream compartment resolution and expansion.

---

## 4. Make location evidence automatic when requested

Extend `collect-location-evidence` so it collects gene-level localization evidence from the configured evidence sources.

Merge evidence in this precedence order:

1. Explicit `gene_locations` in configuration.
2. Snapshot evidence.
3. Live evidence.

Explicit configuration therefore remains able to override external evidence intentionally.

For live evidence:

1. Resolve gene identifiers through the existing Ensembl client boundary where necessary.
2. Resolve subcellular locations through the existing location-client boundary.
3. Preserve raw location strings before normalization.
4. Persist one normalized evidence record per gene.
5. Preserve ambiguous, conflicting, and unresolved results rather than dropping them.

Example:

```json
{
  "gene_id": "GENE1",
  "raw_locations": [
    "Mitochondrial inner membrane"
  ],
  "source": "uniprot",
  "status": "resolved",
  "identifiers": {
    "ensembl": "ENSG..."
  }
}
```

Do not assign an unresolved gene to cytosol implicitly.

Retain the existing explicit `fallback_location` option.

Fallback use must be visible in evidence provenance.

---

## 5. Collect BioCyc reaction-location evidence separately

BioCyc may provide reaction-level compartment information in addition to gene-level localization evidence.

Collect this evidence separately rather than pretending it is gene localization.

For each applicable reaction, preserve candidate BioCyc compartment terms, including BioCyc CCO identifiers when available.

Example:

```json
{
  "reaction_id": "R1",
  "source": "biocyc",
  "locations": [
    {
      "raw_location": "mitochondrial inner membrane",
      "cco_id": "CCO-..."
    }
  ],
  "status": "candidate"
}
```

Reaction-location evidence must not silently replace GPR-derived gene localization.

Instead:

* agreement strengthens provenance;
* reaction evidence may provide a candidate when gene-localization evidence is absent;
* disagreement is recorded as a conflict;
* unresolved or ambiguous BioCyc evidence does not cause expansion automatically.

Keep database-derived reaction localization as evidence, not as a mutation instruction.

---

## 6. Add BioCyc CCO-aware compartment resolution

Add a dedicated `resolve-compartment-evidence` stage.

Recommended DAG:

```text
load-beta1
→ collect-catalysis-evidence
→ collect-gpr-evidence
→ resolve-gprs
→ normalize-compartments
→ collect-location-evidence
→ collect-reaction-location-evidence
→ resolve-compartment-evidence
→ infer-complex-and-isoenzyme-locations
→ generate-expansion-plan
→ apply-expansion-decisions
→ apply-expansion
→ consolidate-expanded-model
→ validate-beta2
→ export-beta2
```

If reaction-level BioCyc localization is collected within `collect-location-evidence` instead of a separate stage, that is acceptable, but gene-level and reaction-level evidence must remain distinguishable in the output schema.

### Resolution principle

Specific evidence locations should be reduced to a configured β2 target when an explicit biological relationship supports doing so.

For example:

```text
mitochondrial inner membrane
    ↓
mitochondrion
    ↓
Mitochondria
    ↓
configured target "m"
```

The resolution order should be:

1. Normalize whitespace and capitalization.
2. Apply existing deterministic aliases.
3. Attempt an exact normalized match against configured compartment display names.
4. If a BioCyc CCO identifier is available, resolve that identifier.
5. If only a BioCyc location name is available, perform exact CCO name/synonym resolution.
6. Traverse the recorded CCO relationships toward broader cellular components.
7. Stop when a configured β2 target is reached.
8. Reject the location when no configured target can be reached.
9. Reject as ambiguous when equally valid paths reach multiple configured targets.

Do not perform fuzzy biological string matching.

For example, do not guess that an arbitrary term containing `membrane` belongs to `Mitochondria`.

---

## 7. Traverse the relevant CCO relationships conservatively

The BioCyc Cell Component Ontology contains more than a simple lexical hierarchy.

The compartment resolver should support relevant broader/containment relationships such as:

```text
specific CCO term
→ superclass
→ broader CCO term
```

and:

```text
specific cellular component
→ COMPONENT-OF
→ enclosing organelle/component
```

`COMPONENT-OF` is particularly important for model-level compartment reduction.

Examples:

```text
mitochondrial inner membrane
→ component-of
→ mitochondrion
→ Mitochondria
→ m
```

```text
mitochondrial intermembrane space
→ component-of
→ mitochondrion
→ Mitochondria
→ m
```

```text
peroxisomal membrane
→ component-of
→ peroxisome
→ Peroxisome
→ x
```

Prefer the nearest configured target.

Prefer explicit containment relationships such as `COMPONENT-OF` over a generic superclass when both produce competing candidates.

Do not use spatial-neighbor relations such as `SURROUNDED-BY` or `SURROUNDS` as if they meant containment.

Those relationships could otherwise incorrectly turn membrane evidence into lumen, cytosol, or extracellular evidence.

Never traverse from a broad term downward to guess a specific configured target.

For example:

```text
membrane
```

must not automatically become:

```text
plasma membrane
```

or:

```text
mitochondria
```

unless the evidence graph explicitly establishes the relationship.

---

## 8. Keep CCO resolution deterministic and offline-replayable

Separate CCO retrieval from CCO resolution.

The pure resolver should be network-free.

Conceptually:

```text
resolve_compartment(
    raw_location,
    optional_cco_id,
    recorded_cco_graph,
    configured_registry
)
```

returns a normalized resolution record.

The live BioCyc client is responsible only for retrieving the CCO term and its relevant relationships.

Persist the information required for replay into the evidence snapshot.

A snapshot must contain enough information to reproduce the decision without querying the current BioCyc ontology.

For example:

```json
{
  "raw_location": "mitochondrial inner membrane",
  "normalized_location": "mitochondrial inner membrane",
  "source": "biocyc",
  "cco_id": "CCO-MIT-IMEM",
  "cco_name": "mitochondrial inner membrane",
  "status": "resolved",
  "resolution_method": "cco-component-of",
  "resolution_path": [
    {
      "cco_id": "CCO-MIT-IMEM",
      "name": "mitochondrial inner membrane"
    },
    {
      "relation": "component-of",
      "cco_id": "CCO-MIT",
      "name": "mitochondrion"
    }
  ],
  "target_compartment_id": "m",
  "target_compartment_name": "Mitochondria"
}
```

For an unsupported location:

```json
{
  "raw_location": "some specific compartment",
  "source": "biocyc",
  "cco_id": "CCO-...",
  "status": "rejected",
  "reason": "location-not-in-registry"
}
```

For competing valid targets:

```json
{
  "status": "rejected",
  "reason": "ambiguous-compartment-resolution",
  "candidate_targets": [
    "m",
    "x"
  ]
}
```

Record BioCyc/CCO version or retrieval metadata where available.

A `snapshot` replay must not re-fetch ontology data.

---

## 9. Resolve gene localization before GPR location logic

Feed only successfully normalized target-compartment names into `resolve_gpr_locations`.

The flow becomes:

```text
raw gene location evidence
→ alias normalization
→ CCO resolution where applicable
→ configured β2 target
→ resolve_gpr_locations
```

This keeps Boolean GPR logic independent of database-specific compartment vocabulary.

Continue using the existing GPR-location semantics:

* OR → union of valid locations;
* AND → intersection/co-localization;
* missing required subunit location → unresolved/rejected;
* explicit fallback only when configured.

Example:

```text
A → mitochondrial inner membrane
B → mitochondrion
```

first resolves to:

```text
A → Mitochondria
B → Mitochondria
```

then:

```text
A and B
→ Mitochondria
```

This avoids incorrectly treating two different BioCyc subcompartment labels as biologically incompatible when both reduce to the same configured β2 compartment.

---

## 10. Define evidence-conflict behavior explicitly

Gene-level, reaction-level, model-level, and external evidence must not silently overwrite one another.

For localization:

### Gene evidence supports one target

Use the supported target.

### Multiple gene sources resolve to the same target

Retain the target and combine provenance.

### One source gives a specific CCO child and another gives its configured parent

Treat them as agreement after CCO reduction.

Example:

```text
BioCyc: mitochondrial inner membrane
UniProt: mitochondrion
```

both resolve to:

```text
Mitochondria
```

### Sources resolve to different configured targets

Record a conflict.

Do not choose arbitrarily.

Example:

```text
BioCyc → Mitochondria
UniProt → Cytosol
```

produces evidence such as:

```text
location-conflict
```

unless an explicit configured precedence rule applies.

### Evidence does not resolve to a configured target

Produce:

```text
location-not-in-registry
```

### CCO graph reaches multiple equally valid targets

Produce:

```text
ambiguous-compartment-resolution
```

No implicit cytosol fallback.

---

## 11. Keep the configured β2 registry authoritative

Every expansion location must eventually resolve to:

```text
configured compartment ID
+
configured normalized display name
```

For example:

```json
{
  "x": "mitochondria",
  "i": "cytosol"
}
```

must be valid even if β1 uses different IDs.

BioCyc resolution should therefore produce:

```json
{
  "target_compartment_id": "x",
  "target_compartment_name": "Mitochondria"
}
```

not a hard-coded `m`.

The workflow must never assume conventional IDs such as:

```text
c
m
n
p
```

The configured IDs are authoritative.

A β1 model may contain additional source compartments, but they do not become legal β2 expansion targets unless explicitly listed under `beta2.compartments`.

---

## 12. Reuse the existing expansion engine

Keep `generate_expansion_plan` and `apply_expansion_plan` as the mutation mechanism.

They already provide the desired architecture:

* compartment-specific reaction copies;
* compartment-specific metabolite copies;
* bounds preservation;
* provenance preservation;
* group preservation;
* deterministic IDs;
* duplicate/equivalent chemistry checks;
* proposal-first mutation;
* existing validation hooks.

Do not port legacy:

* reaction-ID heuristics;
* string-based equation parsing;
* destructive post-processing;
* fuzzy compartment mappings;
* Excel/pickle runtime mappings;
* old cache semantics.

The expansion engine should receive already-resolved normalized compartment evidence.

It should not know about BioCyc CCO.

---

## 13. Produce rejected proposals for unsupported localization

Evidence outside the legal target registry should remain visible in proposal/report outputs.

For example:

```json
{
  "reaction_id": "R1",
  "raw_location": "lysosomal membrane",
  "status": "rejected",
  "reason": "location-not-in-registry"
}
```

if lysosome is not configured.

Do not silently discard it.

Similarly preserve:

```text
ambiguous-compartment-resolution
location-conflict
unresolved-location
missing-gene-location
required-subunit-location-intersection-is-empty
```

where applicable.

This makes it possible to inspect why reactions were not expanded.

---

## 14. Export reproducible evidence

Export at minimum:

```text
gpr-evidence.jsonl
location-evidence.jsonl
reaction-location-evidence.jsonl
compartment-resolution-evidence.jsonl
beta2-evidence-snapshot.jsonl
beta2-unresolved.tsv
```

The combined snapshot should contain all external information needed to reproduce the expansion plan offline.

It should include:

* EC evidence;
* external GPR candidates;
* selected GPR and policy decision;
* gene identifiers;
* raw gene locations;
* raw reaction locations;
* BioCyc CCO IDs;
* CCO names/synonyms used for exact matching;
* relevant CCO edges used during resolution;
* CCO resolution paths;
* target compartment IDs;
* conflict states;
* unresolved states;
* source/version/retrieval metadata where available.

Continue exporting the existing:

```text
expansion plan
proposal ledger
ID registry
change ledger
model diff
validation
provenance
```

---

## 15. Make snapshot replay an explicit reproducibility guarantee

A completed `live` run must be replayable using:

```text
evidence_mode = snapshot
```

without any BioCyc, KEGG, Ensembl, UniProt, or other network calls.

Given:

* the same β1 input;
* the same β2 configuration;
* the generated evidence snapshot;
* the same software version;

the replay should produce an identical normalized evidence set and expansion plan.

Where practical, test equality of deterministic artifacts byte-for-byte.

At minimum verify semantic equality of:

```text
resolved GPRs
resolved compartment evidence
expansion proposals
deterministic IDs
```

---

## 16. Make resumability evidence-aware

Completed evidence stages should not re-fetch data during a normal resume.

For example:

```text
resume
```

after successful:

```text
collect-gpr-evidence
collect-location-evidence
collect-reaction-location-evidence
resolve-compartment-evidence
```

must reuse existing outputs when their fingerprints remain valid.

Forcing a downstream modeling stage must not cause external evidence to be fetched again unnecessarily.

Forcing an evidence stage should rerun only that stage and its dependent descendants according to the existing DAG semantics.

Network retrieval should therefore remain entirely inside explicit evidence-collection stages.

---

## 17. Add static BioCyc CCO fixtures

Extend the existing injectable `StaticBioCycClient` or add a dedicated static CCO fixture/client boundary.

Do not make unit tests depend on the live BioCyc service.

Static CCO data should represent enough graph structure to test:

```text
term
name
synonyms
superclasses
component-of
```

without requiring a complete ontology export.

The production BioCyc client may fetch CCO data in live mode, but the resolver should operate on a small normalized internal representation.

For example:

```json
{
  "CCO-MIT-IMEM": {
    "name": "mitochondrial inner membrane",
    "superclasses": [
      "CCO-MIT-MEM"
    ],
    "component_of": [
      "CCO-MIT"
    ]
  },
  "CCO-MIT": {
    "name": "mitochondrion"
  }
}
```

---

## 18. Test the complete workflow

Add unit and integration tests covering the following.

### GPR evidence

* EC evidence fills a missing β1 GPR.
* EC lookup occurs only once per unique EC.
* A valid β1 GPR takes precedence over conflicting external evidence.
* An invalid/missing β1 GPR can be replaced by valid recorded EC evidence.
* GPR conflicts are preserved in evidence.

### GPR location semantics

* OR union behavior.
* AND co-localization/intersection behavior.
* Mixed AND/OR behavior.
* Required subunit missing from a location rejects that location.
* Missing location does not default to cytosol.
* Explicit `fallback_location` still works.

### Configured registry

* Explicit compartment IDs such as `x` and `i` are honored.
* β1 compartment IDs do not become legal targets automatically.
* An evidence location outside the configured registry is rejected.
* Adding a new configured target makes it legal without code changes.

### BioCyc CCO resolution

Static fixtures should cover at least:

```text
mitochondrial inner membrane
→ Mitochondria
```

```text
mitochondrial intermembrane space
→ Mitochondria
```

```text
mitochondrial matrix
→ Mitochondria
```

```text
peroxisomal membrane
→ Peroxisome
```

Also test:

* direct configured-location match without CCO lookup;
* existing alias match without CCO lookup;
* exact CCO-name resolution;
* direct CCO-ID resolution;
* `COMPONENT-OF` traversal;
* superclass traversal where appropriate;
* preference for the nearest target;
* preference for containment over a conflicting generic superclass;
* no downward guessing;
* no use of `SURROUNDED-BY` as containment;
* a term with no configured ancestor produces `location-not-in-registry`;
* two equally valid configured targets produce `ambiguous-compartment-resolution`;
* resolution path is persisted in evidence.

### Evidence integration

* A specific BioCyc child term and a broad UniProt parent term resolve to the same target and are treated as agreement.
* BioCyc reaction evidence and gene evidence agreeing on a target strengthen provenance.
* Conflicting BioCyc reaction and gene evidence are reported.
* Ambiguous BioCyc reaction evidence does not generate an expansion.

### Offline reproducibility

* Snapshot mode performs zero network calls.
* A live-generated snapshot reproduces the same compartment resolutions.
* Snapshot replay produces an identical expansion plan.

### Resumability

* Completed GPR evidence is not fetched again.
* Completed location evidence is not fetched again.
* Completed CCO evidence is not fetched again.
* Forcing downstream stages does not trigger external calls.
* Forcing an evidence stage reruns its dependent descendants correctly.

---

## 19. Preserve architectural boundaries

Keep these concerns separate:

```text
services/
    external HTTP/API access

evidence collection stages
    fetch and normalize source records

CCO compartment resolver
    pure graph resolution

GPR/location resolver
    biological Boolean logic

expansion engine
    model proposals and mutation

validation/export
    model checks and reproducibility artifacts
```

In particular:

* `services/biocyc.py` may retrieve BioCyc/CCO records.
* β2 evidence stages may request and snapshot them.
* the compartment resolver interprets recorded CCO relationships.
* `generate_expansion_plan` receives only normalized configured compartments.
* `apply_expansion_plan` remains unaware of external evidence services.

This prevents network/database semantics from leaking into model mutation.

---

## 20. Scope boundary

This restores the legacy principle:

```text
β1 model
+
external biological evidence
+
explicit compartment registry
→ localized β2 reaction copies
```

without reproducing the legacy script's exact:

* APIs;
* caches;
* identifiers;
* fuzzy mappings;
* Excel/pickle mappings;
* equation parsing;
* post-processing;
* output bytes.

`model_build_batch` and the Human Database workflow remain separate.

They may enrich, reconstruct, or merge model content, but they do not replace the normalized GPR/localization evidence contract required by β2 expansion.

BioCyc CCO likewise remains an evidence-resolution mechanism, not a model-compartment registry.

The final authority for whether a compartment may appear as a new β2 expansion target is always:

```text
beta2.compartments
```
