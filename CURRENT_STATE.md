# THG Protocol Refactoring: Current State

Last reviewed: 2026-08-05

This document is the concise operational snapshot for the refactoring described
in `docs/plans/REFACTORING_PLAN.md`, with closeout requirements in
`docs/plans/REFACTORING_PLAN_NEXT.md`. It replaces the chronological progress diary.
Update it when implementation status, validation evidence, blockers, or the
next reviewable work changes. Git history remains the source for detailed
historical implementation notes.

## Overall Assessment

The package migration and legacy-directory closeout are implemented. All 15
legacy checkout directories and their 82 Python files are absent; maintained
tests use package APIs, and preserved artifacts have canonical destinations.
Local release validation is complete; the only release gate not evidenced from
the current checkout is a hosted current-head Python 3.10–3.12 matrix run.

The legacy-parity remediation baseline is maintained separately from the
refactoring closeout. The capability registry records implementation,
verification, workflow coverage, legacy relationship, and publication
reproduction independently. No legacy source commit or frozen publication
artifact is available in this checkout, so parity and exact reproduction
remain unverified.

## Repository Snapshot

- Branch: `refactoring-cleanup`
- Reviewed commit: `0c91fdec` (`fix: chagned contirbuting md`)
- Working tree at review: one intentional supplementary-notebook migration is
  pending; no legacy source or artifact directories are present
- Logical closeout commits: `c8f85a3` (documentation and artifact ownership),
  `77634e6` (maintained test migration), and `dc32a9e` (legacy implementation
  removal and artifact relocation), followed by `2626038` (canonical artifact
  tracking and closeout documentation)
- Package layout: `src/thg_protocol`
- Installed commands: `thg-gapfill`, `thg-pathway`, `thg-compare`, and `thg-run`
- Supported Python range currently declared: `>=3.10,<3.13`
- Canonical large artifacts: seven targeted Git LFS paths
- Legacy checkout namespaces: removed; not shipped in wheels

## Implemented

- Setuptools packaging, dependency extras, central pytest markers, Ruff/Black
  configuration, MkDocs documentation, and a `src/` layout.
- Python 3.10–3.12 CI with lint, default offline tests, source/wheel builds,
  outside-checkout imports, and installed CLI help checks. The package matrix
  uses `fail-fast: false` so every supported interpreter reports its result.
- Package APIs and compatibility boundaries for annotation, GPR parsing and
  lookup, pathway implementation, gapfill, comparison, model reconstruction,
  model building, merge primitives, network analysis, figures, cell-specific
  helpers, model I/O, and formula-level mass balance.
- Dependency-free mass-balance numerics and positive equation balancing live in
  `thg_protocol.model_build.mass_balance`.
- Merge, consistency, network, visualization, annotation, database, pathway,
  and cell-specific workflows are owned by package APIs.
- Promoted metabolite annotation now uses the package PubChem client for both
  injected and default lookups without importing PubChemPy or mutating global
  proxy state.
- Injectable clients and static test adapters for PubChem, Ensembl, BioCyc,
  KEGG, and location-page operations.
- Explicit input/output paths for maintained CLIs and package workflows.
- Promoted metabolite annotation APIs require explicit input/output paths.
- Targeted Git LFS migration and generated-artifact index cleanup.
- Workflow, installation, development, artifact, dependency, and release
  documentation.
- Complete legacy Python inventory and final removal manifest in
  `docs/legacy-api-inventory.md` for all 82 former source-checkout files.
- Contract groups for legacy parity, intentional migration differences, and
  archived workflow ownership in `docs/api-contracts.md` and
  `docs/legacy-workflows.md`.
- Canonical pathway inputs/configuration are tracked under `files/pathway/`;
  the large input uses the relocated LFS path and is no longer hidden by the
  repository-wide `files/` ignore rule.
- Executable `tests/unit/test_legacy_import_policy.py` gate asserting package
  import boundaries and absence of all 15 legacy directories.
- Package-owned export checks and relocated characterization fixtures under
  `tests/`.
- Supplementary boundary-summary notebook imports now use
  `thg_protocol.merge`; it no longer presents the removed `functions` namespace
  as an available example dependency.
