# β2 Open Evidence Integration Plan

## Goal

Extend the β2 workflow so compartment resolution and localization evidence are based on open, reproducible resources rather than depending on BioCyc as the primary ontology source.

The target architecture is:

```text
β1 model
   │
   ├─ existing model GPRs
   ├─ EC / Rhea reaction evidence
   ├─ UniProt / GOA gene localization
   ├─ Reactome reaction + catalyst evidence
   └─ optional BioCyc evidence
            │
            ▼
     canonical GO representation
            │
            ▼
  GO Cellular Component DAG
       is_a / part_of
            │
            ▼
 beta2 configured targets
            │
            ▼
 GPR location inference
            │
            ▼
 proposal-first expansion
            │
            ▼
      β2 model
```

Core rule:

```text
external databases = evidence

GO Cellular Component = canonical biological location ontology

beta2.compartments = legal model compartments
```

External databases may support or resolve a location, but they must never introduce a β2 compartment that is not explicitly configured.

---

## 1. Scope

This plan extends the existing β2 evidence-driven expansion workflow.

It does not replace:

- β1;
- the Human Database workflow;
- the existing proposal/decision mechanism;
- the existing expansion engine;
- the existing validation/export framework.

The goal is to improve evidence collection and compartment resolution while keeping model mutation deterministic, offline-capable, and auditable.

### 1.1 Current repository boundary

The current β2 implementation provides the evidence boundary, the
`provided`/`snapshot`/`live` modes, proposal-first expansion, replay artifacts,
and a pure GO Cellular Component resolver. It supports configured GO targets,
GOA GAF snapshots/live bulk retrieval, structured UniProt snapshots/live
lookup, Rhea candidate reaction/protein evidence, Reactome location/catalyst
snapshots, and optional BioCyc CCO corroboration. It still intentionally keeps
complex-catalyst interpretation and weak cross-database conflicts as
candidate/unresolved evidence. The stages named below are the target
decomposition; where a current stage already covers the boundary, it should be
extended or split rather than duplicated.

### 1.2 Implementation checkpoint

The first open-evidence slice is implemented in the current β2 workflow:

- GO Cellular Component parsing and nearest-target resolution use only `is_a`
  and `part_of` edges.
- GOA, UniProt, Rhea, Reactome, and BioCyc evidence enter through injectable
  snapshot/live boundaries.
- Explicit configuration remains authoritative; ambiguous or conflicting
  evidence remains candidate/unresolved.
- Live runs export replayable evidence, GO metadata, source checksums, and
  resolution/reconciliation artifacts.

The remaining operational gate is recorded-service/online verification for
external providers. It is intentionally not conflated with the offline
workflow tests.

Open reaction sources also expose canonical stoichiometric-GPR evidence through
the shared sGPR AST. Structural evidence is merged separately from ordinary
GPR compatibility strings; unknown coefficients are not asserted as observed
`*1` values. See [Stoichiometric GPR evidence](sgpr_evidence.md).

This document describes both the current stage layout and the remaining
acceptance work. A checked item in the final section means that the behavior
is implemented and covered by the stated evidence; provider plumbing that
still lacks the policies below remains unchecked.

---

## 2. Architectural principles

### 2.1 Keep network access outside model mutation

External APIs and downloads belong only in evidence-collection stages.

The model mutation code must consume normalized evidence and must not call:

- GO;
- UniProt;
- Rhea;
- Reactome;
- BioCyc;
- KEGG;
- Ensembl.

### 2.2 Use GO Cellular Component as the canonical compartment ontology

All supported external location evidence should ultimately be normalized to a GO Cellular Component term where possible.

Examples:

```text
UniProt subcellular location
→ GO term

GOA annotation
→ GO term

Reactome compartment
→ GO term

BioCyc CCO
→ GO term where possible
```

### 2.3 Keep `beta2.compartments` authoritative

The configured β2 registry defines the only legal expansion targets.

For example:

```json
{
  "compartments": {
    "c": "cytosol",
    "m": "mitochondria"
  }
}
```

