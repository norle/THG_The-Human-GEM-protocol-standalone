# THG Functional Implementation Plan

**Created:** 2026-08-06  
**Legacy functional reference:** `MarindeMasLab/THG_The-Human-GEM-protocol`  
**Maintained target:** `norle/THG_The-Human-GEM-protocol-standalone`  
**Purpose:** implement useful THG functionality without requiring one-to-one legacy behavior.

---

## 1. Instructions to the implementation agent

This document is both the implementation plan and the primary progress tracker.

The implementation agent must:

1. Read this file before starting work.
2. Update the status dashboard before and after each meaningful work session.
3. Mark a task complete only after its acceptance criteria and required tests pass.
4. Add a dated progress entry describing:
   - what changed;
   - files changed;
   - tests run and results;
   - unresolved issues;
   - the next recommended action.
5. Record scientific and architectural decisions in the decision log.
6. Record blockers in the blocker log rather than silently changing scope.
7. Link commits, pull requests, issues, reports, and run artifacts when available.
8. Preserve explicit paths, non-mutating model ownership, injected service clients, offline tests, and resumability.
9. Never label an output THGβ1 or THGβ2 until its release gate is satisfied.

### Progress-file policy

Use this file for progress tracking by default.

A separate `thg-implementation-progress.md` may be created when the chronological log becomes difficult to navigate. If created:

- keep the authoritative status dashboard in this file;
- link the progress file from the dashboard;
- move only detailed chronological entries;
- keep scope, decisions, blockers, and release gates here;
- never allow the two files to disagree about task status.

---

## 2. Status conventions

Use these exact values:

| Status | Meaning |
|---|---|
| `not-started` | No implementation work has begun |
| `in-progress` | Design or implementation work is active |
| `blocked` | Work requires a decision, fixture, dependency, credential, or external input |
| `implemented` | Code exists, but acceptance criteria are not fully verified |
| `verified` | Acceptance criteria and required tests pass |
| `deferred` | Intentionally postponed with a recorded reason |
| `rejected` | Deliberately excluded from scope with a recorded reason |

Checkboxes are supplementary. The status field is authoritative.

---

## 3. Goal

Build maintained, restartable workflows for:

1. **THGβ1:** curate an existing reference human GEM.
2. **THGβ2:** expand a validated β1 model using GPR and localization evidence.
3. **Human Database:** optionally harvest and reconstruct a database-derived human metabolic network.
4. **Final THG:** optionally merge β2 and Human Database branches and run final consistency checks.
5. **Validation:** reusable structural, chemical, solver-backed, MEMOTE, and metabolic-task checks.
6. **Comparison:** semantic model and workflow-artifact comparisons.
7. **Optional extensions:** gap filling, pathway workflows, publication reproduction, and cell-specific modeling.

The MarindeMasLab repository is a historical source of intended functionality, terminology, examples, and regression cases. It is not the maintained behavioral specification.

---

## 4. Core principles

### 4.1 Functionality over parity

Implement useful scientific behavior rather than legacy implementation details.

Do not preserve behavior solely because it existed in legacy code, including:

- exact Jaccard scores;
- historical synonym tie-breaking;
- implicit cytosol fallback;
- sequential ID allocation;
- raw HTML stored in model annotations;
- repository-relative writes;
- broad exception swallowing;
- pickle as the maintained runtime format.

### 4.2 Proposal before mutation

Every scientific mutation must follow:

```text
collect evidence
  ↓
normalize evidence
  ↓
generate proposals
  ↓
apply policy and overrides
  ↓
mutate a copied model
  ↓
validate
  ↓
export artifacts
```

The complete proposal artifact must be written before mutation, including in automatic mode.

### 4.3 Application modes

The default is:

```yaml
curation:
  mode: apply-all
```

Supported modes:

| Mode | Behavior |
|---|---|
| `apply-all` | Apply every valid proposal unless explicitly rejected |
| `report-only` | Generate proposals and reports without changing the model |
| `user-approved-only` | Apply only explicitly approved proposals |

`apply-all` means “apply all valid proposals,” not “invent a result when evidence is insufficient.” Unresolvable conflicts remain unresolved and are reported.

### 4.4 Decision precedence

1. Explicit rejection blocks a proposal.
2. Explicit replacement supersedes the generated proposal.
3. Explicit approval accepts a named proposal.
4. Otherwise the selected mode determines application.

### 4.5 Provenance

Every run must record:

- input checksums;
- upstream run and artifact references;
- source releases or retrieval dates;
- parser and client versions;
- COBRApy, libSBML, Python, MEMOTE, and solver versions when applicable;
- solver configuration and tolerances;
- configuration snapshot;
- override checksum;
- stage fingerprints;
- output checksums.

### 4.6 Deterministic IDs

Generated IDs must not depend on collection order, the current maximum ID, response ordering, Python hash order, or execution time.

### 4.7 Model ownership

Workflow stages operate on copied models and never overwrite caller-owned input artifacts.

---

## 5. Target workflows

| Workflow ID | Primary input | Primary output |
|---|---|---|
| `beta1` | Existing human GEM | Validated THGβ1 model |
| `beta2` | Validated β1 artifact | Validated THGβ2 model |
| `human-database` | Source snapshot or live services | Database-derived model |
| `final-thg` | β2 and Human Database artifacts | Merged validated model |
| `validate` | Any supported model | Validation bundle |
| `compare` | Two models or run artifacts | Semantic comparison report |
| `gapfill` | Model and candidate universe | Gapfill plan and optional model |
| `cell-specific` | Validated model and activity data | Context-specific model |

---

## 6. Status dashboard

Update this table whenever task status changes.