- Capability evidence is recorded in
  [`docs/protocol/capability-evidence.json`](docs/protocol/capability-evidence.json)
  and rendered in the [capability and evidence status matrix](docs/protocol/implementation-status.md).
  Complete beta1/beta2 construction, live harvesting, publication-compatible
  merge, and exact final-artifact reproduction remain Not implemented or Not
  yet verified.
- The resumable v1 DAG is represented in the API inventories and wheel/CI smoke
  checks, including the installed `thg-run` command.

## Validation Evidence

The strongest recorded model-backed checkpoint ran from committed tree
`37359ef` in a Python 3.12 environment with GLPK:

- `1827 passed, 1 skipped`
- The skip was the credential-gated online GPR fixture.
- Package imports and all four installed CLI `--help` checks passed from
  outside the checkout.

Later dependency-free checks on the current refactoring line recorded:

- Editable package installation without dependency resolution.
- `47 passed` for the dependency-free characterization/API subset.
- Direct import, compilation, CLI-help, and static-client checks for subsequent
  workflow-boundary changes.

- `ruff check src tests`: clean on 2026-07-31.
- Default offline suite: `1858 passed, 2 skipped` on Python 3.12 with the
  pinned GLPK constraints.
- Pre-removal checkout closeout gate: `1880 passed, 2 skipped` under Python 3.12,
  with the exact inventory manifest, maintained-import, compatibility-export,
  deterministic adapter, and CLI contract checks included; Ruff is clean for
  `src tests`.
- The pre-removal package checkout passed the complete default suite under the
  available Python 3.10.12 environment: `1880 passed, 2 skipped`.
- The installed-command compatibility checks pass for the legacy CLI
  option/help contract under Python 3.10 and 3.12.
- The focused inventory, compatibility-export, deterministic-adapter, CLI, and
  CI-policy gates pass: `22 passed` under both Python 3.10.12 and Python 3.12.9.
- No-isolation `python -m build` completed successfully on the current
  checkout; the rebuilt wheel passed outside-checkout imports and all four
  installed CLI help checks.
- Unit/integration gates passed: `127 passed, 1 skipped` for the unit and
  characterization paths, and `1848 passed, 2 skipped` for unit plus
  integration tests. Python 3.10 and 3.11 constraint dry-runs resolved.
- `python -m build`: source distribution and wheel built successfully.
- Current checkout default suite: `1838 passed, 2 skipped` under Python 3.12
  after legacy-directory removal; the skips are optional online and figures
  dependencies.
- Current checkout removal policy and package export gates: `19 passed`.
- The exact default offline command from the CI failure report passes after
  the artifact-tracking fix: `1838 passed, 2 skipped` under Python 3.12.
- Current audit rerun of the exact default offline gate passes: `1843 passed,
  2 skipped` under Python 3.12. Ruff, bytecode compilation, the legacy-closure
  policy tests, and the four installed CLI help checks also pass. The closure
  policy covers maintained Python/notebook sources, documentation snippets,
  canonical artifact tracking, and package imports.
- A fresh isolated `python -m build` completed successfully, and the resulting
  wheel installed outside the checkout, imported all supported package areas,
  and passed `thg-gapfill`, `thg-compare`, `thg-pathway`, and `thg-run --help`
  smoke tests.
- The focused legacy-closure and CI-policy gates pass: `9 passed`; Ruff is
  clean for `src tests`.
- `git lfs fsck` passes with all seven approved objects, including the
  relocated `files/pathway/inputs/endoA_250917_3.json` path. The rebuilt wheel
  installs outside the checkout and all four installed CLI `--help` checks
  pass.
- A no-dependency wheel installed outside the checkout imported all package
  areas and passed all four installed CLI `--help` smoke tests.
- Python 3.10 dependency installation completed in `/tmp/thg-py310-venv` using
  the project constraints; `thg_protocol` and `cobra` import successfully.
- Python 3.10 exact editable install (`pip install -c
  constraints/py310-glpk.txt -e ".[dev]"`) passed on 2026-07-31, followed by
  Ruff and the complete default offline suite: `1858 passed, 2 skipped`.
- Python 3.10 source distribution and wheel builds passed on 2026-07-31.
  The no-dependency wheel installed outside the checkout and passed package,
  workflow, database/model-build, merge, cell-specific, and all four CLI help
  smoke checks; the rebuilt wheel also exposes the explicit annotation-path
  signatures.
