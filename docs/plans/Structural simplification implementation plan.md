# Structural simplification implementation plan

## Goal

Reduce the maintenance cost of the largest workflow modules without changing
scientific behavior, artifact contracts, or public APIs.

The immediate structural pressure points are:

- `src/thg_protocol/workflow/beta2/_stages.py` — workflow orchestration,
  evidence collection, resolution policy, model mutation, and serialization are
  concentrated in one large stage dispatcher.
- `src/thg_protocol/curation/beta1.py` — a large domain module with a broad
  public API.

The first implementation target is the β2 GPR path because it is actively
changing and currently mixes workflow orchestration with scientific selection
policy.

## Constraints

- Preserve all public package APIs.
- Preserve registered workflow IDs and stage IDs.
- Preserve stage dependencies and execution order.
- Preserve artifact roles, filenames where contractually relevant, schemas,
  manifests, hashes, checkpoints, and provenance fields.
- Preserve current scientific behavior exactly unless a separate scientific
  change is explicitly proposed.
- Keep `thg_protocol.runtime` independent from workflow and scientific-domain
  code.
- Do not introduce a generic stage framework.
- Do not split modules solely because of line count.
- Prefer pure functions and existing domain packages over new workflow
  abstractions.
- Keep the refactor reviewable as a sequence of small commits.

## Target architecture

Keep `DetailedBeta2Stage` as the workflow orchestration boundary.

The intended separation is:

```text
workflow/beta2/
├── __init__.py
├── definition.py
└── _stages.py
    ├── read config
    ├── load dependency artifacts
    ├── call domain functions
    ├── write stage artifacts
    └── return StageResult

gpr/
├── existing GPR parsing / evidence / merge APIs
└── selection.py
    └── pure model-vs-evidence GPR selection policy
```

`_stages.py` should remain responsible for workflow concerns.

The `gpr` package should own reusable scientific GPR decision logic.

This change does **not** attempt to split all β2 stages into separate modules.

---

## Phase 1 — remove confirmed dead code

### 1. Delete `_resolve_gpr_payload`

Remove the unused helper from:

```text
src/thg_protocol/workflow/beta2/_stages.py
```

Before deletion, confirm there are no runtime, test, documentation, or public
imports referring to it.

### Verification

Run the focused β2 tests that cover GPR resolution and the registered workflow.

At minimum:

```bash
pytest tests/unit/test_beta2_curation.py
pytest tests/unit/test_beta2_evidence.py
pytest tests/integration/test_beta2_registered_workflow.py
pytest tests/integration/test_beta2_live_snapshot_replay.py
```

No behavior or artifact output should change.

---

## Phase 2 — characterize the current GPR selection contract

Before moving logic, add or strengthen focused tests that describe the current
selection behavior.

The tests should cover the policy currently embedded in the `resolve-gprs`
stage.

### Required cases

1. Existing valid model GPR is retained when external evidence disagrees.
2. Existing model GPR remains preferred over a conflicting external sGPR.
3. External sGPR is selected when the model has no usable GPR.
4. Conservative sGPR conflict resolution remains deterministic.
5. Accepted non-sGPR external evidence can be used when no model GPR or
   resolved sGPR is available.
6. Weak, ambiguous, unresolved, or unsupported candidates are not silently
   promoted.
7. Conflicting candidates remain represented in the evidence output.
8. Selected genes match the selected GPR/sGPR.
9. Derived subunit stoichiometry is preserved when it is unambiguous.
10. Existing configured stoichiometry is preserved where it has precedence.
11. Invalid candidate expressions do not change existing behavior.
12. Candidate ordering does not affect the selected scientific result.

The objective is not to test private implementation details.

The tests should establish the observable contract that must remain true after
extraction.

---

## Phase 3 — extract one pure GPR selection boundary

### 1. Create a domain-level selection module

Add:

```text
src/thg_protocol/gpr/selection.py
```

Do not place the new logic under `workflow/beta2` unless it depends on workflow
objects.

The extracted code must not depend on:

- `StageContext`;
- `StageResult`;
- dependency artifact paths;
- workflow configuration objects;
- run directories;
- manifest mutation;
- filesystem writes.

### 2. Move selection policy, not orchestration

Extract the smallest coherent policy currently implemented inside
`DetailedBeta2Stage.run()`.

The new API should conceptually represent:

```python
selection = select_reaction_gpr(
    model_gpr=...,
    model_genes=...,
    evidence=...,
    configured_stoichiometry=...,
)
```

The exact signature may differ, but inputs and outputs should be ordinary Python
values or small immutable data objects.

A result object may contain fields such as:

```text
gpr
genes
selected_source
status
conflicts
subunit_stoichiometry
sgpr
sgpr_structure
```

Only include fields that correspond to behavior already produced by the current
stage.

Do not introduce a generalized workflow result abstraction.

### 3. Move `_accepted_external_gpr` if it is part of the same policy

If `_accepted_external_gpr` is only used to decide whether evidence is eligible
for GPR selection, move it into the new domain module as a private helper.