| ID | Workstream | Status | Owner | Last updated | Evidence |
|---|---|---|---|---|---|
| F0 | Workflow registry and artifact chaining | verified | maintained package | 2026-08-06 | `src/thg_protocol/workflow/registry.py`, `registered_runner.py`, `tests/integration/test_phase0_registered_workflow.py` |
| F1 | Scientific stage contracts | verified | maintained package | 2026-08-06 | `src/thg_protocol/workflow/contracts.py`, `tests/unit/test_phase0_foundations.py` |
| F2 | Evidence and provenance model | verified | maintained package | 2026-08-06 | `src/thg_protocol/workflow/evidence.py`, `tests/unit/test_phase0_foundations.py` |
| F3 | Proposal, decision, and change-ledger framework | verified | maintained package | 2026-08-06 | `src/thg_protocol/workflow/proposals.py`, `tests/unit/test_phase0_foundations.py` |
| F4 | Deterministic object-ID registry | verified | maintained package | 2026-08-06 | `src/thg_protocol/workflow/ids.py`, `tests/unit/test_phase0_foundations.py` |
| B1 | THGβ1 workflow | not-started | unassigned | 2026-08-06 | — |
| B2 | THGβ2 workflow | not-started | unassigned | 2026-08-06 | — |
| V1 | Validation framework | not-started | unassigned | 2026-08-06 | — |
| V2 | Metabolic tasks | not-started | unassigned | 2026-08-06 | — |
| V3 | MEMOTE integration | not-started | unassigned | 2026-08-06 | — |
| H1 | Human Database workflow | deferred | unassigned | 2026-08-06 | After β1/β2 foundations |
| M1 | Final semantic merge | deferred | unassigned | 2026-08-06 | After H1 and B2 |
| G1 | Gapfill framework | deferred | unassigned | 2026-08-06 | Optional extension |
| P1 | Pathway workflows | deferred | unassigned | 2026-08-06 | Scope review required |
| C1 | Cell-specific workflows | deferred | unassigned | 2026-08-06 | Separate from core THG |
| R1 | Restart and release validation | not-started | unassigned | 2026-08-06 | — |

---

# Phase 0 — Shared foundations

## F0. Workflow registry and workflow-specific DAGs

**Status:** `verified`

### Tasks

- [ ] Add a top-level `workflow` selector to configuration.
- [ ] Register stage DAGs by workflow ID.
- [ ] Validate dependencies independently for each DAG.
- [ ] Retain start, resume, status, lock, checksum, attempts, and forced-rerun behavior.
- [ ] Allow workflow-specific configuration sections.
- [ ] Reject keys that do not apply to the selected workflow.
- [ ] Add public CLI commands for β1, β2, validation, and comparison.

### Suggested configuration

```json
{
  "format_version": 2,
  "workflow": "beta1",
  "run": {
    "name": "human1-beta1",
    "output_dir": "runs/human1-beta1"
  }
}
```

### Acceptance criteria

- [ ] At least two test DAGs execute through the same runner.
- [ ] Resume skips valid completed stages.
- [ ] Forced rerun invalidates only the selected stage and descendants.
- [ ] Workflow-specific configuration validation is tested.
- [ ] Existing manifests have a documented compatibility or migration policy.

## F0.1 Upstream run artifact references

**Status:** `verified`

### Tasks

- [ ] Reference artifacts by run directory, stage ID, and artifact role.
- [ ] Verify upstream completion status.
- [ ] Verify artifact checksums.
- [ ] Record upstream fingerprints in downstream provenance.
- [ ] Reject ambiguous role matches.
- [ ] Detect upstream artifact changes.

### Required chains

```text
β1 → β2
β2 → final THG
Human Database → final THG
final THG → cell-specific
```

### Acceptance criteria

- [ ] A β2 fixture consumes a β1 artifact without manual copying.
- [ ] Artifact corruption produces a clear failure.
- [ ] Downstream reports identify their upstream runs.

---

## F1. Scientific stage contracts

**Status:** `verified`

Every scientific stage must define:

```yaml
id:
workflow:
purpose:
inputs:
outputs:
preconditions:
postconditions:
mutation:
side_effects:
failure_policy:
configuration:
provenance:
validation:
```

### Tasks

- [ ] Create a contract schema.
- [ ] Add one contract per public stage.
- [ ] Link implementation and tests to contract IDs.
- [ ] Classify each stage as analysis, collection, normalization, proposal, mutation, validation, or rendering.
- [ ] Document network, credential, solver, and optional dependency boundaries.
- [ ] Document ownership and mutation semantics.

### Acceptance criteria

- [ ] No public stage lacks a contract.
- [ ] CI validates required contract fields.
- [ ] A reviewer can determine what rerunning a stage may change.

---

## F2. Normalized evidence and provenance model

**Status:** `verified`

### Required evidence fields

- [ ] Evidence ID.
- [ ] Source and source version or retrieval time.
- [ ] Query.
- [ ] Normalized result.
- [ ] Raw-response path or checksum.
- [ ] Parser and normalization versions.
- [ ] Confidence or evidence category.
- [ ] Affected model objects.
- [ ] Errors, warnings, and retry history.
- [ ] License or redistribution restrictions when relevant.

### Storage requirements

- [ ] Versioned JSONL or equivalent streamable format.
- [ ] Content-addressed cache support.
- [ ] Recorded-response fixtures for default tests.
- [ ] Offline reruns from recorded evidence where possible.
- [ ] No large raw service payloads embedded in SBML annotations.
- [ ] No Python pickle as the maintained interchange format.

### Acceptance criteria

- [ ] A collection-dependent stage can rerun offline from recorded evidence.
- [ ] Raw and normalized records are connected by checksums.
- [ ] Unsupported schema versions fail clearly.

---