No external database may implicitly add:

```text
nucleus
lysosome
peroxisome
plasma membrane
```

unless those targets are explicitly configured.

### 2.4 Do not infer model compartment IDs from biological names

Compartment IDs are user-configured.

For example:

```json
{
  "compartments": {
    "x": "mitochondria",
    "i": "cytosol"
  }
}
```

must work exactly as well as:

```json
{
  "compartments": {
    "m": "mitochondria",
    "c": "cytosol"
  }
}
```

---

## 3. Add explicit GO terms to the configured compartment registry

Extend β2 configuration with canonical GO targets.

Example:

```json
{
  "compartments": {
    "c": "cytosol",
    "m": "mitochondria"
  },
  "compartment_go_terms": {
    "c": "GO:0005829",
    "m": "GO:0005739"
  }
}
```

Interpretation:

```text
c
├─ display name: Cytosol
└─ GO target: GO:0005829

m
├─ display name: Mitochondria
└─ GO target: GO:0005739
```

The GO term is the semantic target.

The compartment key is the model identifier.

The display name is presentation/configuration metadata.

Require every configured automatic target to have a canonical GO term unless an explicit non-GO target mode is introduced later.

Validate this at configuration load time:

- every `compartment_go_terms` key must exist in `compartments`;
- every value must be a valid GO ID;
- two model compartments may not share one GO target;
- automatic open-evidence mode must reject a registry without complete GO
  mappings until an explicit non-GO mode exists.

---

## 4. Extend the β2 evidence configuration

Recommended configuration:

```json
{
  "evidence_mode": "snapshot",
  "evidence_file": "../inputs/evidence/beta2.jsonl",

  "gpr_policy": "model-then-ec",
  "location_policy": "provided-then-evidence",

  "compartments": {
    "c": "cytosol",
    "m": "mitochondria"
  },

  "compartment_go_terms": {
    "c": "GO:0005829",
    "m": "GO:0005739"
  },

  "location_sources": [
    "goa",
    "uniprot",
    "reactome",
    "biocyc"
  ],

  "reaction_sources": [
    "rhea",
    "reactome",
    "biocyc"
  ],

  "fallback_location": null
}
```

Add the relevant keys to the strict β2 configuration schema.

Recommended keys:

```text
evidence_mode
evidence_file
gpr_policy
location_policy
compartment_go_terms
location_sources
reaction_sources
go_ontology_file
go_annotation_file
```

Optional later:

```text
rhea_snapshot
reactome_snapshot
uniprot_snapshot
source_confidence_policy
```

---

## 5. Preserve the offline-first evidence modes

Support three evidence modes.

### `provided`

Use only:

- configured gene locations;
- configured reaction evidence;
- supplied ontology/evidence files;
- deterministic aliases.

No network calls.

### `snapshot`

Read previously captured evidence.

No network calls.

The snapshot must contain everything needed to reproduce:

- GPR decisions;
- gene locations;
- reaction locations;
- GO mappings;
- GO resolution paths;
- reaction identity decisions.

### `live`

Allow external retrieval.

Live mode must persist sufficient evidence so the run can later be replayed in `snapshot` mode.

A live run should never be the only reproducible representation of the evidence.

---

## 6. Load the GO ontology

The ontology-loading boundary loads a pinned `go-basic` release.

Live mode must receive an explicit immutable release URL and release/version.
The moving `current.geneontology.org` URL is not sufficient. Persist the URL,
release, retrieval time, raw-response checksum, and parser version in the
snapshot metadata. A supplied local ontology file is acceptable when its
checksum and release metadata are recorded.

Current DAG location:

```text
normalize-compartments (loads ontology when needed)
→ collect-location-evidence
```

The current implementation performs ontology loading inside
`normalize-compartments`; keep that boundary unless independent caching and
resume behavior justify a separate stage.

The loader should parse only what β2 needs.

Internal representation:

