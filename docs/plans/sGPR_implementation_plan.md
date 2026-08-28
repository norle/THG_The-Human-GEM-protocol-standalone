# sGPR Implementation Plan

## Goal

Implement a source-independent stoichiometric GPR (sGPR) system that works consistently across BioCyc, Reactome, Rhea, KEGG, UniProt-supported evidence, and existing model GPRs while preserving the existing legacy `get_gpr()` compatibility API.

The implementation should:

- preserve correct `AND` / `OR` enzyme logic;
- preserve subunit multiplicity when a source actually provides it;
- distinguish observed stoichiometry from inferred/defaulted values;
- avoid inventing `*1` coefficients when stoichiometry is unknown;
- allow normal GPR and legacy textual sGPR to be generated from the same canonical representation;
- retain provenance for every structural and stoichiometric claim;
- keep current beta2 evidence resolution auditable and deterministic.

---

## Current Problems

### 1. BioCyc compatibility sGPR is not biologically faithful

The current compatibility path effectively generates:

```text
(GENE_A*1) or (GENE_B*1)
```

for all returned BioCyc genes.

This has two problems:

1. every gene is assigned coefficient `1`, whether or not BioCyc actually supports that stoichiometry;
2. all genes are joined with `OR`, which can destroy real enzyme-complex `AND` relationships.

### 2. Open-database GPR evidence is inconsistent

Current beta2 behavior already collects candidate GPR evidence from multiple sources, but each source exposes a different amount of structure:

- Reactome can distinguish complexes and alternatives;
- Rhea associates EC/reaction evidence with proteins;
- KEGG provides EC-to-gene associations but usually not detailed complex stoichiometry;
- UniProt can provide supporting protein/subunit evidence;
- GOA is primarily localization evidence and should not itself generate sGPRs.

### 3. Stoichiometry is stored separately from GPR structure

The beta2 pipeline already has a `subunit_stoichiometry` concept, but a flat mapping is insufficient for alternative enzyme complexes.

For example:

```text
(A*2 and B*1) or (A*1 and C*3)
```

cannot be represented correctly by:

```python
{
    "A": 2,
    "B": 1,
    "C": 3,
}
```

because `A` has different stoichiometry in different branches.

---

# Proposed Architecture

## 1. Introduce a canonical stoichiometric-GPR AST

Add a module such as:

```text
src/thg_protocol/gpr/stoichiometry.py
```

The canonical representation should be tree-based.

Example:

```python
Or(
    And(
        Gene("A", coefficient=2),
        Gene("B", coefficient=1),
    ),
    And(
        Gene("A", coefficient=1),
        Gene("C", coefficient=3),
    ),
)
```

Equivalent biological expression:

```text
(A*2 and B*1) or (A*1 and C*3)
```

### Suggested node types

```python
@dataclass(frozen=True)
class GeneNode:
    gene: str
    coefficient: int | None = None
    coefficient_status: str = "unknown"
    source: str | None = None
    evidence: tuple[str, ...] = ()

@dataclass(frozen=True)
class AndNode:
    children: tuple["SgprNode", ...]

@dataclass(frozen=True)
class OrNode:
    children: tuple["SgprNode", ...]
```

Possible coefficient statuses:

```text
observed
inferred
defaulted
unknown
```

### Rules

- `observed`: the source explicitly states the multiplicity.
- `inferred`: multiplicity can be derived unambiguously from source structure.
- `defaulted`: coefficient `1` is emitted only for backwards compatibility.
- `unknown`: no coefficient should be biologically asserted.

---

# 2. Add canonical serializers

Create deterministic functions for converting the AST to the formats already used by THG.

## Standard GPR

Input:

```text
(A*2 and B*1) or (A*1 and C*3)
```

Output:

```text
(A and B) or (A and C)
```

Suggested API:

```python
to_gpr(node) -> str
```

## Stoichiometric GPR