## F3. Proposals, decisions, and scientific change ledger

**Status:** `verified`

### Required proposal fields

```yaml
proposal_id:
operation:
object_type:
object_id:
before:
after:
evidence:
confidence:
policy:
stage:
status:
reason:
```

### Tasks

- [ ] Implement `apply-all`, `report-only`, and `user-approved-only`.
- [ ] Support `approve`, `reject`, `replace`, and `defer` decisions.
- [ ] Save proposals before mutation.
- [ ] Validate decision references.
- [ ] Record unapplied proposals and reasons.
- [ ] Fingerprint decision files.
- [ ] Prevent duplicate application on resume.
- [ ] Invalidate affected application stages and descendants when decisions change.

### Change ledger coverage

- [ ] Identifiers and annotations.
- [ ] Formula and charge.
- [ ] GPRs.
- [ ] Stoichiometry and bounds.
- [ ] Reactions, metabolites, and genes added or removed.
- [ ] Compartments.
- [ ] Groups and pathways.
- [ ] Duplicate consolidation.
- [ ] Manual overrides.

### Acceptance criteria

- [ ] All three modes produce identical proposal sets for identical inputs.
- [ ] `report-only` leaves the model signature unchanged.
- [ ] `user-approved-only` applies only accepted proposals.
- [ ] `apply-all` applies every valid proposal except explicit rejections.
- [ ] Every model mutation has a proposal and ledger entry.
- [ ] Ledger entries contain before and after values and evidence links.

---

## F4. Deterministic object-ID registry

**Status:** `verified`

### Tasks

- [ ] Define a versioned ID-generation policy.
- [ ] Persist source-to-generated mappings.
- [ ] Detect collisions.
- [ ] Reuse mappings on resume.
- [ ] Represent source object and target compartment relationships.
- [ ] Support imported IDs and aliases.

### Acceptance criteria

- [ ] Two clean runs produce identical generated IDs.
- [ ] Unrelated input additions do not renumber existing generated objects.
- [ ] Conflicting mappings fail rather than silently remap.

---

# Phase 1 — THGβ1

## B1. Definition

**Status:** `not-started`

THGβ1 is a curated version of a supplied human reference GEM in which identifiers, annotations, formulas, charges, GPRs, and obvious structural inconsistencies have been reviewed and improved without systematic compartment-specific reaction expansion.

The legacy β1.1 annotation checkpoint may exist as an internal artifact but is not required as a separate public model.

## B1.1 Proposed DAG

```text
beta1-input
  ↓
beta1-inventory
  ↓
collect-metabolite-evidence
  ↓
resolve-metabolite-identities
  ↓
collect-reaction-evidence
  ↓
resolve-reaction-identities
  ↓
normalize-genes
  ↓
curate-gprs
  ↓
generate-curation-proposals
  ↓
apply-curation
  ↓
balance-audit
  ↓
generate-balance-proposals
  ↓
apply-balance-proposals
  ↓
deduplicate-and-clean
  ↓
validate-beta1
  ↓
export-beta1
```

## B1.2 Input and inventory

**Status:** `not-started`

### Tasks

- [ ] Load COBRA JSON and SBML.
- [ ] Record checksum, source version, objective, compartments, and software versions.
- [ ] Validate duplicate IDs and object references.
- [ ] Inventory identifier coverage.
- [ ] Inventory missing formulas and charges.
- [ ] Inventory invalid and missing GPRs.
- [ ] Classify boundary, exchange, demand, sink, biomass, transport, spontaneous, and pseudo-reactions.
- [ ] Report orphan genes and metabolites.
- [ ] Produce model counts and compartment coverage.

### Acceptance criteria

- [ ] Input is never overwritten.
- [ ] Inventory does not mutate the model.
- [ ] Every reaction has a classification or explicit unknown status.
- [ ] Reports are machine-readable and summarized for humans.

## B1.3 Metabolite identity resolution

**Status:** `not-started`

### Tasks

- [ ] Gather candidates from existing annotations and configured sources.
- [ ] Normalize identifier namespaces.
- [ ] Compare names, formulas, charges, and structural identifiers.
- [ ] Separate chemical identity from compartment identity.
- [ ] Represent protonation and charge-state relationships explicitly.
- [ ] Preserve useful secondary identifiers.
- [ ] Report conflicts and ambiguous candidates.
- [ ] Distinguish service failure from no match.
- [ ] Generate proposals rather than mutate directly.

### Recommended evidence precedence

1. Curated structural identifier mappings.
2. Existing high-quality database identifiers.
3. Formula and charge compatibility.
4. Curated synonyms.
5. Name similarity as supporting evidence only.

### Acceptance criteria

- [ ] Ambiguous cases remain unresolved unless a configured rule produces a valid winner.
- [ ] Every selection records its reason.
- [ ] Retry, checkpoint, and offline behavior are tested.

## B1.4 Reaction identity resolution

**Status:** `not-started`

### Tasks

- [ ] Compare normalized stoichiometry using accepted metabolite identities.
- [ ] Recognize reaction reversal.
- [ ] Support strict and configurable proton/water normalization.
- [ ] Distinguish exact identity, equivalent chemistry, probable match, and conflict.
- [ ] Detect duplicate chemistry within compartments.
- [ ] Detect shared identifiers with conflicting chemistry.
- [ ] Generate structured proposals and reports.

### Acceptance criteria

- [ ] Match results record normalization policy and rationale.
- [ ] Matching is deterministic.
- [ ] No exact legacy Jaccard result is required.
- [ ] Reversal, duplicate, and conflict fixtures exist.

## B1.5 Gene normalization and canonical GPR representation

**Status:** `not-started`

### Tasks

