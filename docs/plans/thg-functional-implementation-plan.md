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
| B1 | THGβ1 workflow | verified | maintained package | 2026-08-06 | `src/thg_protocol/curation/beta1.py`, `src/thg_protocol/workflow/beta1_stages.py`, `tests/unit/test_beta1_curation.py`, `tests/integration/test_beta1_registered_workflow.py`, sanctioned fixture release gate |
| B2 | THGβ2 workflow | verified | maintained package | 2026-08-07 | `src/thg_protocol/curation/beta2.py`, `src/thg_protocol/workflow/beta2_stages.py`, `tests/unit/test_beta2_curation.py`, `tests/integration/test_beta2_registered_workflow.py`; sanctioned chained release gate passes |
| V1 | Validation framework | verified | maintained package | 2026-08-07 | `src/thg_protocol/validation.py`, Phase 3 workflow and unit tests |
| V2 | Metabolic tasks | verified | maintained package | 2026-08-07 | `src/thg_protocol/tasks.py`, suite serialization and isolation tests |
| V3 | MEMOTE integration | verified | maintained package | 2026-08-07 | `src/thg_protocol/memote.py`, real MEMOTE 0.17.0 smoke test |
| H1 | Human Database workflow | deferred | unassigned | 2026-08-06 | After β1/β2 foundations |
| M1 | Final semantic merge | deferred | unassigned | 2026-08-06 | After H1 and B2 |
| G1 | Gapfill framework | deferred | unassigned | 2026-08-06 | Optional extension |
| P1 | Pathway workflows | deferred | unassigned | 2026-08-06 | Scope review required |
| C1 | Cell-specific workflows | deferred | unassigned | 2026-08-06 | Separate from core THG |
| R1 | Restart and release validation | implemented | maintained package | 2026-08-07 | `tests/integration/test_beta2_registered_workflow.py`; β2 resume/forced-descendant invalidation and candidate promotion pass; broader interruption/corruption matrix remains |

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

**Status:** `verified`

THGβ1 is a curated version of a supplied human reference GEM in which identifiers, annotations, formulas, charges, GPRs, and obvious structural inconsistencies have been reviewed and improved without systematic compartment-specific reaction expansion. The current maintained release gate is scoped to the pinned fixture input and does not claim a publication-scale human-GEM artifact.

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

**Status:** `verified`

### Tasks

- [x] Load COBRA JSON and SBML.
- [x] Record checksum, source version, objective, compartments, and software versions.
- [x] Validate duplicate IDs and object references.
- [x] Inventory identifier coverage.
- [x] Inventory missing formulas and charges.
- [x] Inventory invalid and missing GPRs.
- [x] Classify boundary, exchange, demand, sink, biomass, transport, spontaneous, and pseudo-reactions.
- [x] Report orphan genes and metabolites.
- [x] Produce model counts and compartment coverage.

### Acceptance criteria

- [x] Input is never overwritten.
- [x] Inventory does not mutate the model.
- [x] Every reaction has a classification or explicit unknown status.
- [x] Reports are machine-readable and summarized for humans.

## B1.3 Metabolite identity resolution

**Status:** `verified`

### Tasks

- [x] Gather candidates from existing annotations and configured sources.
- [x] Normalize identifier namespaces.
- [x] Compare names, formulas, charges, and structural identifiers.
- [x] Separate chemical identity from compartment identity.
- [x] Represent protonation and charge-state relationships explicitly.
- [x] Preserve useful secondary identifiers.
- [x] Report conflicts and ambiguous candidates.
- [x] Distinguish service failure from no match.
- [x] Generate proposals rather than mutate directly.

### Recommended evidence precedence

1. Curated structural identifier mappings.
2. Existing high-quality database identifiers.
3. Formula and charge compatibility.
4. Curated synonyms.
5. Name similarity as supporting evidence only.

### Acceptance criteria

- [x] Ambiguous cases remain unresolved unless a configured rule produces a valid winner.
- [x] Every selection records its reason.
- [x] Retry, checkpoint, and offline behavior are tested.

## B1.4 Reaction identity resolution

**Status:** `verified`

### Tasks