Suggested API:

```python
to_sgpr(
    node,
    *,
    include_defaulted: bool = True,
    unknown_policy: str = "omit",
) -> str
```

Example:

```text
(A*2 and B*1) or (A*1 and C*3)
```

## Legacy compatibility serialization

Provide an explicit compatibility serializer rather than constructing the legacy string directly in `get_gpr()`:

```python
to_legacy_sgpr(node) -> str
```

This allows the old API to continue returning the same tuple shape while using the new canonical representation internally.

---

# 3. Add parsing and normalization utilities

Implement:

```python
normalize_sgpr(node) -> SgprNode
validate_sgpr(node) -> None
genes_in_sgpr(node) -> tuple[str, ...]
strip_stoichiometry(node) -> SgprNode
```

Normalization should:

- sort deterministic alternatives where biologically equivalent;
- flatten nested `AND` and nested `OR`;
- remove duplicate identical branches;
- avoid collapsing branches with different coefficients;
- reject coefficients less than `1`;
- preserve provenance metadata.

---

# 4. Refactor BioCyc GPR extraction

## Current behavior to remove

Do not construct sGPR by doing the equivalent of:

```python
" or ".join(f"({gene}*1)" for gene in genes)
```

## New behavior

Introduce a BioCyc-specific evidence parser:

```text
src/thg_protocol/gpr/sources/biocyc.py
```

or extend the existing BioCyc service/parser boundaries.

Suggested API:

```python
biocyc_sgpr_evidence(
    ec: str,
    *,
    biocyc_client,
) -> SgprEvidence
```

The parser should attempt to recover:

1. EC → enzyme/protein records;
2. enzyme → protein complex / monomer relationships;
3. complex → component proteins;
4. component multiplicity where explicitly encoded;
5. protein → human gene mapping;
6. alternative enzymes as `OR`;
7. components of the same complex as `AND`.

### Example

BioCyc evidence:

```text
enzyme 1:
    A x2
    B x1

enzyme 2:
    C x1
```

Canonical result:

```text
(A*2 and B*1) or C
```

### BioCyc fallback policy

If only a gene list is available:

```text
A, B, C
```

do not claim that they form a complex.

Return:

```text
(A) or (B) or (C)
```

with coefficient status `unknown` or `defaulted`, depending on the requested serialization mode.

---

# 5. Refactor Reactome catalyst parsing

Reactome should become one of the main open sources for complex structure.

Current Reactome logic already distinguishes:

- complex → `AND`;
- entity set / isoenzyme / alternatives → `OR`.

The implementation should preserve this but stop flattening components to a unique gene set too early.

## Required changes

### Preserve membership structure

Avoid:

```python
sorted(set(genes))
```

before the catalyst structure has been fully interpreted.

### Preserve multiplicity

If the Reactome record explicitly represents repeated members or stoichiometric coefficients, convert them to:

```python
GeneNode(
    gene="A",
    coefficient=2,
    coefficient_status="observed",
    source="reactome",
)
```

### Recursive complexes

Support nested entities such as:

```text
complex
  ├── protein A
  └── complex
       ├── protein B
       └── protein C
```

Result:

```text
A and B and C
```

while retaining branch-local coefficients.

### Unknown catalyst semantics

Do not invent `AND` or `OR`.

Return unresolved structural evidence with warnings.

---

# 6. Integrate Rhea through reaction-level enrichment

Rhea should primarily establish biochemical reaction identity and relevant protein associations.

Suggested flow:

```text
EC
 ↓
Rhea reaction
 ↓
associated proteins
 ↓
map proteins to genes
 ↓
enrich structure from Reactome / UniProt / BioCyc
```

## Rhea-only evidence

If Rhea supports multiple possible proteins but not complex relationships, produce:

```text
(A) or (B) or (C)
```

with unknown stoichiometry.

Do not generate an asserted:

```text
(A*1) or (B*1) or (C*1)
```