- [ ] Normalize stable gene identifiers and preserve aliases.
- [ ] Record deprecated replacements and conflicts.
- [ ] Detect missing and unused genes.
- [ ] Parse GPRs into a formal AST.
- [ ] Preserve nested `AND` and `OR` semantics.
- [ ] Represent isoenzymes, complexes, and optional subunit stoichiometry.
- [ ] Rewrite GPRs through the gene mapping.
- [ ] Detect dangling references.
- [ ] Serialize GPRs deterministically.

### Acceptance criteria

- [ ] Round-trip tests preserve Boolean meaning.
- [ ] The same AST is reused by β1, β2, Human Database, tasks, comparison, and cell-specific workflows.
- [ ] String manipulation occurs only at import/export boundaries.

## B1.6 Formula and charge audit

**Status:** `not-started`

### Required statuses

```text
balanced
unbalanced
not-evaluable-missing-formula
not-evaluable-missing-charge
not-evaluable-generic-formula
excluded-boundary
excluded-biomass
excluded-pseudo-reaction
```

### Tasks

- [ ] Parse multi-letter elements correctly.
- [ ] Treat missing formulas as unevaluable, not balanced.
- [ ] Separate mass and charge status.
- [ ] Produce residual element and charge vectors.
- [ ] Define glycan, polymer, R-group, and X-group policies.
- [ ] Record excluded reaction classes.

### Acceptance criteria

- [ ] Boundary and biomass semantics are explicit.
- [ ] Missing data is never silently ignored.
- [ ] Audit does not mutate the model.
- [ ] Tests cover overlapping symbols, missing formulas, generic groups, and unsatisfiable cases.

## B1.7 Balance proposals and application

**Status:** `not-started`

### Supported proposal types

- [ ] Add or remove proton.
- [ ] Add or remove water.
- [ ] Adjust coefficients.
- [ ] Correct formula or charge.
- [ ] Flag incorrect identity or directionality.
- [ ] Mark intentionally generic or excluded.

### Required metadata

- [ ] Imbalance before and after.
- [ ] Changed species and coefficients.
- [ ] Evidence and chemical justification.
- [ ] Confidence category.
- [ ] Possible semantic or solver impact.

### Acceptance criteria

- [ ] Proposal generation and application are separate stages.
- [ ] Arbitrary numerical balancing is not considered valid without an explicitly configured strategy.
- [ ] Every stoichiometric mutation is ledgered.
- [ ] Validation reruns after application.

## B1.8 Duplicate consolidation and cleanup

**Status:** `not-started`

### Tasks

- [ ] Consolidate accepted duplicate metabolites, reactions, and genes.
- [ ] Remap GPRs.
- [ ] Preserve annotations and provenance.
- [ ] Preserve or update objectives and groups.
- [ ] Record retained and removed IDs.
- [ ] Remove isolated objects only under explicit policy.
- [ ] Report unresolved conflicts.

### Acceptance criteria

- [ ] Consolidation is deterministic.
- [ ] No dangling references remain.
- [ ] Conflicts are not resolved by collection order.

## B1.9 β1 validation and outputs

**Status:** `not-started`

### Required validation

- [ ] JSON and SBML export/reload.
- [ ] Unique IDs and valid references.
- [ ] Valid GPRs.
- [ ] Complete mapping application.
- [ ] Complete unresolved-conflict report.
- [ ] Mass/charge status for every reaction.
- [ ] Valid objective and groups.
- [ ] Ledger agrees with semantic diff.
- [ ] No accidental systematic compartment expansion.
- [ ] Feasibility and objective feasibility where applicable.
- [ ] Blocked-reaction and optional flux-consistency reports.

### Output bundle

```text
thg-beta1.xml
thg-beta1.json
beta1-signature.json
beta1-proposals.jsonl
beta1-change-ledger.jsonl
beta1-unresolved.tsv
beta1-validation.json
beta1-summary.md
evidence/
mappings/
```

### β1 release gate

The output may be labeled THGβ1 only when:

- [ ] All β1 stage contracts exist.
- [ ] A deterministic end-to-end fixture passes.
- [ ] A sanctioned human-model run completes.
- [ ] Required validation passes or approved exceptions are recorded.
- [ ] Proposal, decision, evidence, mapping, and ledger artifacts are complete.
- [ ] Restart and invalidation tests pass.
- [ ] Documentation states exact workflow behavior and limitations.

---

# Phase 2 — THGβ2

## B2. Definition

**Status:** `not-started`

THGβ2 is a compartment-expanded derivative of a validated β1 model in which enzyme isoforms and protein complexes are assigned to supported locations and new reaction/metabolite copies are generated only where GPR and localization evidence supports them.

## B2.1 Proposed DAG

```text
load-beta1
  ↓
collect-catalysis-evidence
  ↓
resolve-gprs
  ↓
collect-location-evidence
  ↓
normalize-compartments
  ↓
infer-complex-and-isoenzyme-locations
  ↓
generate-expansion-plan
  ↓
apply-expansion-decisions
  ↓
apply-expansion
  ↓
consolidate-expanded-model
  ↓
validate-beta2
  ↓
export-beta2
```

## B2.2 β1 input gate

**Status:** `not-started`

### Tasks

- [ ] Consume a verified β1 run artifact.
- [ ] Allow explicitly declared external β1-equivalent inputs.
- [ ] Verify checksums, GPR parsing, and compartment mapping.
- [ ] Reject unresolved fatal β1 conflicts.
- [ ] Record exceptions for external inputs.

### Acceptance criteria

- [ ] β2 cannot silently label an arbitrary enriched model as β1.
- [ ] External equivalent mode is explicit and provenance-recorded.

## B2.3 Catalysis and localization evidence

**Status:** `not-started`