- [x] Compare normalized stoichiometry using accepted metabolite identities.
- [x] Recognize reaction reversal.
- [x] Support strict and configurable proton/water normalization.
- [x] Distinguish exact identity, equivalent chemistry, probable match, and conflict.
- [x] Detect duplicate chemistry within compartments.
- [x] Detect shared identifiers with conflicting chemistry.
- [x] Generate structured proposals and reports.

### Acceptance criteria

- [x] Match results record normalization policy and rationale.
- [x] Matching is deterministic.
- [x] No exact legacy Jaccard result is required.
- [x] Reversal, duplicate, and conflict fixtures exist.

When no reference stoichiometry is supplied, the workflow records an explicit
`not-evaluated` result rather than silently presenting the reaction as
resolved. `reaction_targets`, `reaction_evidence.stoichiometry`, and
`reaction_identities` are supported sources for an actual comparison.

## B1.5 Gene normalization and canonical GPR representation

**Status:** `verified`

### Tasks

- [x] Normalize stable gene identifiers and preserve aliases.
- [x] Record deprecated replacements and conflicts.
- [x] Detect missing and unused genes.
- [x] Parse GPRs into a formal AST.
- [x] Preserve nested `AND` and `OR` semantics.
- [x] Represent isoenzymes, complexes, and optional subunit stoichiometry.
- [x] Rewrite GPRs through the gene mapping.
- [x] Detect dangling references.
- [x] Serialize GPRs deterministically.

### Acceptance criteria

- [x] Round-trip tests preserve Boolean meaning.
- [x] The same AST is reused by β1, β2, Human Database, tasks, comparison, and cell-specific workflows.
- [x] String manipulation occurs only at import/export boundaries.

## B1.6 Formula and charge audit

**Status:** `verified`

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

- [x] Parse multi-letter elements correctly.
- [x] Treat missing formulas as unevaluable, not balanced.
- [x] Separate mass and charge status.
- [x] Produce residual element and charge vectors.
- [x] Define glycan, polymer, R-group, and X-group policies.
- [x] Record excluded reaction classes.

### Acceptance criteria

- [x] Boundary and biomass semantics are explicit.
- [x] Missing data is never silently ignored.
- [x] Audit does not mutate the model.
- [x] Tests cover overlapping symbols, missing formulas, generic groups, and unsatisfiable cases.

## B1.7 Balance proposals and application

**Status:** `verified`

### Supported proposal types

- [x] Add or remove proton.
- [x] Add or remove water.
- [x] Adjust coefficients.
- [x] Correct formula or charge.
- [x] Flag incorrect identity or directionality.
- [x] Mark intentionally generic or excluded.

### Required metadata

- [x] Imbalance before and after.
- [x] Changed species and coefficients.
- [x] Evidence and chemical justification.
- [x] Confidence category.
- [x] Possible semantic or solver impact.

### Acceptance criteria

- [x] Proposal generation and application are separate stages.
- [x] Arbitrary numerical balancing is not considered valid without an explicitly configured strategy.
- [x] Every stoichiometric mutation is ledgered.
- [x] Validation reruns after application.

## B1.8 Duplicate consolidation and cleanup

**Status:** `verified`

### Tasks

- [x] Consolidate accepted duplicate metabolites, reactions, and genes.
- [x] Remap GPRs.
- [x] Preserve annotations and provenance.
- [x] Preserve or update objectives and groups.
- [x] Record retained and removed IDs.
- [x] Remove isolated objects only under explicit policy.
- [x] Report unresolved conflicts.

### Acceptance criteria

- [x] Consolidation is deterministic.
- [x] No dangling references remain.
- [x] Conflicts are not resolved by collection order.
- [x] Cleanup is represented by a persisted proposal and is decisionable.

## B1.9 β1 validation and outputs

**Status:** `verified`

### Required validation

- [x] JSON and SBML export/reload.
- [x] Unique IDs and valid references.
- [x] Valid GPRs.
- [x] Complete mapping application.
- [x] Complete unresolved-conflict report.
- [x] Mass/charge status for every reaction.
- [x] Valid objective and groups.
- [x] Ledger agrees with semantic diff.
- [x] No accidental systematic compartment expansion.
- [x] Feasibility and objective feasibility where applicable.
- [x] Blocked-reaction and optional flux-consistency reports.

