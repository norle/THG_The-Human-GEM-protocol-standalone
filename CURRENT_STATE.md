# THG Protocol Refactoring: Current State

Last reviewed: 2026-07-30

This document is the concise operational snapshot for the refactoring described
in `REFACTORING_PLAN.md`. It replaces the chronological progress diary. Update
it when implementation status, validation evidence, blockers, or the next
reviewable work changes. Git history remains the source for detailed historical
implementation notes.

## Overall Assessment

The refactor remains feasible and is architecturally sound. Packaging, service
boundaries, CI, Git LFS ownership, and the first installed workflows are in
place. The project is now closer to stabilization than to an architectural
rewrite.

The refactor is not complete. The main risk is behavioral: several legacy
functions and workflow options have been converted to explicit deferred errors
before equivalent package behavior exists. Import safety has improved, but a
source-compatible name that raises `NotImplementedError` is not a behavioral
compatibility wrapper.

## Repository Snapshot

- Branch: `refactoring-cleanup`
- Reviewed commit: `e7d934c` (`refactor legacy workflow boundaries`)
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
- Dependency-free legacy mass-balance numerics (`inarray`, `eq2mat`, and
  `nullity`) now live in `thg_protocol.model_build.mass_balance` and are
  re-exported by the legacy adapter; solver-backed balancing remains deferred.
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

The current review environment has pytest but does not have the declared
`cobra` base dependency or Ruff. The full default suite therefore stops during
collection with seven `ModuleNotFoundError: cobra` errors, and lint cannot be
rerun here. This is an environment limitation, not a recorded test regression,
but the current commit still needs the full clean-environment gate.

## Phase Status

| Phase | Status | Remaining gate |
| --- | --- | --- |
| 0. Baseline and decisions | Complete | None. Artifact ownership and the source-only legacy namespace policy are recorded. |
| 1. Packaging and tooling | Complete | None. Packaging, CI, wheel, and outside-checkout gates have recorded passing checkpoints. |
| 2. Pure utility migration | In progress | Finish legacy utility decoupling and remove remaining checkout-path mutation. |
| 3. Workflow APIs and entry points | In progress | Preserve, replace, or formally retire every deferred legacy behavior; finish remaining script parameterization. |
| 4. Integration and CLI tests | In progress | Migrate or formally archive historical test suites and add coverage for preserved/deprecated workflow contracts. |
| 5. External service hardening | Complete | Keep the client-boundary rule for any newly migrated workflow. |
| 6. Artifacts and Git LFS | Complete | Verify the seven LFS objects when publishing or cloning from a new remote. |
| 7. Documentation and CI expansion | In progress | Approve the dependency matrix, decide package configuration data, and run the final release gate. |

## Important Remaining Gaps

### 1. Behavior preservation and deprecation

The following surfaces currently expose names or options whose historical
behavior is deferred:

- Solver-backed mass balancing.
- Historical multi-stage merge variants.
- Network cleanup and visualization options.
- Credentialed live database harvesting.
- MEMOTE/solver-backed consistency helpers.

For each surface, choose one of these outcomes:

1. Keep the old implementation available through a lazy compatibility adapter
   until the package replacement is tested.
2. Implement and characterize the package replacement.
3. Approve a breaking removal, document the migration path, emit a deprecation
   period where practical, and remove the misleading compatibility claim.

Do not count an unconditional deferred error as a completed migration.

### 2. Remaining legacy coupling

Some cell-specific scripts still mutate `sys.path` and import `pdb`.
Pathway validation and visualization scripts still contain repository-relative
paths. These scripts need explicit input/output contracts or an explicit
archived/unsupported designation.

### 3. Historical test ownership

Pytest is configured to collect `tests/`. Historical suites under
`test_algorithms/` and additional MEMOTE tests remain outside the default
collection path. Migrate useful characterization cases into `tests/`, mark
large/online/solver cases appropriately, and formally archive duplicated test
helpers.

### 4. Public API contracts

The package contains substantially more public surface than its user-facing
API documentation currently defines. Promoted APIs still need consistent
documentation of:

- Accepted model and record types.
- Return schemas.
- Whether inputs are mutated.
- Filesystem and network side effects.
- Raised errors and optional dependencies.

### 5. Release decisions

- Approve the supported Python/dependency matrix and constraints strategy.
- Decide whether configuration templates or schemas are package data.
- Confirm which deferred legacy behaviors must remain supported for the first
  packaged release.

## Next Reviewable Pull Requests

1. Inventory deferred legacy behavior and classify every item as preserve,
   replace, deprecate, or remove. Restore lazy access where continued
   compatibility is required.
2. Finish explicit-path/import-safe conversion of the remaining cell-specific
   and pathway scripts, or mark them as archived with documented replacements.
3. Migrate the remaining valuable `test_algorithms/` and MEMOTE fixtures into
   the central marked test structure.
4. Complete public API contracts and approve the dependency matrix and package
   data decision.
5. Run the clean-clone release gate: install declared dependencies, run Ruff
   and the full default suite, build the wheel, test it outside the checkout,
   verify CLI help, and verify all seven Git LFS objects.

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