### Tasks

- [ ] Collect EC and reaction annotations.
- [ ] Collect gene/protein associations.
- [ ] Represent isoenzymes and complexes.
- [ ] Preserve optional subunit stoichiometry.
- [ ] Record evidence per GPR branch.
- [ ] Build a versioned compartment registry.
- [ ] Normalize location synonyms.
- [ ] Distinguish direct, inferred, conflicting, and unresolved evidence.
- [ ] Require explicit fallback configuration; never silently assign cytosol.

### Acceptance criteria

- [ ] Evidence is normalized, not stored only as raw pages.
- [ ] Complex and isoenzyme structure survives serialization.
- [ ] Every expansion compartment exists in the registry.
- [ ] Recorded fixtures cover direct, complex, multi-location, missing, and conflicting cases.

## B2.4 Complex and isoenzyme location semantics

**Status:** `not-started`

### Required rules

- For `A or B`, supported locations are the union of independently supported branches.
- For `A and B`, supported locations are normally the intersection of locations supported by all required subunits.
- For `(A and B) or C`, localize each OR branch independently and combine surviving branches by compartment.

### Tasks

- [ ] Evaluate location support over the canonical GPR AST.
- [ ] Produce compartment-specific GPRs.
- [ ] Remove unsupported branches per compartment.
- [ ] Record evidence for surviving and rejected branches.
- [ ] Represent incomplete complexes.
- [ ] Make uncertainty policy configurable.

### Acceptance criteria

- [ ] Tests cover union, intersection, mixed rules, unresolved genes, and conflicts.
- [ ] A complex is never assigned to a compartment unsupported by a required subunit.
- [ ] Results are proposals before mutation.

## B2.5 Expansion planner

**Status:** `not-started`

For each eligible reaction, determine:

- [ ] Target compartments.
- [ ] Compartment-specific GPR.
- [ ] Create versus update action.
- [ ] Equivalent existing reaction.
- [ ] Required metabolite copies.
- [ ] Deterministic IDs.
- [ ] Bounds policy.
- [ ] Group and pathway membership.
- [ ] Source-reaction provenance.
- [ ] Reaction-type eligibility.
- [ ] Conflicts and invalid proposals.

### Acceptance criteria

- [ ] Full expansion plan is written before mutation.
- [ ] Plan generation is deterministic.
- [ ] Equivalent existing chemistry is detected semantically.
- [ ] Invalid proposals are reported rather than partially applied.

## B2.6 Reaction-type policies

**Status:** `not-started`

| Reaction class | Initial default |
|---|---|
| Internal enzymatic | Eligible |
| Spontaneous | Retain; do not expand from GPR evidence |
| Exchange | Never expand |
| Demand | Never expand |
| Sink | Never expand |
| Biomass | Never expand |
| Pseudo-reaction | Never expand |
| Transport | Exclude from generic expansion |
| Multi-compartment | Exclude from generic expansion |
| Generic/polymer chemistry | Report or require explicit policy |
| No GPR/EC evidence | Retain; do not expand automatically |

### Acceptance criteria

- [ ] Every reaction receives a policy result.
- [ ] Excluded classes are reported.
- [ ] Generic expansion cannot clone exchange, demand, sink, biomass, or pseudo-reactions.

## B2.7 Transport scope

**Status:** `not-started`

Initial recommendation: do not implement generic transport expansion in the first β2 release.

### Interim requirements

- [ ] Classify transport and membrane reactions.
- [ ] Curate their GPRs.
- [ ] Preserve existing transport reactions.
- [ ] Exclude them from generic compartment cloning.
- [ ] Report potentially missing transport functionality.

## B2.8 Expansion application and consolidation

**Status:** `not-started`

### Tasks

- [ ] Copy metabolites safely with formula, charge, annotation, and provenance.
- [ ] Create or update reaction copies.
- [ ] Assign compartment-specific GPRs and optional S-GPR information.
- [ ] Preserve bounds unless policy changes them.
- [ ] Preserve groups and pathways.
- [ ] Add source-reaction relationships.
- [ ] Record all mutations.
- [ ] Detect equivalent reactions, duplicate metabolites, and ID collisions.
- [ ] Consolidate repeated GPR branches.
- [ ] Remove new orphans only under explicit policy.

### Acceptance criteria

- [ ] Resume does not duplicate copies.
- [ ] Generated IDs match the registry.
- [ ] Every applied action corresponds to a proposal and decision.
- [ ] Failure preserves the previous valid checkpoint.
- [ ] Consolidation is deterministic and ledgered.

## B2.9 β2 validation and outputs

**Status:** `not-started`

### Required validation

- [ ] Every added reaction links to a β1 source, evidence, and proposal.
- [ ] Every added metabolite links to a source metabolite.
- [ ] No excluded reaction class was expanded.
- [ ] All new GPRs parse.
- [ ] Complex location rules are satisfied.
- [ ] No reaction uses wrong-compartment metabolites.
- [ ] Duplicate chemistry is resolved or reported.
- [ ] Every new reaction has mass and charge status.
- [ ] Model exports and reloads.
- [ ] β1-to-β2 semantic diff is complete.
- [ ] β1 and β2 feasibility are recorded.
- [ ] Objective, blocked-reaction, and cycle-risk changes are summarized.

### Output bundle

```text
thg-beta2.xml
thg-beta2.json
beta2-expansion-plan.jsonl
beta2-proposals.jsonl
beta2-change-ledger.jsonl
beta2-location-evidence.jsonl
beta2-unresolved.tsv
beta2-validation.json
beta1-to-beta2-diff.json
beta2-summary.md
```

### β2 release gate

The output may be labeled THGβ2 only when:

- [ ] β1 input gate passes.
- [ ] Canonical GPR representation is used.
- [ ] Compartment ontology is versioned.
- [ ] Complex and isoenzyme location semantics are implemented and tested.
- [ ] Expansion plan exists before mutation.
- [ ] Reaction-type policies are enforced.
- [ ] IDs and provenance are deterministic and complete.
- [ ] Deterministic and sanctioned-model runs complete.
- [ ] Restart and invalidation tests pass.
- [ ] Required validation passes or approved exceptions are recorded.

---

# Phase 3 — Validation, tasks, and MEMOTE

## V1. Validation framework

**Status:** `not-started`

### Profiles

```text
structural-fast
beta1-standard
beta2-standard
final-standard
release-full
```

### Check families

- [ ] Model load and reference integrity.
- [ ] Identifier uniqueness.
- [ ] GPR parsing and references.
- [ ] Formula and charge balance.
- [ ] Stoichiometric consistency.
- [ ] Flux consistency.
- [ ] Blocked reactions.
- [ ] Dead-end topology.
- [ ] Unconserved metabolites.
- [ ] Minimal inconsistent sets where practical.
- [ ] Energy-generating cycles.
- [ ] Objective feasibility.
- [ ] Workflow-specific invariants.
- [ ] Ledger-to-diff consistency.

### Solver metadata

- [ ] Solver and version.
- [ ] Configuration.
- [ ] Feasibility and optimality tolerances.
- [ ] Objective.
- [ ] Status.
- [ ] Deterministic ordering or tie-breaking policy where relevant.

### Acceptance criteria

- [ ] Checks are independently callable.
- [ ] Structural and solver-backed checks are separated.
- [ ] Boundary and biomass semantics are explicit.
- [ ] Profiles define severity and release-blocking behavior.

## V2. Metabolic tasks

**Status:** `not-started`

### Required schema

- [ ] Stable task ID and version.
- [ ] Uptake and secretion constraints.
- [ ] Temporary reactions.
- [ ] Changed bounds.
- [ ] Objective.
- [ ] Expected pass/fail.
- [ ] Task group.
- [ ] Stable identity references.
- [ ] Solver requirements.
- [ ] Diagnostics.

### Acceptance criteria

- [ ] Tasks do not permanently mutate input models.
- [ ] Temporary objects do not leak.
- [ ] Per-task solver status is recorded.
- [ ] Infrastructure failure is distinct from biological task failure.
- [ ] Core and full suites are versioned.

## V3. MEMOTE

**Status:** `not-started`

### Tasks

- [ ] Pin or record MEMOTE version.
- [ ] Record solver.
- [ ] Capture logs and machine-readable results.
- [ ] Retain rendered report when configured.
- [ ] Support thresholds.
- [ ] Distinguish command failure from failed model tests.
- [ ] Add a real small-model CI smoke test.
- [ ] Keep full-model execution optional or scheduled.

### Acceptance criteria

- [ ] Verification uses a real MEMOTE invocation, not only a fake executable.
- [ ] Report artifacts are checksum-recorded.
- [ ] MEMOTE remains separate from pure package checks.

---

# Phase 4 — Human Database and final THG

## H1. Human Database workflow

**Status:** `deferred`

Begin after the evidence schema, GPR representation, compartment ontology, and β1/β2 foundations are stable.

### Proposed DAG

```text
source-snapshot
  ↓
pathway-selection
  ↓
harvest-reactions
  ↓
harvest-compounds
  ↓
harvest-genes-and-gprs
  ↓
harvest-locations
  ↓
normalize-records
  ↓
construct-reactions
  ↓
expand-compartments
  ↓
balance-audit
  ↓
reconstruct-model
  ↓
validate-database-model
```

### Requirements

- [ ] Live and offline snapshot modes.
- [ ] One source adapter at a time.
- [ ] Bounded retries and rate limits.
- [ ] Error records and resumable batches.
- [ ] Cache manifest and recorded-response tests.
- [ ] Versioned normalized record schema.
- [ ] Offline reconstruction.
- [ ] Explicit credential boundary.

### Optional historical import

A separate isolated converter may read legacy pickle artifacts and emit normalized JSON/SBML. It must run without network access, use pinned dependencies, treat input as untrusted executable serialization, and never become a package-import requirement.

## M1. Final semantic merge

**Status:** `deferred`

### Proposed DAG

```text
load-beta2-and-database
  ↓
resolve-metabolite-equivalences
  ↓
resolve-gene-equivalences
  ↓
resolve-reaction-equivalences
  ↓
generate-merge-plan
  ↓
apply-merge-decisions
  ↓
apply-merge
  ↓
validate-and-analyze
  ↓
optional-bounded-repair
  ↓
export-final
```

### Requirements

- [ ] Cross-ID metabolite equivalence.
- [ ] Compartment-aware identity.
- [ ] Gene reconciliation.
- [ ] Reaction equivalence after metabolite mapping.
- [ ] Direction and proton/water normalization policies.
- [ ] Formula, charge, bounds, and GPR conflict categories.
- [ ] Source-precedence policy.
- [ ] Merge plan before mutation.
- [ ] Provenance on merged objects.
- [ ] Bounded repair loop with explicit stop conditions.
- [ ] Full validation and tasks.

---

# Phase 5 — Optional extensions

## G1. Gapfill framework

**Status:** `deferred`

Gap filling is not part of core β1 or β2 correctness.

Potential use cases:

- Human Database completion;
- final merge repair;
- pathway implementation;
- task repair;
- cell-specific reconstruction.

Requirements include a common strategy interface, deterministic and MILP strategies, candidate coverage, solver metadata, explicit failure states, and no leakage of temporary sinks or sources.

## P1. Pathway workflows