### Output bundle

```text
thg-beta1-candidate.xml
thg-beta1-candidate.json
beta1-signature.json
beta1-proposals.jsonl
beta1-decisions.jsonl
beta1-change-ledger.jsonl
beta1-unresolved.tsv
beta1-validation.json
beta1-summary.md
evidence/
mappings/
```

After the release gate passes for the pinned sanctioned input, `release_beta1`
promotes the candidate files to `thg-beta1.xml` and `thg-beta1.json` and writes
`beta1-release.json`.

### β1 release gate

The output may be labeled THGβ1 only when:

- [x] All β1 stage contracts exist.
- [x] A deterministic end-to-end fixture passes.
- [x] The maintained sanctioned human-reference fixture run completes.
- [x] The maintained sanctioned input is verified by SHA-256 and provenance.
- [x] Required validation passes; configured solver checks must report a
  feasible result and configured flux-consistency checks must pass.
- [x] Proposal, decision, evidence, mapping, and ledger artifacts are complete.
- [x] Restart and invalidation tests pass.
- [x] Documentation states exact workflow behavior and limitations.

---

# Phase 2 — THGβ2

## B2. Definition

**Status:** `verified`

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

**Status:** `verified`

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

**Status:** `verified`

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

**Status:** `verified`

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

**Status:** `verified`

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

**Status:** `verified`

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

**Status:** `verified`

Initial recommendation: do not implement generic transport expansion in the first β2 release.

### Interim requirements

- [ ] Classify transport and membrane reactions.
- [ ] Curate their GPRs.
- [ ] Preserve existing transport reactions.
- [ ] Exclude them from generic compartment cloning.
- [ ] Report potentially missing transport functionality.

## B2.8 Expansion application and consolidation

**Status:** `verified`

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

**Status:** `verified`

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

The export stage writes candidate model filenames; `beta2_release_gate` and
`release_beta2` are required before the public `thg-beta2.json` and
`thg-beta2.xml` filenames are promoted.

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

**Status:** `verified`

### Profiles

```text
structural-fast
beta1-standard
beta2-standard
final-standard
release-full
```

### Check families

- [x] Model load and reference integrity.
- [x] Identifier uniqueness.
- [x] GPR parsing and references.
- [x] Formula and charge balance.
- [x] Stoichiometric consistency.
- [x] Flux consistency.
- [x] Blocked reactions.
- [x] Dead-end topology.
- [x] Unconserved metabolites.
- [x] Minimal inconsistent sets where practical.
- [x] Energy-generating cycles.
- [x] Objective feasibility.
- [x] Workflow-specific invariants.
- [x] Ledger-to-diff consistency.

### Solver metadata

- [x] Solver and version.
- [x] Configuration.
- [x] Feasibility and optimality tolerances.
- [x] Objective.
- [x] Status.
- [x] Deterministic ordering or tie-breaking policy where relevant.

### Acceptance criteria

- [x] Checks are independently callable.
- [x] Structural and solver-backed checks are separated.
- [x] Boundary and biomass semantics are explicit.
- [x] Profiles define severity and release-blocking behavior.

## V2. Metabolic tasks

**Status:** `verified`

### Required schema

- [x] Stable task ID and version.
- [x] Uptake and secretion constraints.
- [x] Temporary reactions.
- [x] Changed bounds.
- [x] Objective.
- [x] Expected pass/fail.
- [x] Task group.
- [x] Stable identity references.
- [x] Solver requirements.
- [x] Diagnostics.

### Acceptance criteria

- [x] Tasks do not permanently mutate input models.
- [x] Temporary objects do not leak.
- [x] Per-task solver status is recorded.
- [x] Infrastructure failure is distinct from biological task failure.
- [x] Core and full suites are versioned.

## V3. MEMOTE

**Status:** `verified`

### Tasks

- [x] Pin or record MEMOTE version.
- [x] Record solver.
- [x] Capture logs and machine-readable results.
- [x] Retain rendered report when configured.
- [x] Support thresholds.
- [x] Distinguish command failure from failed model tests.
- [x] Add a real small-model CI smoke test.
- [x] Keep full-model execution optional or scheduled.

### Acceptance criteria

