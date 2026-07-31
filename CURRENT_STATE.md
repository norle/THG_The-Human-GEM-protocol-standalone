# THG Protocol Refactoring: Current State

Last reviewed: 2026-07-31

This document is the concise operational snapshot for the refactoring described
in `REFACTORING_PLAN.md`, with closeout requirements in
`REFACTORING_PLAN_NEXT.md`. It replaces the chronological progress diary.
Update it when implementation status, validation evidence, blockers, or the
next reviewable work changes. Git history remains the source for detailed
historical implementation notes.

## Overall Assessment

The refactor remains feasible and is architecturally sound. Packaging, service
boundaries, CI, Git LFS ownership, installed workflows, and explicit legacy
behavior decisions are in place. The legacy inventory, contract groups,
archival ownership, and maintained-import policy are now recorded. Local
release validation is complete; the only release gate not evidenced from the
current checkout is a current-head CI rerun for the supported matrix.

## Repository Snapshot

- Branch: `refactoring-cleanup`
- Reviewed commit: `4ce9977` (`docs: record matrix execution policy`)
- Working tree at review: closeout inventory/contract changes are in progress
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
  outside-checkout imports, and installed CLI help checks. The package matrix
  uses `fail-fast: false` so every supported interpreter reports its result.
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
- Promoted metabolite annotation APIs now require explicit input/output paths;
  the source-checkout compatibility wrapper retains the historical default
  path and is covered by a dedicated contract test.
- Targeted Git LFS migration and generated-artifact index cleanup.
- Workflow, installation, development, artifact, dependency, and release
  documentation.
- Complete legacy Python inventory in `docs/legacy-api-inventory.md`, including
  exact paths, symbols, package replacements, status, evidence, consumers, and
  removal conditions for all 82 source-checkout files.
- Contract groups for legacy parity, intentional migration differences, and
  archived workflow ownership in `docs/api-contracts.md` and
  `docs/legacy-workflows.md`.
- Executable `tests/unit/test_legacy_import_policy.py` gate preventing package
  imports from legacy namespaces and checking inventory coverage.
- Dedicated `tests/unit/test_legacy_compatibility_exports.py` parity checks for
  package-owned re-export symbols, plus executable archived-workflow docstring
  status checks.

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
- Current checkout closeout gate: `1880 passed, 2 skipped` under Python 3.12,
  with the exact inventory manifest, maintained-import, compatibility-export,
  deterministic adapter, and CLI contract checks included; Ruff is clean for
  `src tests`.
- The same current checkout passed the complete default suite under the
  available Python 3.10.12 environment: `1880 passed, 2 skipped`.
- The three installed-command compatibility checks pass for the legacy CLI
  option/help contract under Python 3.10 and 3.12.
- The focused inventory, compatibility-export, deterministic-adapter, CLI, and
  CI-policy gates pass: `22 passed` under both Python 3.10.12 and Python 3.12.9.
- No-isolation `python -m build` completed successfully on the current
  checkout; the rebuilt wheel passed outside-checkout imports and all three
  installed CLI help checks.
- Unit/integration gates passed: `127 passed, 1 skipped` for the unit and
  characterization paths, and `1848 passed, 2 skipped` for unit plus
  integration tests. Python 3.10 and 3.11 constraint dry-runs resolved.
- `python -m build`: source distribution and wheel built successfully.
- A no-dependency wheel installed outside the checkout imported all package
  areas and passed all three installed CLI `--help` smoke tests.
- Python 3.10 dependency installation completed in `/tmp/thg-py310-venv` using
  the project constraints; `thg_protocol` and `cobra` import successfully.
- Python 3.10 exact editable install (`pip install -c
  constraints/py310-glpk.txt -e ".[dev]"`) passed on 2026-07-31, followed by
  Ruff and the complete default offline suite: `1858 passed, 2 skipped`.
- Python 3.10 source distribution and wheel builds passed on 2026-07-31.
  The no-dependency wheel installed outside the checkout and passed package,
  workflow, database/model-build, merge, cell-specific, and all three CLI help
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
| 7. Documentation and CI expansion | In progress | Run the supported matrix on the current head; local Python 3.10, prior Python 3.11/3.12 CI, wheel, and clean-clone/LFS gates pass. |

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
central tests. The remaining suites are explicitly archived under THG
maintainer ownership with opt-in commands in `docs/legacy-workflows.md`.

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
- Python 3.11 is not installed locally; its matching current-head CI job is the
  remaining evidence source. No GitHub Actions run is associated with local
  `HEAD` `4ce9977`; the branch has not published the closeout changes. The
  prior all-version success and current local regression coverage are recorded
  above.
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
`REFACTORING_PLAN_NEXT.md` (and the carried-forward requirements from
`REFACTORING_PLAN.md`) passes and:

- No maintained workflow silently loses historical behavior.
- Every intentionally removed behavior has an approved and documented
  deprecation/removal decision.
- Remaining legacy scripts are parameterized, thin adapters or explicitly
  archived.
- The central test suite owns all maintained behavior.
- A clean clone passes the supported release matrix and LFS verification.