**Status:** `deferred`

Before porting any legacy validation family, record its scientific question, owner, actionable output, dependency class, and overlap with model-wide validation. Separate structural, database-backed, solver-backed, and rendering functions.

## C1. Cell-specific workflows

**Status:** `deferred`

Keep separate from core THG construction. Future scope may include transcript mapping, GPR activity evaluation, context-specific algorithms, task preservation, solver provenance, and uncertainty reporting.

---

# Phase 6 — Comparison, restart, and release

## Semantic comparison

**Status:** `not-started`

Required comparisons:

```text
input → β1
β1 → β2
β2 + Human Database → final
release → release
uninterrupted run → resumed run
```

Group changes by:

- identifier normalization;
- annotation enrichment;
- formula or charge correction;
- GPR correction;
- localization expansion;
- database-only addition;
- duplicate consolidation;
- manual override;
- validation-result changes;
- task-result changes.

Publication-era counts may be reported as historical context but are not acceptance criteria.

## R1. Restart and invalidation testing

**Status:** `not-started`

For β1 and β2:

- [ ] Run from a clean directory.
- [ ] Resume unchanged and verify no valid stage reruns.
- [ ] Change a decision file and verify targeted invalidation.
- [ ] Change evidence and verify appropriate invalidation.
- [ ] Corrupt an artifact and verify checksum detection.
- [ ] Interrupt a stage and verify recovery.
- [ ] Compare interrupted/resumed and uninterrupted final artifacts.
- [ ] Verify failed attempts are preserved.
- [ ] Verify previous valid checkpoints are not overwritten.
- [ ] Verify generated IDs remain stable.

## Release milestones

### Milestone A — Shared foundations

- Workflow registry.
- Artifact chaining.
- Stage contracts.
- Proposal modes and ledger.
- Evidence schema.
- Deterministic IDs.
- Restart tests on a miniature workflow.

### Milestone B — Deterministic THGβ1 fixture

- Full β1 DAG.
- Offline recorded evidence.
- All application modes.
- Validation and export/reload.

### Milestone C — Deterministic THGβ2 fixture

- Full β2 DAG.
- Complex and isoenzyme localization.
- Expansion planning and application.
- β1-to-β2 comparison.

### Milestone D — Sanctioned human model

- Real reference model.
- Recorded configuration and source data.
- Full β1 and β2 runs.
- Release reports and documented unresolved items.

Every milestone must record supported capabilities, fixtures, environment, CI command, artifact set, owner, limitations, and rollback or stop condition.

---

## 7. Capability registry

Maintain a machine-readable registry containing:

```yaml
capability:
support_tier:
owner:
entry_point:
scientific_status:
implementation_status:
verification:
workflow_coverage:
known_limitations:
decision_log_refs:
```

Support tiers:

- `release-supported`
- `research-supported`
- `experimental`
- `archived`
- `rejected`

Do not use a single ambiguous status such as `partial`.

---

## 8. Explicit non-goals for the core β1/β2 release

- Exact one-to-one MarindeMasLab behavior.
- Exact Jaccard-score reproduction.
- Legacy synonym tie-breaking.
- Legacy formula-tokenization quirks.
- Silent cytosol fallback.
- Raw service pages embedded in model annotations.
- Sequential generated IDs.
- Pickle as a maintained runtime format.
- Exact publication counts as acceptance criteria.
- Generic transport expansion in the first β2 release.
- Automatic gap filling after β1/β2 validation failures.
- Cell-specific reconstruction as part of core THG construction.
- A graphical review interface.
- Publication artifact reproduction unless separately scoped.

---

## 9. Open decisions

### D-OPEN-001 — Automatic balance policy

Determine which balance proposal classes are valid in `apply-all`, including proton/water changes, coefficient changes, and generic compounds.

### D-OPEN-002 — S-GPR scope

Determine whether complete subunit stoichiometry is required for the first β2 release or whether storage-only support is sufficient.

### D-OPEN-003 — External β1-equivalent inputs

Define the validation profile and provenance needed for an external model to enter β2.

### D-OPEN-004 — Transport expansion

Determine whether a later release needs dedicated transport expansion and which membrane ontology and evidence sources are required.

### D-OPEN-005 — Human Database priority

Determine whether live harvesting is required soon after β2 or whether recorded snapshots are initially sufficient.

### D-OPEN-006 — Release-blocking validation

Define which checks block β1, β2, and final THG, and which exceptions require explicit approval.

---

## 10. Decision log

Add new entries at the bottom. Never rewrite a previous decision without marking it superseded.

### D-001 — Functionality over legacy parity

**Date:** 2026-08-06  
**Status:** accepted

The maintained repository will implement useful scientific functionality without requiring one-to-one behavioral parity with MarindeMasLab code.

### D-002 — Separate THGβ1 and THGβ2 workflows

**Date:** 2026-08-06  
**Status:** accepted

THGβ1 and THGβ2 are first-class, independently restartable workflows with separate release gates and artifacts.

### D-003 — Default application mode

**Date:** 2026-08-06  
**Status:** accepted

The default is `apply-all`. `report-only` and `user-approved-only` remain supported. Explicit rejection and replacement override the default.

### D-004 — Progress tracking

**Date:** 2026-08-06  
**Status:** accepted

This file is the primary progress tracker. A separate detailed log may be created only under the policy in Section 1.

### D-005 — Additive workflow configuration migration

**Date:** 2026-08-06  
**Status:** accepted

Format-1 configurations and manifests remain supported as a compatibility path.
Format 2 is selected explicitly with `format_version: 2` and `workflow`; it
uses dynamic registered DAGs and does not reinterpret existing manifests.

### D-006 — Fixture workflow labeling