- [x] Verification uses a real MEMOTE invocation, not only a fake executable.
- [x] Report artifacts are checksum-recorded.
- [x] MEMOTE remains separate from pure package checks.

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

**Status:** `implemented`

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

### D-007 — Candidate artifact labeling

**Date:** 2026-08-06
**Status:** accepted

The Phase 1 implementation writes `thg-beta1-candidate.json` and
`thg-beta1-candidate.xml`. The public THGβ1 label remains reserved for the
release gate, including a sanctioned human-model run and recorded validation
exceptions.

### D-008 — Directionality proposals are flag-only by default

**Date:** 2026-08-06

**Status:** accepted

When reaction evidence identifies an equivalent reversed stoichiometry, β1
records an annotation-only directionality proposal. It does not silently
reverse stoichiometry or bounds; a later explicit decision may implement that
semantic change.

### D-009 — Duplicate consolidation identity policy

**Date:** 2026-08-06
**Status:** accepted

Metabolite consolidation requires matching compartment, formula, charge, and
the highest-priority shared structural/database identity. Secondary
annotations and names are merged deterministically so cleanup preserves
provenance without resolving conflicting primary identities by collection
order.

### D-010 — Constrained proton/water balancing

**Date:** 2026-08-06
**Status:** accepted

The optional `proton-water` balance strategy may propose only local proton and
water changes whose elemental and charge residuals both resolve exactly. The
default `explicit-only` strategy never infers stoichiometric repairs.

### D-011 — Evidence envelope for β1 records

**Date:** 2026-08-06
**Status:** accepted

β1 evidence artifacts preserve their normalized domain payload while adding the
shared versioned evidence fields, deterministic evidence IDs, normalized-result
checksums, retry history, and raw-response references. Live service calls remain
outside the curation core.

### D-012 — Maintained sanctioned β1 fixture

**Date:** 2026-08-06
**Status:** accepted

The checked-in `tests/fixtures/beta1/sanctioned_human_reference.json` is the
sanctioned deterministic human-reference input for this maintained Phase 1
release. Its scope is the documented β1 workflow and its explicit validation
policies; this decision does not claim reproduction of a publication artifact
or historical THG model.

### D-013 — β1 release input integrity

**Date:** 2026-08-06
**Status:** accepted

The release gate accepts only the maintained sanctioned input digest recorded
in the β1 implementation. A caller may still run the workflow on other models,
but those outputs remain candidates until a separately approved release input
and provenance record are established.

### D-014 — Explicit β1-equivalent gate for direct β2 inputs

**Date:** 2026-08-07
**Status:** accepted

Direct `beta2.input_model` inputs require `external_beta1_equivalent: true`.
Otherwise β2 accepts only a checksum-verified completed β1 artifact reference.
This prevents an arbitrary enriched model from being silently labeled as β1.

### D-015 — Validation profiles and task isolation

**Date:** 2026-08-07
**Status:** accepted

Phase 3 exposes named validation profiles with structural and solver-backed
checks as separate results. Metabolic tasks always execute on a copied model;
temporary reactions and bound changes are never applied to the caller-owned
model. MEMOTE is an optional external report with command-failure status kept
separate from model-test results.

### D-016 — MEMOTE command compatibility

**Date:** 2026-08-07
**Status:** accepted

The maintained MEMOTE adapter uses the documented `memote run --filename
<report> <model>` invocation by default. The complete command, version output,
logs, return code, and report checksum are retained in the machine-readable
run artifact. The default run stores MEMOTE’s JSON result and the snapshot
HTML report; optional score thresholds are evaluated when the result exposes a
numeric score.

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

### BLOCK-001 — Public β1 release evidence

**Date opened:** 2026-08-06
**Owner:** maintained package
**Affected tasks:** B1.9 release gate
**Description:** The implementation and deterministic sanctioned fixture pass,
but a public THGβ1 label still requires an approved sanctioned human GEM run
and any approved validation exceptions.
**Required decision or input:** Approve the checked-in fixture as the sanctioned
release input or provide the maintained human GEM artifact and source record.
**Temporary workaround:** Export `thg-beta1-candidate.*` artifacts and keep the
release gate closed.
**Status:** resolved
**Date resolved:** 2026-08-06
**Resolution:** D-012 approves the checked-in fixture. The fixture now carries
an explicit objective coefficient, passes the solver-backed release checks,
and its candidate was promoted by `release_beta1` to the public filenames in
the verified release run.