unless running the legacy serializer.

---

# 7. Keep KEGG as a low-structure fallback

KEGG EC-to-gene evidence should remain useful when stronger structural sources are unavailable.

## KEGG result

For:

```text
A
B
C
```

produce canonical:

```text
A or B or C
```

with:

```text
coefficient = None
coefficient_status = "unknown"
source = "kegg"
```

The compatibility serializer may emit:

```text
(A*1) or (B*1) or (C*1)
```

but those coefficients must be marked internally as `defaulted`, not observed.

---

# 8. Use UniProt as supporting/enrichment evidence

UniProt should be used to:

- map protein identifiers to genes;
- corroborate protein complexes/subunits;
- identify isoforms where appropriate;
- recover useful subunit descriptions;
- support provenance/confidence.

Do not automatically convert free-text subunit descriptions into exact numerical coefficients unless the parsing rule is explicit and well-tested.

Suggested evidence status:

```text
source = "uniprot"
confidence = "supporting"
```

unless the record gives sufficiently structured evidence.

---

# 9. Keep GOA outside sGPR generation

GOA should remain localization evidence.

It should not produce gene-complex or stoichiometric structure.

This keeps responsibilities clean:

```text
reaction evidence:
    Rhea
    Reactome
    BioCyc
    KEGG

protein / structure support:
    Reactome
    UniProt
    BioCyc

localization:
    GOA
    UniProt
    Reactome
    BioCyc
```

---

# 10. Add a unified evidence record

Introduce a normalized evidence object, for example:

```python
@dataclass(frozen=True)
class SgprEvidence:
    source: str
    ec: str
    sgpr: SgprNode | None
    confidence: str
    status: str
    identifiers: tuple[str, ...] = ()
    provenance: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
```

Suggested statuses:

```text
resolved
candidate
partial
unresolved
conflict
```

Suggested confidence levels:

```text
authoritative
strong
reaction-matched
supporting
weak
```

---

# 11. Add source-merging logic

Create:

```python
merge_sgpr_evidence(
    evidence: Iterable[SgprEvidence]
) -> SgprResolution
```

The merger should not blindly union genes.

It should compare complete enzyme structures.

## Suggested precedence

For structural information:

```text
explicit Reactome/BioCyc complex structure
    >
reaction-matched structured evidence
    >
existing curated model GPR
    >
Rhea protein associations
    >
KEGG EC-gene fallback
```

The exact precedence should remain configurable.

## Conflicts

Example:

BioCyc:

```text
A and B
```

Reactome:

```text
A or B
```

This must produce a conflict record, not silently choose one.

Example:

```python
{
    "status": "conflict",
    "candidates": [
        {
            "source": "biocyc",
            "gpr": "(A and B)",
        },
        {
            "source": "reactome",
            "gpr": "(A or B)",
        },
    ],
}
```

---

# 12. Integrate into beta2 `collect-gpr-evidence`

Refactor the existing beta2 stage so every source returns `SgprEvidence`.

Conceptual flow:

```python
evidence = []

if "biocyc" in reaction_sources:
    evidence.extend(...)

if "rhea" in reaction_sources:
    evidence.extend(...)

if "reactome" in reaction_sources:
    evidence.extend(...)

if "kegg" in reaction_sources:
    evidence.extend(...)

resolution = merge_sgpr_evidence(evidence)
```

The resulting beta2 record should contain:

```python
{
    "candidate_gpr": "...",
    "candidate_sgpr": "...",
    "sgpr_structure": {...},
    "sgpr_status": "resolved",
    "sgpr_sources": [...],
    "sgpr_warnings": [...],
}
```

---

# 13. Replace flat `subunit_stoichiometry`

Deprecate using a single reaction-level mapping as the canonical representation:

```python
{
    "A": 2,
    "B": 1,
}
```

because alternative branches may require different coefficients.