```json
{
  "GO:0005743": {
    "name": "mitochondrial inner membrane",
    "synonyms": [
      "inner mitochondrial membrane"
    ],
    "parents": [
      {
        "relation": "part_of",
        "id": "GO:0005739"
      },
      {
        "relation": "is_a",
        "id": "GO:0031966"
      }
    ]
  }
}
```

Supported upward relationships:

```text
is_a
part_of
```

Do not use:

```text
has_part
surrounded_by
regulates
occurs_in
```

for compartment collapse.

---

## 7. Keep the GO resolver pure and network-free

Implement a pure compartment resolver separate from all HTTP/API clients.

Conceptually:

```python
resolve_compartment(
    evidence_term,
    configured_registry,
    go_graph,
)
```

Input may include:

```text
raw name
GO ID
UniProt location ID
Reactome compartment
BioCyc CCO ID
```

but it must be normalized to a GO term before graph resolution.

The resolver returns:

```json
{
  "raw_location": "mitochondrial inner membrane",
  "canonical_go_id": "GO:0005743",
  "status": "resolved",
  "target_compartment_id": "m",
  "target_compartment_name": "Mitochondria",
  "target_go_id": "GO:0005739",
  "resolution_path": [
    {
      "id": "GO:0005743",
      "name": "mitochondrial inner membrane"
    },
    {
      "relation": "part_of",
      "id": "GO:0005739",
      "name": "mitochondrion"
    }
  ]
}
```

---

## 8. Resolve to the nearest configured GO target

For each evidence GO term:

1. Check exact configured GO target.
2. Traverse upward through `is_a` and `part_of`.
3. Find all configured target GO terms reachable from the evidence term.
4. Choose the nearest valid target.
5. If no target is reachable, reject as `location-not-in-registry`.
6. If multiple equally valid nearest targets exist, reject as `ambiguous-compartment-resolution`.

Example:

```text
GO:0005743
mitochondrial inner membrane
       │
       │ part_of
       ▼
GO:0005739
mitochondrion
       │
       ▼
configured target m
```

Result:

```text
m
```

---

## 9. Support overlapping configured targets

The resolver must work if the user configures both broad and specific compartments.

Example:

```json
{
  "compartments": {
    "m": "mitochondria",
    "im": "mitochondrial inner membrane"
  },
  "compartment_go_terms": {
    "m": "GO:0005739",
    "im": "GO:0005743"
  }
}
```

Evidence:

```text
GO:0005743
```

must resolve to:

```text
im
```

because it is the nearest configured target.

Do not automatically collapse to the broader mitochondrion if a more specific legal model target exists.

---

## 10. Make GOA the primary automatic gene-location source

Add a human GOA evidence loader.

Prefer bulk annotation snapshots rather than one API request per gene.

The loader should preserve:

```text
gene/product identifier
GO ID
aspect
qualifier
evidence code
reference
assigned_by
source release
```

Filter to Cellular Component annotations.

Exclude negated annotations.

Example normalized evidence:

```json
{
  "gene_id": "GENE1",
  "source": "goa-uniprot",
  "go_id": "GO:0005743",
  "qualifier": "located_in",
  "evidence_code": "IDA",
  "reference": "PMID:...",
  "status": "candidate"
}
```

Keep multiple annotations when biologically supported.

Do not collapse them prematurely.

---

## 11. Use UniProt as complementary localization evidence

Use UniProt for:

- gene/protein identifier mapping;
- protein localization;
- subcellular-location vocabulary;
- additional GO annotations.

Prefer controlled identifiers and official mappings over free-text scraping.

Recommended path:

```text
UniProt subcellular-location term
→ official SL-to-GO mapping
→ GO term
→ GO resolver
```

The SL-to-GO mapping must be location-specific. Do not attach every GO
cross-reference on a UniProt protein to every subcellular-location comment.
Only mapped Cellular Component terms may become automatic location evidence;
an unmapped SL term remains preserved raw evidence and unresolved.

Free-text aliases should only be a fallback for:

- user-provided configuration;
- legacy records;
- sources that lack structured identifiers.

---

## 12. Define location evidence precedence

Recommended precedence:

```text
1. explicit beta2.gene_locations
2. supplied snapshot evidence
3. GOA annotations
4. UniProt localization
5. Reactome supporting evidence
6. optional BioCyc supporting evidence
```

Higher-precedence evidence controls the automatic decision.

Lower-precedence evidence is still preserved for provenance and conflict detection.

Agreement should be evaluated after GO normalization.

If multiple same-precedence records resolve to different legal targets, retain
all records and emit a deterministic location conflict. Precedence may select
the primary automatic decision, but it must not erase the conflict.

Example:

```text
BioCyc:
    mitochondrial inner membrane

GOA:
    GO:0005743

UniProt:
    mitochondrial inner membrane
```

all become:

```text
GO:0005743
→ GO:0005739
→ m
```

and therefore count as agreement.

---

## 13. Resolve gene locations before Boolean GPR logic

Current GPR location logic should receive configured β2 targets, not raw biological location strings.

New flow:

```text
raw gene localization
→ canonical GO term
→ configured GO target
→ model compartment ID/name
→ GPR location inference
```

Example:

```text
Gene A:
    mitochondrial inner membrane

Gene B:
    mitochondrial matrix
```

may resolve to:

```text
Gene A → m
Gene B → m
```

before evaluating:

```text
A and B
```

This prevents false rejection caused by biologically compatible subcompartment labels.

---

## 14. Preserve current OR/AND semantics

After compartment normalization, reuse the existing β2 GPR location logic.

### OR

Use union semantics.

```text
A or B
```

with:

```text
A → m
B → c
```

gives:

```text
m: A
c: B
```

### AND

Use intersection/co-localization semantics.

```text
A and B
```

requires both genes to support the same configured target.

### Missing location

Do not silently assign cytosol.

Only use `fallback_location` when explicitly configured.

---

## 15. Add Rhea as the primary reaction identity source

Add:

```text
src/thg_protocol/services/rhea.py
```

Recommended protocol:

```python
class RheaClientProtocol:
    def reactions_for_ec(self, ec_number): ...
    def reaction(self, rhea_id): ...
    def proteins_for_reaction(self, rhea_id): ...
```

Provide:

```text
RheaClient
StaticRheaClient
```

Rhea should primarily answer:

```text
what biochemical reaction is this?
which curated proteins are linked to it?
```

It should not directly mutate model GPRs.

---

## 16. Use a reaction identity confidence hierarchy

Do not treat EC alone as exact reaction identity.

Use a deterministic hierarchy.

### Strongest

```text
existing Rhea annotation on the model reaction
```

### Strong

```text
model reaction chemistry matches one Rhea reaction
```

Prefer ChEBI-supported matching where available.

### Moderate

```text
EC maps to one plausible Rhea reaction
```

### Candidate only

```text
EC maps to multiple plausible Rhea reactions
```

Ambiguous reaction identity must remain unresolved/proposed.

Do not guess.

---

## 17. Use Rhea to obtain candidate human enzymes

Once a Rhea reaction is sufficiently identified:

```text
Rhea reaction
→ linked UniProt proteins
→ Homo sapiens proteins
→ gene identifiers
```

Example evidence:

```json
{
  "reaction_id": "R1",
  "rhea_id": "RHEA:12345",
  "human_proteins": [
    {
      "uniprot": "P12345",
      "gene": "GENE1"
    }
  ],
  "status": "candidate",
  "confidence": "reaction-matched"
}
```

Multiple proteins linked to the same reaction may support an OR candidate.

Do not interpret multiple proteins as an AND complex without additional evidence.

---

## 18. Do not reconstruct complex GPRs from Rhea alone

This is a hard safety rule for biological inference.

Given:

```text
Rhea reaction
→ Protein A
→ Protein B
```

do not infer:

```text
A and B
```

The proteins may be:

- isoenzymes;
- different subunits;
- species-specific alternatives;
- separately curated catalysts.

AND logic requires explicit complex evidence.

---

## 19. Use Reactome for catalyst complexes

Add Reactome as a higher-level source for:

```text
reaction
→ catalyst activity
→ protein / complex / entity set
```