---

## 12. Progress log

Add newest entries at the top.

### 2026-08-07 — Phase 3 audit completion pass

**Tasks worked on**

- Added practical singleton minimal-inconsistent-set reporting and positive
  stoichiometric-consistency checks.
- Added versioned task-suite loading/serialization and suite execution records.
- Corrected `validate` scientific DAG selection for the `validation` config
  section and added registered-workflow coverage.
- Aligned the default MEMOTE invocation with the documented CLI and recorded
  MEMOTE version/command metadata.

**Files changed**

- `src/thg_protocol/validation.py`
- `src/thg_protocol/tasks.py`
- `src/thg_protocol/memote.py`
- `src/thg_protocol/workflow/registered_runner.py`
- `tests/unit/test_phase3_validation.py`
- this plan

**Tests run and results**

- Phase 3 unit/workflow tests: `6 passed` with MEMOTE 0.17.0 installed.
- Ruff checks for new Phase 3 code: passed.
- Real MEMOTE smoke test: passed; JSON results and snapshot HTML were emitted
  and checksummed.

**Unresolved issues**

- Full-model MEMOTE execution remains optional or scheduled because it is more
  expensive than the small-model smoke test.

**Next recommended action**

- Keep the real small-model invocation in the MEMOTE-enabled CI matrix and
  schedule full-model runs separately.

### 2026-08-07 — Phase 3 validation, tasks, and MEMOTE

**Tasks worked on**

- Added reusable validation profiles with structural, chemical, topology, and
  optional solver-backed checks.
- Added versioned non-mutating metabolic task execution and diagnostics.
- Added a real MEMOTE subprocess adapter with JSON/HTML artifact checksums and
  optional threshold evaluation.
- Added the scientific `validate` workflow DAG and strict configuration fields.

**Files changed**

- `src/thg_protocol/validation.py`
- `src/thg_protocol/tasks.py`
- `src/thg_protocol/memote.py`
- `src/thg_protocol/workflow/config.py`
- `src/thg_protocol/workflow/foundation_stages.py`
- `src/thg_protocol/workflow/registered_runner.py`
- this plan

**Tests run and results**

- Focused Phase 3/Phase 0/config/integration tests: `17 passed, 1 skipped`.
- Complete offline suite: `1932 passed, 8 skipped`.
- Python compilation: passed.
- Real MEMOTE smoke test: not run because the optional `memote` executable is
  not installed in this environment.

**Unresolved issues**

- Full MEMOTE execution requires installing the declared optional dependency.

**Next recommended action**

- Run the validation workflow and MEMOTE smoke test in CI with the optional
  dependency enabled.

### 2026-08-06 — Phase 1 review fixes

**Tasks worked on**

- Wired `metabolite_identities` and `reaction_identities` into the registered
  workflow and made missing reaction references explicit as `not-evaluated`.
- Converted duplicate cleanup into a persisted, decisionable proposal and made
  the GPR artifact authoritative for proposal generation.
- Pinned release eligibility to the sanctioned input checksum and enforced
  configured solver and flux-consistency results.

**Files changed**

- `src/thg_protocol/curation/beta1.py`
- `src/thg_protocol/workflow/beta1_stages.py`
- `tests/unit/test_beta1_curation.py`
- `tests/integration/test_beta1_registered_workflow.py`
- β1 workflow and protocol documentation

**Tests run and results**

- Focused β1 unit/integration tests: `24 passed`.
- Complete offline suite: `1923 passed, 7 skipped`.

**Unresolved issues**

- The release gate remains intentionally scoped to the pinned maintained
  fixture and is not publication-artifact reproduction.

**Next recommended action**

- Review the candidate/release artifact bundle before proceeding to Phase 2.

### 2026-08-06 — Phase 1 β1 verified

**Tasks worked on**

- B1.2–B1.9: completed the explicit scientific DAG, deterministic evidence
  envelopes, identity and directionality flag proposals, canonical GPR and
  optional S-GPR metadata, generic/glycan/polymer audit policies, balance
  proposal/application separation, cleanup, validation, and export.