Keep it only as a derived compatibility field where the GPR contains exactly one unambiguous enzyme complex.

Example:

```text
A*2 and B
```

can safely derive:

```python
{"A": 2, "B": 1}
```

but:

```text
(A*2 and B) or (A and C*3)
```

cannot.

In the latter case:

```python
subunit_stoichiometry = None
```

or use a branch-aware serialized representation.

---

# 14. Preserve the existing `get_gpr()` API

Do not break existing callers.

Keep:

```python
get_gpr(...)
```

returning the legacy five-field tuple.

Internally:

```text
get_gpr()
    ↓
get_gpr_evidence()
    ↓
resolve canonical SgprNode
    ↓
to_gpr()
to_legacy_sgpr()
    ↓
legacy tuple
```

This means callers get the same interface while correctness improves underneath.

---

# 15. Add a new explicit API

Expose a modern API such as:

```python
get_sgpr_evidence(ec, ...)
```

and:

```python
resolve_sgpr(ec, ...)
```

Example return:

```python
{
    "gpr": "(A and B) or (C)",
    "sgpr": "(A*2 and B*1) or (C)",
    "structure": {...},
    "status": "resolved",
    "confidence": "strong",
    "sources": ["reactome", "rhea"],
    "warnings": [],
}
```

---

# 16. Add provenance for every assertion

Every result should make it possible to answer:

- Where did this gene come from?
- Why is it `AND` rather than `OR`?
- Where did coefficient `2` come from?
- Was coefficient `1` observed or defaulted?
- Which reaction record was matched?
- Was BioCyc, Reactome, Rhea, KEGG, or UniProt responsible?

Suggested gene-node metadata:

```python
GeneNode(
    gene="A",
    coefficient=2,
    coefficient_status="observed",
    source="reactome",
    evidence=("R-HSA-123456",),
)
```

---

# Testing Plan

## 17. Unit tests for the AST

Add tests for:

```text
single gene
AND complex
OR isoenzymes
nested AND/OR
branch-specific coefficients
unknown coefficients
defaulted coefficients
normalization
deterministic serialization
```

Examples:

```text
A
A and B
A or B
(A and B) or C
(A*2 and B) or (A and C*3)
```

---

# 18. BioCyc regression tests

Test:

### Monomer

Input evidence:

```text
A
```

Expected:

```text
GPR  = A
sGPR = A*1
```

if BioCyc explicitly or compatibly supports one copy.

### Complex

Input:

```text
A x2
B x1
```

Expected:

```text
GPR  = A and B
sGPR = A*2 and B*1
```

### Alternative enzymes

Input:

```text
enzyme 1 = A + B
enzyme 2 = C
```

Expected:

```text
(A and B) or C
```

---

# 19. Reactome regression tests

Test:

- protein complex;
- entity set;
- isoenzyme;
- nested complexes;
- explicit stoichiometry;
- repeated components;
- unknown catalyst type;
- protein-to-gene mapping failures.

Ensure repeated members are not destroyed by `set()` deduplication.

---

# 20. Rhea tests

Test:

- unique EC→Rhea match;
- multiple Rhea reactions;
- no protein association;
- one associated gene;
- multiple associated genes;
- Rhea + Reactome enrichment;
- Rhea + UniProt enrichment.

Rhea-only multiple genes should not automatically become an `AND` complex.

---

# 21. KEGG tests

Verify:

```text
KEGG genes A, B, C
```

becomes canonical:

```text
A or B or C
```

with unknown coefficients.

Also test the legacy serializer separately:

```text
(A*1) or (B*1) or (C*1)
```

with coefficients marked as defaulted.

---

# 22. Legacy parity tests

Reuse existing legacy GPR characterization fixtures where possible.

Build a regression set containing:

```text
EC
legacy GPR
legacy sGPR
expected genes
expected identifiers
```

For each entry:

1. parse expected legacy result;
2. generate the new canonical AST;
3. compare normal GPR;
4. compare sGPR when the underlying evidence supports it;
5. flag intentional differences caused by correcting old behavior.

---

# 23. Cross-source conflict tests

Create synthetic examples.

### Agreement

BioCyc:

```text
A and B
```

Reactome:

```text
A and B
```

Expected:

```text
resolved / high confidence
```

### Structural conflict

BioCyc:

```text
A and B
```

Reactome:

```text
A or B
```

Expected:

```text
conflict
```

### Stoichiometry conflict

BioCyc:

```text
A*2 and B
```

Reactome:

```text
A*3 and B
```

Expected:

```text
conflict
```

Do not silently average or select a coefficient.

---

# 24. Integration tests

Run the complete beta2 GPR collection path using injected clients for:

- BioCyc;
- Reactome;
- Rhea;
- KEGG;
- UniProt.

Verify that the same EC can be processed with different source configurations.

Example configurations:

```yaml
reaction_sources:
  - biocyc
```

```yaml
reaction_sources:
  - rhea
  - reactome
  - uniprot
```

```yaml
reaction_sources:
  - rhea
  - reactome
  - kegg
```

```yaml
reaction_sources:
  - biocyc
  - rhea
  - reactome
  - kegg
  - uniprot
```

---

# 25. Add audit output

Extend beta2 output with an optional machine-readable evidence file:

```text
gpr_evidence.jsonl
```

Each reaction record should include:

```json
{
  "reaction_id": "R1",
  "ec": "1.2.3.4",
  "gpr": "(A and B) or C",
  "sgpr": "(A*2 and B*1) or C",
  "sources": ["rhea", "reactome"],
  "status": "resolved",
  "evidence": []
}
```

This makes debugging database disagreements much easier.

---

# 26. Documentation

Add:

```text
docs/protocol/sgpr_evidence.md
```

Document:

- canonical sGPR semantics;
- `AND` vs `OR`;
- coefficient meaning;
- observed vs inferred vs defaulted vs unknown;
- source-specific limitations;
- source precedence;
- conflict handling;
- legacy compatibility behavior.

Update the existing open-evidence documentation to make clear that open sources now participate in sGPR resolution rather than only ordinary GPR resolution.

---

# Suggested File Changes

## New files

```text
src/thg_protocol/gpr/stoichiometry.py
src/thg_protocol/gpr/evidence.py
src/thg_protocol/gpr/merge.py
src/thg_protocol/gpr/sources/biocyc.py
src/thg_protocol/gpr/sources/reactome.py
src/thg_protocol/gpr/sources/rhea.py
src/thg_protocol/gpr/sources/kegg.py

tests/unit/test_sgpr_ast.py
tests/unit/test_sgpr_serialization.py
tests/unit/test_sgpr_merge.py
tests/unit/test_sgpr_biocyc.py
tests/unit/test_sgpr_reactome.py
tests/unit/test_sgpr_rhea.py
tests/unit/test_sgpr_kegg.py
tests/integration/test_beta2_sgpr.py

docs/protocol/sgpr_evidence.md
```

## Existing files likely requiring modification

```text
src/thg_protocol/gpr/lookup.py
src/thg_protocol/services/biocyc.py
src/thg_protocol/services/reactome.py
src/thg_protocol/services/rhea.py
src/thg_protocol/workflow/beta2/_stages.py
tests/unit/test_biocyc_kegg_clients.py
docs/protocol/beta2_open_evidence_integration_plan.md
docs/protocol/beta2_open_evidence_integration_progress.md
```

---

# Recommended Implementation Order

## Phase 1 — Core representation

Implement:

- `GeneNode`;
- `AndNode`;
- `OrNode`;
- validation;
- normalization;
- `to_gpr()`;
- `to_sgpr()`;
- `to_legacy_sgpr()`.

Do not modify source integrations yet.

### Exit criteria

All AST and serializer unit tests pass.