Potential mapping:

```text
model reaction
→ Rhea
→ Reactome
→ catalyst complex
→ UniProt proteins
→ genes
```

Use this only when the reaction mapping is sufficiently strong.

Reactome evidence may support:

```text
A and B
```

when the catalyst is explicitly represented as a complex.

It may support:

```text
A or B
```

when the catalyst is represented as an entity set or alternative catalysts.

Do not flatten Reactome structures without preserving the semantic distinction.
Unknown catalyst types, incomplete nested complexes, and mixed structures must
remain unresolved rather than defaulting to OR.

---

## 20. Use Reactome for reaction compartment evidence

Reactome reaction compartments can feed directly into the GO resolver.

Flow:

```text
Reactome reaction
→ GO compartment
→ configured GO target
→ β2 compartment
```

Example:

```json
{
  "reaction_id": "R1",
  "source": "reactome",
  "reactome_id": "R-HSA-...",
  "go_id": "GO:0005829",
  "target_compartment_id": "c"
}
```

Reaction-level evidence must remain separate from gene-level localization.

---

## 21. Keep BioCyc optional

Do not remove the existing BioCyc client.

Change its architectural role.

Recommended source hierarchy:

```text
Canonical ontology:
    GO Cellular Component

Primary gene localization:
    GOA
    UniProt

Primary reaction identity:
    Rhea

Primary reaction/complex support:
    Reactome

Optional corroboration:
    BioCyc
    KEGG
```

BioCyc CCO evidence should be translated to GO where possible before entering the compartment resolver.

The resolver itself should never depend on BioCyc-specific ontology semantics.

---

## 22. Add a GPR evidence stage

Add:

```text
collect-gpr-evidence
```

between:

```text
collect-catalysis-evidence
```

and:

```text
resolve-gprs
```

For reactions with missing or unusable model GPRs:

1. collect EC annotations;
2. identify Rhea candidates;
3. resolve exact reaction identity where possible;
4. collect human UniProt enzyme candidates;
5. optionally collect Reactome catalyst evidence;
6. optionally collect BioCyc evidence;
7. produce normalized GPR candidates.

Do not mutate the model in this stage.

---

## 23. Define GPR precedence

Recommended:

```text
gpr_policy = model-then-ec
```

Rules:

### Valid model GPR

Keep it.

External disagreement becomes conflict evidence only.

### Missing model GPR

Use a strong external candidate when available.

### Invalid model GPR

Allow strong external evidence to produce a replacement proposal.

### Ambiguous external evidence

Leave unresolved/proposed.

An external GPR may be selected only when its normalized record has an
accepted confidence (`authoritative`, `strong`, or an explicitly defined
reaction-matched equivalent) and a non-ambiguous status. `supporting`,
`candidate`, `unresolved`, and ambiguous records remain evidence/proposals and
must not mutate the resolved-GPR model.

### Complex structure unavailable

Do not invent AND rules.

---

## 24. Add reaction-location collection

Add:

```text
collect-reaction-location-evidence
```

Sources:

```text
Reactome
optional BioCyc
```

Keep records separate from gene localization.

Example:

```json
{
  "reaction_id": "R1",
  "source": "reactome",
  "raw_location": "mitochondrial matrix",
  "go_id": "GO:0005759",
  "status": "candidate"
}
```

---

## 25. Add a compartment resolution stage

Add:

```text
resolve-compartment-evidence
```

This stage resolves:

```text
gene localization
reaction localization
user-provided free text
UniProt SL terms
Reactome GO compartments
optional BioCyc locations
```

to:

```text
configured β2 targets
```

Output must retain all resolution paths.

---

## 26. Reconcile gene and reaction evidence

Keep this responsibility inside:

```text
resolve-compartment-evidence
```

Possible outcomes:

### Agreement

Gene and reaction evidence resolve to the same configured target.

```text
status = supported
```

### Specific/broad agreement

Example:

```text
gene:
    mitochondrial inner membrane

reaction:
    mitochondrion
```

Both resolve to:

```text
m
```

Therefore this is agreement.