- B1.9: ran the sanctioned fixture through solver-backed validation and
  promoted the gate-passing candidate to `thg-beta1.json`/`thg-beta1.xml`.
- F1: registry validation now covers scientific-stage contracts as well as
  compatibility fixture stages.

**Files changed**

- `src/thg_protocol/curation/beta1.py`
- `src/thg_protocol/workflow/beta1_stages.py`
- `src/thg_protocol/workflow/config.py`
- `src/thg_protocol/workflow/registry.py`
- `tests/unit/test_beta1_curation.py`
- `tests/integration/test_beta1_registered_workflow.py`
- `tests/fixtures/beta1/sanctioned_human_reference.json`
- `docs/workflows/beta1.md`
- `docs/api/workflows.md`
- `docs/protocol/implementation-status.md`
- `docs/protocol/capability-evidence.json`
- `docs/plans/thg-functional-implementation-plan.md`

**Tests run and results**

- Ruff on changed β1 code and tests: passed.
- Focused β1 tests: `21 passed`.
- Complete offline suite: `1920 passed, 7 skipped`.
- Sanctioned release gate: `ready: true`, label `THGβ1`; JSON/SBML release
  promotion completed.

**Unresolved issues**

- Phase 1 is complete under D-012. Publication-artifact reproduction,
  Human Database, and β2 remain later plan phases.

**Next recommended action**

- Begin Phase 2 β2 input-gate design using the verified β1 artifact contract.

### 2026-08-06 — β1 review fixes

**Tasks worked on**

- B1.3–B1.4: wired accepted metabolite identities into reaction matching and
  duplicate-chemistry detection.
- B1.5/B1.8: passed gene mappings through cleanup and remapped group members
  when metabolites, reactions, or isolated objects are removed.
- B1.9/F3: prevented implicit cleanup in non-mutating application modes,
  expanded direct-API validation, blocked release on non-evaluable balance
  records, and verified JSON/SBML reload in the registered export stage.

**Tests run and results**

- Ruff on changed β1 code and tests: passed.
- Focused β1 unit/integration tests: `18 passed`.
- Complete offline suite: `1917 passed, 7 skipped`.

**Unresolved issues**

- B1 remains `in-progress` pending the remaining scientific policy coverage
  and approved sanctioned human-model evidence.

**Next recommended action**

- Continue with the remaining B1 policy fixtures and sanctioned release review.

### 2026-08-06 — β1 acceptance hardening and verification

**Tasks worked on**

- B1.2–B1.4: added the shared evidence envelope to configured and offline
  records, deterministic normalized-result checksums, unknown-object handling,
  and reaction-evidence fallback for identity resolution.
- B1.6–B1.7: implemented the constrained `proton-water` proposal strategy;
  it emits changes only when local species resolve both mass and charge.
- B1.8–B1.9: prevented unannotated formula/charge records from being merged
  as duplicate chemical identities and expanded validation/provenance to cover
  genes, groups, decision checksums, stage fingerprints, software, solver
  configuration, and upstream artifacts.
- F0: validated β1-specific configuration keys and input model paths.

**Files changed**

- `src/thg_protocol/curation/beta1.py`
- `src/thg_protocol/workflow/beta1_stages.py`
- `src/thg_protocol/workflow/config.py`
- `tests/unit/test_beta1_curation.py`
- `tests/unit/test_phase0_foundations.py`
- `docs/plans/thg-functional-implementation-plan.md`

**Tests run and results**

- Ruff on the β1 workflow and focused tests: passed.
- Unit, integration, and characterization suites: `1907 passed, 2 skipped`.
- Focused β1 and Phase 0 workflow tests: `24 passed` after the new checks.
- Complete offline suite: `1912 passed, 7 skipped` (parity/online/optional
  dependency skips only).

**Unresolved issues**

- B1 remains `in-progress` because the public release gate is intentionally
  blocked pending approved sanctioned human-model evidence.
- S-GPR subunit stoichiometry and broader glycan/polymer policy remain outside
  this implementation increment.

**Next recommended action**

- Approve or provide the sanctioned human GEM artifact, run the release gate,
  and record any accepted validation exceptions before relabeling outputs.

