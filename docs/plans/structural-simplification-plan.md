# Structural simplification plan

## Goal

Reduce the maintenance cost of the largest workflow modules without changing
scientific behavior or introducing a new framework.

The current pressure points are:

- `src/thg_protocol/workflow/beta2/_stages.py` — stage definitions, evidence
  handling, resolution, mutation, and serialization in one module.
- `src/thg_protocol/curation/beta1.py` — curation rules and supporting helpers
  in one large module.

## Constraints

- Preserve the public package APIs and registered workflow IDs.
- Preserve artifact schemas, manifests, and provenance fields.
- Keep the runtime layer independent from workflow/domain code.
- Avoid a broad rewrite before a concrete maintenance problem requires it.

## Possible solutions

### Option A — targeted extraction (recommended)

Simplify only the actively changing β2 GPR path:

1. Delete the unused `_resolve_gpr_payload` helper.
2. Keep GPR selection in `DetailedBeta2Stage`, using the existing
   `thg_protocol.gpr` APIs.
3. Extract one pure selection helper only when the next GPR change needs
   independent tests or would otherwise add another branch to the stage.
4. Repeat for location resolution only if its code becomes difficult to change.

Benefits: smallest diff, low regression risk, and no new module before it is
needed.

Cost: `_stages.py` remains large and will still contain unrelated operations.

### Option B — split β2 by responsibility

Split the stage implementation into modules for:

- evidence collection;
- GPR and location resolution;
- expansion planning and decisions;
- model mutation and export.

Keep one thin stage registry that wires those functions together.

Benefits: clearer ownership and smaller test surfaces.

Cost: more file movement, more import/API churn, and a larger regression
surface. Use only if Option A does not make the next changes simpler.

### β1 curation

Do not split `curation/beta1.py` on size alone. When a change there becomes
hard to isolate, extract only the helper required by that change and add a
focused regression test.

## Recommended sequence

1. Delete `_resolve_gpr_payload` and run the affected β2 tests.
2. Keep the β2 GPR path in place unless the next change meets Option A's
   extraction trigger.
3. Apply the same rule to β1 curation when it next changes.
4. Run the full offline test suite and strict docs build for any extraction.
5. Reassess whether the remaining large modules still slow down real work.

## Do not do yet

- Do not introduce a generic stage framework.
- Do not split every large file by line count alone.
- Do not change artifact schemas or public workflow IDs as part of this cleanup.

## Completion criteria

- No public import or registered workflow changes unexpectedly.
- The β2 stage registry remains readable and behaviorally identical.
- Focused regression tests cover each changed responsibility.
- Full tests, Ruff, package build, and strict docs build pass.