**Date:** 2026-08-06  
**Status:** accepted

The Phase 0 registered `beta1` and `beta2` DAGs are deterministic orchestration
fixtures. They must not be labeled THGβ1 or THGβ2 until the scientific release
gates in this plan are satisfied.

---

## 11. Blocker log

Use this template:

```markdown
### BLOCK-XXX — Title

**Date opened:**
**Owner:**
**Affected tasks:**
**Description:**
**Required decision or input:**
**Temporary workaround:**
**Status:**
**Date resolved:**
**Resolution:**
```

No blockers recorded yet.

---

## 12. Progress log

Add newest entries at the top.

### 2026-08-06 — Phase 0 foundations implemented

**Tasks worked on**

- F0, F0.1: registered format-2 workflow DAGs, dynamic manifests, public CLI
  aliases, explicit upstream artifact references, checksum verification, and
  downstream fingerprints.
- F1: machine-readable stage contracts for registered and legacy public stages.
- F2: versioned JSONL evidence, content-addressed raw cache, offline checksum
  verification, and normalized-result checksums.
- F3: proposal modes, decision validation, replacement/rejection/defer policy,
  and idempotent change ledger.
- F4: persisted deterministic source-to-target ID mappings and collision checks.
- R1: clean start, resume, forced descendant invalidation, and corruption
  behavior are covered by the registered workflow tests.

**Status changes**

- F0–F4: `not-started` → `verified` for the Phase 0 acceptance scope.
- Existing format-1 manifests remain supported under the compatibility policy.

**Summary**

Format 2 is selected with `format_version: 2` and a top-level `workflow` key.
The maintained fixture workflows are `beta1`, `beta2`, `validate`, and
`compare`; their stages exercise shared orchestration foundations and are not
scientific THGβ1/β2 release artifacts.

**Files changed**

- `src/thg_protocol/workflow/`
- `tests/unit/test_phase0_foundations.py`
- `tests/integration/test_phase0_registered_workflow.py`
- `docs/workflows/phase0-foundations.md`

**Tests run**

- `ruff check src/thg_protocol/workflow tests/unit/test_phase0_foundations.py tests/integration/test_phase0_registered_workflow.py`
  - Result: passed.
- `pytest -q tests/unit/test_phase0_foundations.py tests/integration/test_phase0_registered_workflow.py tests/unit/test_workflow_config.py tests/unit/test_workflow_manifest.py tests/unit/test_workflow_runner.py tests/unit/test_workflow_cli.py`
  - Result: passed.
- `pytest -q`
  - Result: 1897 passed, 7 skipped.

**Decisions made**

- D-005: format-2 registered workflows are additive; format-1 manifests remain
  the documented compatibility path.
- D-006: Phase 0 fixture DAGs provide orchestration evidence only and cannot be
  labeled THGβ1 or THGβ2.

**Blockers**

- None.

**Known limitations**

- Scientific β1/β2 mutation stages, sanctioned-model release gates, and final
  THG construction remain later phases.

**Recommended next action**

- Begin the scientific β1 input/inventory contract and offline model fixture
  while retaining the Phase 0 proposal-before-mutation boundary.

### 2026-08-06 — Plan created

**Status changes**

- Created the functionality-first implementation plan.
- Established β1 and β2 as separate restartable workflows.
- Set `apply-all` as the default application mode.
- Retained `report-only` and `user-approved-only`.
- Added progress, decision, blocker, provenance, stage-contract, proposal, deterministic-ID, validation, and release requirements.

**Files changed**

- `thg-functional-implementation-plan.md`

**Tests run**

- None; planning artifact only.

**Open items**

- Assign owners.
- Select the first milestone.
- Resolve open decisions as implementation reaches them.

**Recommended next action**

Begin Phase 0 with the workflow registry, stage-contract schema, proposal framework, evidence schema, and deterministic ID registry.

---

## 13. Work-session update template

```markdown
### YYYY-MM-DD — Brief title

**Tasks worked on**

- F0:
- F1:

**Status changes**

- `not-started` → `in-progress`
- `implemented` → `verified`

**Summary**

Describe what was implemented or investigated.

**Files changed**

- `path/to/file.py`
- `path/to/test.py`

**Tests run**

- `command`
  - Result:

**Artifacts or evidence**

- Commit:
- Pull request:
- Report:
- Run directory:

**Decisions made**

- D-XXX:

**Blockers**

- BLOCK-XXX:

**Known limitations**

- ...

**Recommended next action**

- ...
```

---

## 14. Definition of done for an individual task

A task may be marked `verified` only when all applicable conditions hold:

- [ ] Implementation exists behind the maintained package boundary.
- [ ] Scientific stage contract exists.
- [ ] Unit tests pass.
- [ ] Integration tests pass.
- [ ] An offline deterministic fixture exists.
- [ ] Errors and unresolved cases are tested.
- [ ] Provenance is recorded.
- [ ] Proposal and ledger behavior is tested when mutation occurs.
- [ ] Resume and invalidation behavior is tested when used in a workflow.
- [ ] Documentation is updated.
- [ ] Capability registry is updated.
- [ ] Acceptance criteria in this file are satisfied.
- [ ] Progress log includes evidence.

---

## 15. Recommended first implementation slice

1. Add the workflow registry.
2. Implement upstream artifact references.
3. Define the scientific stage-contract schema.
4. Implement proposal and decision modes.
5. Implement the scientific change ledger.
6. Define the normalized evidence schema.
7. Implement deterministic ID mappings.
8. Add restart and invalidation integration tests.
9. Build a miniature demonstration workflow using all shared foundations.
10. Update this file with status, files, tests, decisions, blockers, and evidence.

Do not begin full β1 mutation logic until this shared foundation is verified.