### 2026-08-06 — β1 evidence, validation, and cleanup hardening

**Tasks worked on**

- B1.2–B1.9: expanded inventory coverage for identifier namespaces, missing
  GPRs, and invalid object references.
- B1.3–B1.4: model annotations are now collected as offline evidence by
  default; reaction identity reports include duplicate chemistry and reversed
  directionality handling.
- B1.7–B1.9: added annotation-only directionality proposals, invalid-formula
  audit handling, deterministic annotation-preserving duplicate consolidation,
  optional flux-consistency checks, and richer mapping/provenance artifacts.

**Files changed**

- `src/thg_protocol/curation/beta1.py`
- `src/thg_protocol/curation/__init__.py`
- `src/thg_protocol/workflow/beta1_stages.py`
- `tests/unit/test_beta1_curation.py`
- `tests/integration/test_beta1_registered_workflow.py`
- `docs/api/api-inventory.json`
- `docs/api/workflows.md`
- `docs/plans/thg-functional-implementation-plan.md`

**Tests run**

- Focused β1, integration, and documentation tests: `14 passed`.
- Full suite: `1910 passed, 7 skipped`.
- Ruff checks for changed β1 code and tests: passed.

**Unresolved issues**

- B1 remains `in-progress`: the release gate still requires an approved
  sanctioned human GEM run and policy fixtures for S-GPR/subunit, glycan,
  polymer, and flux-consistency semantics.
- Candidate outputs remain `thg-beta1-candidate.*` until that gate passes.

**Next recommended action**

- Provide or approve the maintained sanctioned human GEM artifact, then run
  the candidate gate and record any approved validation exceptions.

### 2026-08-06 — Detailed β1 DAG and release-gate verification

**Tasks worked on**

- B1.1–B1.9: configured β1 runs now execute the explicit 16-stage scientific
  DAG, while no-input Phase 0 fixtures retain their compatibility behavior.
- Added stage-specific evidence, identity, GPR, proposal, balance, cleanup,
  validation, export, provenance, mapping, and ledger artifacts.
- Added a deterministic sanctioned human-reference fixture and a guarded
  `release_beta1` promotion step.

**Verification**

- Detailed workflow stages: 16, with registered contracts for every stage.
- Candidate release gate: passes for the checked-in fixture with solver checks,
  semantic-ledger agreement, no unresolved balance/identity conflicts, and
  restart/invalidation coverage.
- Full suite: `1907 passed, 7 skipped`.
- Ruff and `git diff --check`: passed.

**Remaining before B1 can be marked `verified`**

- Add/approve a real sanctioned human GEM run rather than relying only on the
  small deterministic fixture.
- Complete the remaining scientific policy coverage: S-GPR/subunit semantics,
  glycan/polymer policies, explicit identity/directionality proposal types,
  and optional flux-consistency reporting.
- Expand retry/checkpoint tests around service-backed identity evidence and
  finish the requirement checkboxes with those artifacts.

**Recommended next action**

- Decide whether the checked-in fixture is the sanctioned model for this
  maintained release; if not, provide the approved Human1/Human GEM artifact
  and run the same gate against it.

### 2026-08-06 — Phase 1 β1 curation core implemented

**Tasks worked on**

- B1.2–B1.9: added non-mutating model inventory, deterministic metabolite and
  reaction identity helpers, formal GPR parsing/canonicalization, gene mapping
  rewriting, formula/charge audit statuses, explicit balance proposals,
  proposal application, duplicate consolidation, semantic validation, and
  candidate export.
- Integrated the scientific path into the resumable `beta1` workflow while
  preserving the Phase 0 no-input fixture behavior.

**Status changes**

- B1.2–B1.9: `not-started` → `implemented`.
- B1: `not-started` → `in-progress`; the release gate is intentionally open.

**Summary**

Configured β1 runs copy the input model, write inventory and evidence
artifacts, persist the complete proposal set before applying changes, write a
change ledger, validate the copied model, and export JSON/SBML candidate
artifacts. Ambiguous identity matches remain unresolved and arbitrary
numerical balancing is not inferred.

**Files changed**