- Git LFS verification passed: all seven approved LFS files are present,
  `git lfs fsck` is clean, and a fresh local clone checked out all seven files
  with content matching the source tree.
- GitHub Actions run `30340915763` passed all three package jobs (Python 3.10,
  3.11, and 3.12). The newer run `30545574823` tested remote commit `13c6066`
  and failed its Python 3.11 job on the legacy COBRA group-member shape; that
  compatibility fix is present in current commit `d21cf04` and passes the
  current Python 3.10 suite. A current-head CI rerun is still required.
- The latest reported Python 3.10 failure was caused by the migrated pathway
  directories being ignored and therefore absent from a clean checkout. The
  canonical files are now tracked and the LFS attribute points to their new
  path; rerun the hosted matrix on the resulting head.

## Phase Status

| Phase | Status | Remaining gate |
| --- | --- | --- |
| 0. Baseline and decisions | Complete | None. Artifact ownership and the source-only legacy namespace policy are recorded. |
| 1. Packaging and tooling | Complete | None. Packaging, CI, wheel, and outside-checkout gates have recorded passing checkpoints. |
| 2. Pure utility migration | Complete | None. Legacy utility namespaces are removed. |
| 3. Workflow APIs and entry points | Complete | None. Archived workflows are removed and replacements are documented. |
| 4. Integration and CLI tests | Complete | None. Central package contracts own maintained behavior. |
| 5. External service hardening | Complete | Keep the client-boundary rule for any newly migrated workflow. |
| 6. Artifacts and Git LFS | Complete | Verify the seven LFS objects when publishing or cloning from a new remote. |
| 7. Documentation and CI expansion | In progress | Run the supported matrix on the current head; local package and wheel gates pass. |

## Important Remaining Gaps

### 1. Behavior preservation and deprecation

Former deferred workflows now have package replacements or explicit retirement
decisions documented in
[`docs/legacy-workflows.md`](docs/legacy-workflows.md).

Formula balancing, merge, structural consistency, network reports, and live
service boundaries are package-owned. Historical fixture data is retained only
under canonical artifact paths.

### 2. Remaining legacy coupling

Solver-heavy cell-specific and pathway diagnostic scripts were retired; their
package replacements and unsupported status are recorded in
`docs/legacy-workflows.md`.

### 3. Historical test ownership

Pytest collects `tests/`; representative historical inputs were relocated to
`tests/fixtures`, and duplicate historical Python suites were removed.

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

The current promoted API set is covered by the `C1`–`C9` contract groups in
`docs/api-contracts.md`; new promotions must extend the corresponding group and
inventory evidence.

### 5. Release decisions

- Python 3.10 now has the exact editable-install, Ruff, default offline-suite,
  build, and outside-wheel evidence recorded above.
- The system `python3.10` interpreter is present, but its current environment
  has no pytest; the current-head 3.10 result therefore remains a hosted CI
  gate rather than a local rerun.
- Python 3.11 is not installed locally; its matching current-head CI job is the
  remaining evidence source. The branch has not published the closeout changes.
- The clean-clone release gate against the approved Python 3.10–3.12
  constraints and all seven LFS checks passed locally.

## Next Reviewable Pull Requests

1. Run the CI package matrix on the current `refactoring-cleanup` head and
   record the Python 3.10–3.12 results.
2. If the matrix is green, update this snapshot with the current-head result
   and mark Phase 7 complete.
3. Keep the credential-gated BioCyc fixture opt-in; it does not replace the
   offline release gate.

The credential-gated BioCyc fixture should be run when credentials are
available, but it does not replace the work above and should not block offline
refactoring progress.

## Completion Criteria

The refactor is complete when the definition of done in
`docs/plans/REFACTORING_PLAN_NEXT.md` (and the carried-forward requirements from
`docs/plans/REFACTORING_PLAN.md`) passes and:

- No maintained workflow silently loses historical behavior.
- Every intentionally removed behavior has an approved and documented
  deprecation/removal decision.
- Former legacy scripts and historical suites are removed.
- The central test suite owns all maintained behavior.
- A clean clone passes the supported release matrix and LFS verification.