---

## Phase 2 — Legacy BioCyc compatibility

Refactor `get_gpr()` so it uses the new representation internally.

Initially preserve current behavior where necessary, but mark generated coefficients as `defaulted`.

### Exit criteria

Existing callers and tests continue to pass with no API break.

---

## Phase 3 — Correct BioCyc complex parsing

Extend BioCyc evidence extraction to preserve:

- alternatives;
- complexes;
- component membership;
- supported multiplicity.

### Exit criteria

BioCyc no longer blindly converts every returned gene into an OR-ed `*1` expression.

---

## Phase 4 — Reactome structural sGPR

Refactor Reactome catalyst parsing to produce the canonical AST directly.

Preserve:

- `AND`;
- `OR`;
- nested entities;
- multiplicity;
- provenance.

### Exit criteria

Reactome can generate proper structural sGPRs without lossy gene-set flattening.

---

## Phase 5 — Rhea enrichment

Make Rhea evidence produce canonical candidate structures and enrich them through Reactome/UniProt when possible.

### Exit criteria

Rhea-associated proteins participate in sGPR resolution without invented complex structure.

---

## Phase 6 — KEGG fallback

Convert KEGG fallback to canonical evidence with unknown stoichiometry.

### Exit criteria

KEGG still works as fallback but no longer masquerades as measured `*1` stoichiometry internally.

---

## Phase 7 — Unified beta2 resolution

Replace source-specific candidate string manipulation in `collect-gpr-evidence` with:

```text
collect
→ normalize
→ merge
→ resolve
→ serialize
```

### Exit criteria

All configured reaction sources produce the same evidence schema.

---

## Phase 8 — Regression and live comparison

Run:

- unit tests;
- integration tests;
- legacy fixture comparisons;
- archived beta2 comparisons;
- live open-database comparisons;
- BioCyc comparison when an entitled BioCyc account is available.

Generate a report listing:

```text
identical
improved
changed due to corrected semantics
unresolved
source conflict
```

---

# Acceptance Criteria

The implementation is complete when all of the following are true:

- BioCyc no longer blindly assigns every gene `*1` and joins all genes with `OR`.
- Reactome preserves complex `AND` structure and alternative `OR` structure.
- Reactome multiplicity is preserved where explicitly provided.
- Rhea contributes reaction-matched protein evidence without inventing unsupported stoichiometry.
- KEGG fallback contributes GPR evidence with unknown/defaulted rather than falsely observed coefficients.
- UniProt can enrich protein/gene/subunit evidence.
- GOA remains localization-only.
- Standard GPR and sGPR are generated from the same canonical structure.
- Alternative complexes can contain different coefficients for the same gene.
- Provenance exists for coefficients and logical relationships.
- Conflicting sources are reported rather than silently collapsed.
- Existing `get_gpr()` callers continue to work.
- Existing beta2 workflows remain deterministic.
- Legacy fixtures are used as regression coverage.
- The pipeline can run with BioCyc disabled and still generate the best possible sGPR using open databases.

---

# Final Target Behavior

For a well-supported complex:

```text
Reactome:
A x2 + B x1
```

Result:

```text
GPR:
A and B

sGPR:
A*2 and B*1
```

For alternative complexes:

```text
complex 1:
A x2 + B

complex 2:
A + C x3
```

Result:

```text
GPR:
(A and B) or (A and C)

sGPR:
(A*2 and B*1) or (A*1 and C*3)
```

For KEGG-only evidence:

```text
A
B
C
```

Canonical result:

```text
GPR:
A or B or C

sGPR:
unknown stoichiometry
```

Legacy compatibility output may still be:

```text
(A*1) or (B*1) or (C*1)
```

but each coefficient must be internally recorded as `defaulted`, not observed.

This gives THG one consistent sGPR system across BioCyc and the open evidence stack while preserving compatibility and making the biological confidence of every result explicit.