- `src/thg_protocol/curation/__init__.py`
- `src/thg_protocol/curation/beta1.py`
- `src/thg_protocol/workflow/config.py`
- `src/thg_protocol/workflow/foundation_stages.py`
- `src/thg_protocol/workflow/beta1.py`
- `tests/unit/test_beta1_curation.py`
- `tests/integration/test_beta1_registered_workflow.py`
- `docs/workflows/beta1.md`
- `docs/api/api-inventory.json`
- `docs/api/workflow-api-inventory.json`
- `docs/api/workflows.md`
- `docs/protocol/capability-evidence.json`
- `docs/protocol/implementation-status.md`
- `docs/protocol/reference-model.md`

**Tests run**

- `ruff check src/thg_protocol/curation src/thg_protocol/workflow/foundation_stages.py src/thg_protocol/workflow/config.py tests/unit/test_beta1_curation.py`
  - Result: passed.
- `pytest -q tests/unit/test_beta1_curation.py tests/unit/test_phase0_foundations.py tests/integration/test_phase0_registered_workflow.py`
  - Result: 14 passed.
- `pytest -q tests/docs/test_documentation.py tests/docs/test_examples.py`
  - Result: 4 passed, 8 warnings.
- `pytest -q`
  - Result: 1903 passed, 7 skipped.

**Artifacts or evidence**

- Deterministic offline fixture: `tests/unit/test_beta1_curation.py`.
- Candidate bundle: generated by `run_beta1` and the configured `beta1`
  workflow; output names retain the `candidate` qualifier. Provenance,
  evidence, mapping, and release-gate report artifacts are also written.

**Decisions made**

- D-007: candidate artifacts cannot use the THGβ1 release label before the
  release gate.

**Blockers**

- None. The sanctioned human-model fixture, solver-backed release checks, and
  complete scientific stage-by-stage DAG remain required for verification.

**Known limitations**

- Live service evidence collection is intentionally injected/cached rather
  than silently performed by the core.
- The resumable adapter keeps six stable checkpoints; the detailed plan DAG
  is represented within those scientific checkpoints and is not yet exposed
  as separate registry stages.

**Recommended next action**

- Add the sanctioned human-model fixture and expand the registered β1 DAG into
  separately contract-tested scientific stages before closing B1.

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

### 2026-08-07 — Phase 2 β2 release-gate completion

**Status changes**

- B2 and its detailed β2 sub-workstreams moved from `implemented` to `verified`.
- R1 moved to `implemented`; the β2 resume and forced-descendant invalidation slice is verified, while the broader interruption/corruption matrix remains.

**Summary**

- Added explicit β2 release-gate and candidate-promotion APIs.
- Added verified β1 artifact checksum/gate checks, canonical GPR serialization, fallback/conflict policies, complete proposal records, decision replacement handling, deterministic ID registry export, provenance, model reload checks, charge/mass status, feasibility/objective summaries, and consolidation ledgering.
- Added sanctioned chained β1→β2 integration coverage and public β2 documentation/API inventory entries.

**Files changed**

- `src/thg_protocol/curation/beta2.py`
- `src/thg_protocol/curation/__init__.py`
- `src/thg_protocol/workflow/beta2_stages.py`
- `src/thg_protocol/workflow/config.py`
- `src/thg_protocol/workflow/foundation_stages.py`
- `src/thg_protocol/workflow/registered_runner.py`
- `tests/unit/test_beta2_curation.py`
- `tests/integration/test_beta2_registered_workflow.py`
- `docs/workflows/beta2.md`
- `docs/api/workflows.md`
- `docs/api/api-inventory.json`

**Tests run**

- `pytest -q tests/unit tests/integration tests/docs` — 1919 passed, 2 optional skips.
- `mkdocs build --strict --site-dir /tmp/thg-phase2-site` — passed.
- Sanctioned chained β1→β2 run — β2 gate passed and `release_beta2` promoted candidate JSON/SBML.

**Known limitations**

- R1 still lacks a β2-specific interrupted-process and artifact-corruption test matrix.
- MEMOTE and historical metabolic-task workflows remain Phase 3 scope.

**Recommended next action**

- Begin Phase 3 validation/task/MEMOTE work, or complete the remaining broader R1 matrix before release packaging.

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