### Conflict

Example:

```text
gene:
    mitochondrion

reaction:
    cytosol
```

Result:

```text
location-conflict
```

Do not silently choose one unless an explicit policy says to.

### Gene evidence absent

Strong reaction evidence may provide a candidate target.

### Reaction evidence absent

Gene/GPR localization continues normally.

---

## 27. Add deterministic evidence confidence tiers

Use categorical confidence instead of arbitrary probabilities.

Recommended levels:

```text
authoritative
strong
supporting
candidate
```

### Authoritative

```text
explicit configuration
valid existing model GPR
```

### Strong

```text
curated GO localization
exact Rhea reaction mapping
explicit Reactome reaction compartment
explicit Reactome catalyst complex
```

### Supporting

```text
other curated UniProt evidence
unique EC-derived reaction candidate
optional BioCyc agreement
```

### Candidate

```text
ambiguous EC mapping
indirect reaction mapping
unresolved source disagreement
```

Decision rule:

```text
strong + strong agreement
→ accept

strong + strong conflict
→ conflict

candidate only
→ proposal / unresolved
```

---

## 28. Revised β2 DAG

Current implementation DAG:

```text
load-beta1
│
├─ collect-catalysis-evidence
│
├─ collect-gpr-evidence
│    ├─ model
│    ├─ Rhea
│    ├─ Reactome
│    └─ optional BioCyc
│
├─ resolve-gprs
│
├─ normalize-compartments
│
├─ collect-location-evidence
│    ├─ explicit
│    ├─ GOA
│    ├─ UniProt
│    └─ optional BioCyc
│
├─ collect-reaction-location-evidence
│    ├─ Reactome
│    └─ optional BioCyc
│
├─ resolve-compartment-evidence
│
├─ infer-complex-and-isoenzyme-locations
│
├─ generate-expansion-plan
│
├─ apply-expansion-decisions
│
├─ apply-expansion
│
├─ consolidate-expanded-model
│
├─ validate-beta2
│
└─ export-beta2
```

`normalize-compartments` currently loads the configured ontology when needed;
`collect-location-evidence` is the gene-location stage; and
`resolve-compartment-evidence` emits reconciliation/conflict records. Split
these into separate stages only if independent resume and provenance behavior
becomes necessary.

---

## 29. Reuse the existing expansion engine

Do not modify the expansion engine to understand:

```text
GO
Rhea
Reactome
UniProt
BioCyc
```

It should continue receiving:

```text
reaction
configured target compartment
resolved GPR
evidence/provenance ID
```

Example:

```json
{
  "reaction_id": "R1",
  "target_compartment": "m",
  "gpr": "(GENE1 and GENE2)",
  "evidence_id": "beta2-location:R1:m"
}
```

This preserves the existing proposal-first model mutation architecture.

---

## 30. Export reproducible evidence artifacts

Export at minimum:

```text
go-release.json
go-compartment-subgraph.json
gene-location-evidence.jsonl
reaction-location-evidence.jsonl
reaction-identity-evidence.jsonl
gpr-evidence.jsonl
compartment-resolution-evidence.json
location-reconciliation.jsonl
beta2-evidence-snapshot.jsonl
beta2-unresolved.tsv
```

Continue exporting existing:

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

## 31. Record source versions

Each external snapshot should record:

```text
source
release/version
retrieval date
source URL or identifier
checksum
parser version
```

Example:

```json
{
  "source": "Gene Ontology",
  "release": "YYYY-MM-DD",
  "file": "go-basic.obo",
  "sha256": "...",
  "parser_version": "1"
}
```

Do the same for:

```text
GOA
Rhea
Reactome
UniProt
BioCyc
```

when those sources participate in the run.

The metadata must be present for live GOA, UniProt, Rhea, Reactome, and
BioCyc retrievals; `live` or `unknown` is not a release identifier. A
normalized-result checksum is not a substitute for the raw-response checksum
when the raw response was retrieved.

---

## 32. Make snapshot replay a hard reproducibility guarantee

A completed live run must be replayable with:

```text
evidence_mode = snapshot
```

without external requests.

Given:

```text
same β1 model
same β2 config
same evidence snapshot
same software version
```

the workflow should reproduce:

```text
same resolved GPRs
same resolved compartments
same rejected/ambiguous evidence
same expansion proposals
same deterministic IDs
```

Prefer byte-identical artifacts where practical.

---

## 33. Make resume evidence-aware

Completed evidence stages must not refetch data during a normal resume.

Examples:

```text
collect-gpr-evidence
collect-location-evidence
collect-reaction-location-evidence
normalize-compartments
```

must reuse their outputs if fingerprints remain valid.

Forcing:

```text
generate-expansion-plan
```

must not trigger external API calls.

Forcing:

```text
collect-location-evidence
```

should rerun that stage and its dependent descendants only.

---

## 34. Add static clients and fixtures

Unit and integration tests must not depend on live services.

Add or extend:

```text
StaticRheaClient
StaticReactomeClient
StaticUniProtClient
StaticGOALoader
StaticBioCycClient
```

Fixtures should contain minimal realistic records.

Example GO fixture:

```json
{
  "GO:0005743": {
    "name": "mitochondrial inner membrane",
    "parents": [
      ["part_of", "GO:0005739"]
    ]
  },
  "GO:0005739": {
    "name": "mitochondrion",
    "parents": []
  }
}
```

---

## 35. Test GO compartment resolution

Cover at least:

```text
mitochondrial inner membrane
→ mitochondrion
→ m
```

```text
mitochondrial matrix
→ mitochondrion
→ m
```

```text
peroxisomal membrane
→ peroxisome
→ configured target
```

Also test:

- direct GO target match;
- GO synonym match;
- `is_a` traversal;
- `part_of` traversal;
- nearest configured target;
- overlapping configured targets;
- arbitrary model compartment IDs;
- no reachable target;
- equal-distance ambiguity;
- obsolete GO term handling;
- no `has_part` traversal;
- no downward guessing.

---

## 36. Test gene-location evidence

Cover:

- explicit configured location wins;
- GOA Cellular Component annotations;
- non-CC GO annotations ignored;
- negated annotations ignored;
- evidence code preserved;
- reference preserved;
- multiple locations preserved;
- UniProt SL-to-GO mapping;
- duplicate evidence deduplicated without losing provenance;
- snapshot mode performs zero network calls.

---

## 37. Test Rhea reaction evidence

Cover:

- existing Rhea annotation;
- EC → one Rhea candidate;
- EC → multiple candidates;
- ChEBI-supported disambiguation;
- no chemical match;
- human protein filtering;
- multiple human enzymes;
- ambiguous reaction remains unresolved;
- no AND inference from multiple proteins.

---

## 38. Test Reactome evidence

Cover:

- Rhea → Reactome reaction;
- reaction → GO compartment;
- single protein catalyst;
- catalyst complex;
- entity set / isoenzyme alternatives;
- unmapped reaction;
- conflicting Reactome and gene localization.

---

## 39. Test combined location reconciliation

### Same final target

```text
GOA:
    mitochondrial inner membrane

Reactome:
    mitochondrion
```

must be agreement after resolution.

### Conflict

```text
GOA:
    mitochondrion

Reactome:
    cytosol
```

must produce:

```text
location-conflict
```

### No configured target

Evidence for an unconfigured compartment must produce:

```text
location-not-in-registry
```

### Ambiguous target

Multiple equally valid configured targets must produce:

```text
ambiguous-compartment-resolution
```

---

## 40. Recommended implementation sequence

Do not implement every provider at once.

### Phase 1 — GO compartment resolver

Implement:

```text
compartment_go_terms
go-basic loader
GO DAG
is_a / part_of traversal
nearest configured target
resolution artifacts
```

Continue using configured `gene_locations`.

This is the lowest-risk and highest-value first step.

### Phase 2 — GOA gene localization

Add:

```text
human GOA snapshot
gene/product mapping
evidence codes
automatic gene localization
```

