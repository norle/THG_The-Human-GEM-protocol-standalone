# Structural simplification plan

## Goal

Reduce the maintenance cost of the largest workflow modules without changing
scientific behavior or introducing a new framework.

The current pressure points are:

- `src/thg_protocol/workflow/beta2/_stages.py` — stage definitions, evidence
  handling, resolution, mutation, and serialization in one module.
- `src/thg_protocol/curation/beta1.py` — curation rules and supporting helpers
  in one large module.
- `src/thg_protocol/workflow/_foundation.py` — older stage wrappers that may be
  compatibility scaffolding rather than active registry dependencies.

## Constraints

- Preserve the public package APIs and registered workflow IDs.
- Preserve artifact schemas, manifests, and provenance fields.
- Keep the runtime layer independent from workflow/domain code.
- Avoid a broad rewrite before a concrete maintenance problem requires it.

## Possible solutions

### Option A — targeted extraction (recommended)

Extract only the actively changing β2 GPR path:

1. Move `_accepted_external_gpr`, GPR payload resolution, and sGPR selection
   into a small `workflow/beta2/gpr_resolution.py` module.
2. Keep `DetailedBeta2Stage` as the orchestration boundary.
3. Add focused tests for conservative conflict selection and evidence output.
4. Repeat for location resolution only if its code becomes difficult to change.

Benefits: smallest diff, low regression risk, and immediate relief in the area
currently receiving feature work.

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

### Option C — delete compatibility scaffolding first

Trace the wrappers in `_foundation.py` and related exports. If no registry,
public API, or test uses them, delete them and their tests; otherwise mark the
remaining compatibility boundary explicitly.

Benefits: immediate deletion and less misleading architecture.

Cost: removal is unsafe until every caller is checked, especially downstream
users importing historical names.

## Recommended sequence

1. Run a repository-wide reference search for the `_foundation.py` classes and
   exports.
2. If unused, remove only the dead wrappers and update the architecture docs.
3. Extract the β2 GPR path using Option A.
4. Run the full offline test suite and strict docs build.
5. Reassess whether the remaining large modules still slow down real work.

## Do not do yet

- Do not introduce a generic stage framework.
- Do not split every large file by line count alone.
- Do not change artifact schemas or public workflow IDs as part of this cleanup.

## Completion criteria

- No public import or registered workflow changes unexpectedly.
- The β2 stage registry remains readable and behaviorally identical.
- Focused tests cover each extracted responsibility.
- Full tests, Ruff, package build, and strict docs build pass.