If it has another workflow-specific responsibility, leave it in `_stages.py`.

### 4. Reuse existing GPR APIs

The selection implementation should continue to rely on existing APIs such as:

```text
thg_protocol.gpr.merge
thg_protocol.gpr.stoichiometry
thg_protocol.gpr evidence structures
```

Do not duplicate parsing, canonicalization, merging, or sGPR normalization
logic.

### 5. Keep serialization in the stage

`selection.py` should return data.

`_stages.py` should remain responsible for writing:

- GPR stage artifacts;
- evidence reports;
- checkpoints;
- metadata;
- provenance;
- `StageResult`.

This keeps the scientific decision layer independent from the workflow runtime.

---

## Phase 4 — simplify the `resolve-gprs` stage

After extraction, reduce the `resolve-gprs` branch in
`DetailedBeta2Stage.run()` to orchestration.

The branch should approximately do the following:

```text
1. Load model.
2. Load collected GPR evidence.
3. Load configured stoichiometry.
4. Build per-reaction selection inputs.
5. Call the pure GPR selection function.
6. Apply the selected GPR to the model.
7. Assemble the existing evidence/artifact payload.
8. Write artifacts.
9. Return StageResult.
```

Avoid changing surrounding β2 stages as part of this phase.

### Explicit non-goals

Do not simultaneously refactor:

- `collect-gpr-evidence`;
- service clients;
- Rhea lookup;
- UniProt lookup;
- Reactome lookup;
- location resolution;
- compartment normalization;
- expansion planning;
- model export.

Those can be evaluated independently later.

---

## Phase 5 — protect workflow contracts

Add or retain tests that ensure the structural refactor has not changed the β2
workflow contract.

Verify:

- `DETAILED_BETA2_STAGE_IDS` is unchanged.
- Stage order is unchanged.
- Stage dependencies are unchanged.
- Registered workflow ID remains `beta2`.
- Artifact roles remain unchanged.
- Artifact schema versions remain unchanged.
- Resume behavior remains unchanged.
- Fingerprints remain semantically equivalent.
- Snapshot replay still produces the expected result.
- Existing configuration files continue to load without migration.

Where practical, compare artifact payloads before and after the refactor rather
than only asserting that stages complete successfully.

---

## Phase 6 — reassess location resolution

Do not automatically extract location code after finishing the GPR work.

Review the following after the GPR refactor:

- `_resolve_location_payload`;
- `collect-location-evidence`;
- `collect-reaction-location-evidence`;
- `resolve-compartment-evidence`;
- `infer-complex-and-isoenzyme-locations`.

Extract a location helper only if at least one of these conditions is true:

1. a new location feature would add another substantial branch to
   `_stages.py`;
2. the decision policy cannot be tested without constructing workflow state;
3. the same scientific decision logic is needed outside the β2 workflow;
4. changing the logic requires modifying unrelated stage code;
5. regressions are difficult to isolate with existing tests.

If none apply, leave the location path in place.

---

## Phase 7 — β1 curation policy

Do not split:

```text
src/thg_protocol/curation/beta1.py
```

solely because it is large.

Unlike β2 `_stages.py`, this module contains a broad public domain API and
splitting it unnecessarily would create import and compatibility churn.

Use targeted extraction when an actual maintenance seam appears.

A β1 extraction is justified when:

- a responsibility has a clear independent domain concept;
- a change requires touching unrelated sections of the module;
- the logic benefits from independent focused tests;
- the extracted function can remain free of workflow/runtime dependencies;
- existing public imports can remain stable through re-exporting.

If extraction occurs, preserve the current API through:

```text
thg_protocol.curation
```

and any currently supported direct imports.

Do not reorganize the β1 public API as part of structural cleanup.

---

## Phase 8 — clarify repository-level data layout

The package structure itself should not be reorganized further as part of this
work.

Instead, update the repository layout documentation to distinguish maintained
software/workspace directories from preserved research artifacts.

Document approximately:

```text
Maintained software and workspace
---------------------------------
src/                 Installable package.
tests/               Unit, integration, characterization, and docs tests.
docs/                User and contributor documentation.
configs/             Version-controlled workflow configurations.
inputs/              Caller-owned read-only workflow inputs.
runs/                Generated resumable workflow runs.

Preserved research/reference corpus
-----------------------------------
models/              Canonical and historical model artifacts.
files/               Retained research inputs/intermediate artifacts.
supplementary_material/
                     Publication and supporting research material.
```

Do not move canonical research artifacts merely to make the repository root
look smaller.

Historical and provenance-sensitive paths should remain stable unless there is
a separate artifact-migration plan.

---

## Commit sequence

Prefer a sequence similar to:

### Commit 1 — dead-code cleanup

```text
Remove unused β2 GPR payload helper
```

Changes:

- delete `_resolve_gpr_payload`;
- no behavior changes.

### Commit 2 — characterize selection policy

```text
Add regression coverage for β2 GPR selection
```

Changes:

- add focused tests for current model/evidence precedence;
- add conflict and stoichiometry cases;
- no production behavior changes.

### Commit 3 — extract GPR selection

```text
Extract β2 GPR selection policy
```

Changes:

- add `thg_protocol/gpr/selection.py`;
- move pure selection policy;
- keep stage artifact generation unchanged;
- update focused unit tests.

### Commit 4 — simplify stage orchestration

```text
Simplify β2 resolve-gprs stage orchestration
```

Changes:

- replace inline policy with domain call;
- remove obsolete local helpers/imports;
- preserve stage output exactly.

### Commit 5 — docs and structural closeout

```text
Document simplified workflow and repository boundaries
```

Changes:

- update architecture/repository-layout documentation;
- record validation results;
- update this plan with completion status.

Do not combine unrelated scientific changes into these commits.

---

## Verification gates

### Focused gate

Run tests covering:

```text
GPR parsing
sGPR normalization
GPR evidence merging
β2 curation
β2 evidence
β2 registered workflow
β2 snapshot replay
```

### Full local gate

Run the complete offline suite.

Expected checks include:

```bash
pytest
ruff check src tests
python -m compileall src
python -m build
mkdocs build --strict
```

Also run the project's existing artifact-integrity and CLI smoke checks.

### Package gate

Build both source and wheel distributions and install them outside the source
checkout.

Verify:

```text
import thg_protocol
import thg_protocol.gpr
import thg_protocol.curation
import thg_protocol.workflow
```

Verify installed commands:

```bash
thg-run --help
thg-gapfill --help
thg-pathway --help
thg-compare --help
```

### Hosted gate

Run the maintained Python 3.10–3.12 CI matrix on the final refactor commit.

---

## Behavioral comparison

For representative β2 fixtures, compare the before/after outputs for:

- selected GPR;
- selected sGPR;
- gene lists;
- subunit stoichiometry;
- conflict records;
- evidence provenance;
- checkpoint content;
- model reaction GPRs;
- exported model signature;
- artifact roles;
- schema versions;
- stage metadata.

Differences should be zero unless explicitly documented as serialization-only
differences that do not affect the existing artifact contract.

If an unexpected scientific difference appears, stop the structural refactor
and treat the discrepancy as a separate behavior change.

---

## Extraction rule for future work

Do not use file size as the extraction trigger.

Extract when a responsibility has a clear boundary and at least one concrete
maintenance problem exists.

Good extraction candidates are:

- independently testable scientific decisions;
- logic reused by multiple workflows;
- policy currently mixed with filesystem/runtime orchestration;
- code where a new feature would add another branch to an already complex
  dispatcher.

Poor extraction candidates are:

- tiny helpers used once;
- wrappers created only to shorten a file;
- abstractions with no second caller;
- generic stage frameworks;
- modules whose only purpose is renaming existing functions.

---

## Do not do yet

- Do not create one Python file per β2 stage.
- Do not replace `DetailedBeta2Stage` with a new stage-class hierarchy.
- Do not introduce dependency injection beyond existing service boundaries.
- Do not move workflow-specific serialization into the GPR domain package.
- Do not split `curation/beta1.py` by category merely to reduce line count.
- Do not rename stage IDs.
- Do not change workflow IDs.
- Do not change configuration schemas.
- Do not change artifact schemas.
- Do not reorganize preserved research data.
- Do not mix scientific behavior changes into the structural refactor.

---

## Completion criteria

The structural simplification is complete when:

- `_resolve_gpr_payload` is removed.
- β2 GPR model-vs-evidence selection is independently testable without
  `StageContext`.
- The selection policy lives in the existing GPR domain layer.
- `DetailedBeta2Stage` remains the workflow orchestration boundary.
- The `resolve-gprs` branch contains materially less scientific decision logic.
- β2 stage IDs and dependencies are unchanged.
- Public package APIs are unchanged.
- Artifact schemas and provenance are unchanged.
- Focused regression tests cover selection precedence and conflicts.
- The full offline test suite passes.
- Ruff passes.
- Package build passes.
- Strict documentation build passes.
- Artifact integrity checks pass.
- Clean source/wheel installation passes.
- The Python 3.10–3.12 hosted matrix passes.
- Repository documentation clearly distinguishes maintained workspace
  directories from preserved research/reference artifacts.

After these criteria are met, reassess `_stages.py`.

Do not schedule another structural split unless the remaining module continues
to create a concrete maintenance problem.

## Implementation status

The targeted β2 GPR simplification is implemented locally:

- `_resolve_gpr_payload` and the inline GPR selection policy were removed from
  `_stages.py`.
- `thg_protocol.gpr.selection` now owns pure model/evidence selection,
  deterministic conflict handling, and stoichiometry derivation.
- Stage wiring, artifact assembly, public imports, and repository layout
  boundaries remain stable.
- The offline suite, Ruff, compileall, strict MkDocs, offline package build,
  clean wheel installation, package imports, and CLI help checks pass.

The Python 3.10–3.12 hosted matrix remains a CI gate and is not runnable from
this offline environment.