At this point the majority of automatic compartment inference is already functional.

### Phase 3 — UniProt

Add:

```text
identifier mapping
subcellular location vocabulary
SL-to-GO mapping
additional localization evidence
```

### Phase 4 — Rhea

Add:

```text
EC → Rhea
Rhea reaction evidence
ChEBI matching
Rhea → human UniProt proteins
candidate GPR evidence
```

### Phase 5 — Reactome reaction compartments

Add:

```text
reaction mapping
reaction GO compartments
location reconciliation
```

### Phase 6 — Reactome catalyst complexes

Add:

```text
catalyst activity
complex membership
entity sets
AND/OR GPR evidence
```

This is the most biologically complex part and should come after the simpler evidence pipeline is stable.

### Phase 7 — BioCyc compatibility

Route existing BioCyc evidence through the same canonical evidence model.

BioCyc becomes optional corroboration rather than a foundational dependency.

---

## 41. Realism and risk assessment

### Very realistic

```text
GO ontology loading
specific → broad compartment resolution
configured GO target mapping
GOA gene localization
offline snapshots
deterministic replay
Reactome GO compartment normalization
```

### Realistic with careful implementation

```text
UniProt identifier mapping
Rhea reaction identity
Rhea → human enzyme candidates
reaction chemistry disambiguation
Reactome reaction mapping
```

### Requires conservative policies

```text
automatic GPR creation from EC numbers
complex AND GPR reconstruction
conflicting database evidence
reaction identity from weak annotations
```

### Do not automate aggressively

Never assume:

```text
multiple proteins returned by Rhea
= protein complex
```

Never assume:

```text
EC number
= unique reaction
```

Never assume:

```text
database location
= legal β2 model compartment
```

Never assume:

```text
missing localization
= cytosol
```

---

## 42. Final target architecture

The final evidence architecture should look like:

```text
                       GOA ──────────────┐
                                        │
UniProt SL ── SL-to-GO ─────────────────┤
                                        │
Reactome compartment ───────────────────┤
                                        │
BioCyc CCO ── optional mapping ─────────┤
                                        ▼
                              GO Cellular Component
                                        │
                                is_a / part_of
                                        │
                                        ▼
                             configured GO targets
                                        │
                                        ▼
                              beta2.compartments
                                        │
                                        ▼
                              GPR location logic
                                        │
                                        ▼
                             expansion proposals
```

Reaction/GPR evidence:

```text
β1 GPR
   │
   ├─ valid
   │    └─ keep
   │
   └─ missing / unusable
          │
          ▼
      Rhea identity
          │
     ┌────┴────┐
     │         │
   exact    ambiguous
     │         │
     ▼         ▼
 human       unresolved
 proteins
     │
     ▼
 candidate OR evidence
     │
     ▼
 optional Reactome catalyst structure
     │
     ├─ complex
     │    └─ AND support
     │
     └─ entity set / alternatives
          └─ OR support
```

---

## 43. Definition of done

The integration is complete when:

1. [x] β2 resolves specific GO locations to configured broader compartments.
2. [x] Configured model compartment IDs remain arbitrary.
3. [x] GOA provides automatic human gene localization from bulk evidence with release metadata.
4. [x] Structured UniProt localization records use a location-specific SL-to-GO mapping.
5. [x] Rhea provides reaction identity and human enzyme candidates under the confidence hierarchy.
6. [x] Reactome contributes reaction compartments and preserves explicit catalyst structure.
7. [x] BioCyc is optional corroboration rather than a fallback canonical resolver.
8. [x] Missing, ambiguous, or low-confidence evidence does not silently create model content.
9. [x] Live evidence runs produce replayable snapshots with complete source provenance.
10. [x] Snapshot mode performs zero external requests.
11. [x] Existing expansion and validation logic remains source-agnostic.
12. [x] Accepted/rejected expansion evidence and policy decisions are exported with the documented artifact names.

Credentialed provider availability and release-specific biological coverage
remain operational verification work, but the live-to-snapshot provenance and
zero-network replay behavior are implemented and covered by the test suite.
