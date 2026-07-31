# THG Protocol Refactoring: Current State

Last reviewed: 2026-07-31

This document is the concise operational snapshot for the refactoring described
in `REFACTORING_PLAN.md`. It replaces the chronological progress diary. Update
it when implementation status, validation evidence, blockers, or the next
reviewable work changes. Git history remains the source for detailed historical
implementation notes.

## Overall Assessment

The refactor remains feasible and is architecturally sound. Packaging, service
boundaries, CI, Git LFS ownership, installed workflows, and explicit legacy
behavior decisions are in place. The remaining work is release hardening and
historical-test ownership rather than an architectural rewrite.

## Repository Snapshot

- Branch: `refactoring-cleanup`
- Reviewed commit: `1141e78` (`refactor: complete legacy compatibility boundaries`)
- Working tree at review: clean
- Package layout: `src/thg_protocol`
- Installed commands: `thg-gapfill`, `thg-pathway`, and `thg-compare`
- Supported Python range currently declared: `>=3.10,<3.13`
- Canonical large artifacts: seven targeted Git LFS paths
- Legacy `functions` namespace: source-checkout compatibility only; not shipped
  in wheels

## Implemented

- Setuptools packaging, dependency extras, central pytest markers, Ruff/Black
  configuration, MkDocs documentation, and a `src/` layout.
- Python 3.10–3.12 CI with lint, default offline tests, source/wheel builds,
  outside-checkout imports, and installed CLI help checks.
- Package APIs and compatibility boundaries for annotation, GPR parsing and
  lookup, pathway implementation, gapfill, comparison, model reconstruction,
  model building, merge primitives, network analysis, figures, cell-specific
  helpers, model I/O, and formula-level mass balance.
- Dependency-free legacy mass-balance numerics and positive equation balancing
  now live in `thg_protocol.model_build.mass_balance` and are re-exported by
  the legacy adapter.
- Legacy merge, consistency, network-cleanup, and visualization options now
  delegate to package APIs or require explicit output paths; their supported
  scope is recorded in `docs/legacy-workflows.md`.
- Promoted metabolite annotation now uses the package PubChem client for both
  injected and default lookups without importing PubChemPy or mutating global
  proxy state.
- Injectable clients and static test adapters for PubChem, Ensembl, BioCyc,
  KEGG, and location-page operations.
- Explicit input/output paths for the maintained CLIs and many legacy entry
  points.
- Targeted Git LFS migration and generated-artifact index cleanup.
- Workflow, installation, development, artifact, dependency, and release
  documentation.

## Validation Evidence

The strongest recorded model-backed checkpoint ran from committed tree
`37359ef` in a Python 3.12 environment with GLPK:

- `1827 passed, 1 skipped`
- The skip was the credential-gated online GPR fixture.
- Package imports and all three installed CLI `--help` checks passed from
  outside the checkout.

Later dependency-free checks on the current refactoring line recorded:

- Editable package installation without dependency resolution.
- `47 passed` for the dependency-free characterization/API subset.
- Direct import, compilation, CLI-help, and static-client checks for subsequent
  workflow-boundary changes.

- `ruff check src tests`: clean on 2026-07-31.
- Default offline suite: `1858 passed, 2 skipped` on Python 3.12 with the
  pinned GLPK constraints.
- Unit/integration gates passed: `127 passed, 1 skipped` for the unit and
  characterization paths, and `1848 passed, 2 skipped` for unit plus
  integration tests. Python 3.10 and 3.11 constraint dry-runs resolved.
- `python -m build`: source distribution and wheel built successfully.
- A no-dependency wheel installed outside the checkout imported all package
  areas and passed all three installed CLI `--help` smoke tests.

## Phase Status

| Phase | Status | Remaining gate |
| --- | --- | --- |
| 0. Baseline and decisions | Complete | None. Artifact ownership and the source-only legacy namespace policy are recorded. |
| 1. Packaging and tooling | Complete | None. Packaging, CI, wheel, and outside-checkout gates have recorded passing checkpoints. |
| 2. Pure utility migration | Complete | None. Remaining `functions` imports are explicit compatibility tests. |
| 3. Workflow APIs and entry points | Complete | None. Archived workflow status and replacements are documented. |
| 4. Integration and CLI tests | Complete | None. Central adapter contracts and historical-suite ownership are documented. |
| 5. External service hardening | Complete | Keep the client-boundary rule for any newly migrated workflow. |
| 6. Artifacts and Git LFS | Complete | Verify the seven LFS objects when publishing or cloning from a new remote. |
| 7. Documentation and CI expansion | In progress | Run the final clean-clone release gate against the approved matrix. |

## Important Remaining Gaps

### 1. Behavior preservation and deprecation

The former unconditional deferred errors have been replaced with package-backed
compatibility adapters. Their exact scope and the explicitly archived
solver-heavy workflows are documented in
[`docs/legacy-workflows.md`](docs/legacy-workflows.md).

The adapters cover formula balancing, multi-stage merge names, structural and
solver-backed consistency checks, and explicit network cleanup/reporting. Live
database harvesting remains an opt-in online workflow behind injected clients.
Adapter contracts are covered by
`tests/unit/test_legacy_compatibility_boundaries.py`; historical suites are
explicitly archived in `docs/legacy-workflows.md`.

### 2. Remaining legacy coupling

The remaining solver-heavy cell-specific and pathway diagnostic scripts are
explicitly archived/unsupported for installed use; the designation and package
replacements are recorded in `docs/legacy-workflows.md`. Their historical
output conventions remain local workflow behavior and are not part of the
package release contract.

### 3. Historical test ownership

Pytest is configured to collect `tests/`. Historical suites under
`test_algorithms/` and additional MEMOTE tests remain outside the default
collection path. Useful annotation and algorithm fixtures are represented by
central tests; the remaining duplicated suites need a final archive decision.

### 4. Public API contracts

The promoted workflow contracts and package-data decision are documented in
[`docs/api-contracts.md`](docs/api-contracts.md). Remaining work is to keep
those contracts aligned as additional APIs are promoted.

Promoted APIs must consistently document:

- Accepted model and record types.
- Return schemas.
- Whether inputs are mutated.
- Filesystem and network side effects.
- Raised errors and optional dependencies.

### 5. Release decisions

- Run the clean-clone release gate against the approved Python 3.10–3.12
  constraints and verify the seven LFS objects from a fresh clone.

## Next Reviewable Pull Requests

1. Run the clean-clone release gate, including seven Git LFS object checks.

The credential-gated BioCyc fixture should be run when credentials are
available, but it does not replace the work above and should not block offline
refactoring progress.

## Completion Criteria

The refactor is complete when the definition of done in
`REFACTORING_PLAN.md` passes and:

- No maintained workflow silently loses historical behavior.
- Every intentionally removed behavior has an approved and documented
  deprecation/removal decision.
- Remaining legacy scripts are parameterized, thin adapters or explicitly
  archived.
- The central test suite owns all maintained behavior.
- A clean clone passes the supported release matrix and LFS verification.
