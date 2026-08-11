# THG Protocol Refactoring Closeout Plan

This is the executable closeout plan for:

1. proving that supported `src/thg_protocol` behavior covers the legacy
   checkout interfaces;
2. documenting any intentional behavior changes;
3. removing every legacy checkout directory after its code and contents have
   been migrated or explicitly retired; and
4. completing the remaining release and CI gates.

The legacy directories must not be deleted merely because equivalent-looking
functions exist in `src`. Deletion is allowed only after the parity, reference,
and release gates in this document pass.

## Required final directory state

This closeout has a directory-level end state: no legacy checkout directory
may remain in the final repository. `Equivalent`, `Intentional difference`, and
`Archived` are temporary statuses used while executing the removal batches;
they are not permission to retain a legacy directory indefinitely.

The final removal manifest must make these top-level directories absent:

`build_model/`, `cell_type_specific_model/`, `compare_models/`, `functions/`,
`gapfill/`, `generate_data-base/`, `generate_figures/`, `implement_pathway/`,
`memote_and_task_analysis/`,
`merge_metabolic_netowrks_and_network_consistency/`,
`metabolite_reac_identification/`, `network_analysis/`, `test_algorithms/`,
`tools/`, and `utils/`.

This does not authorize silent loss of research material. Before a directory
is closed, each non-Python file must be moved to an approved canonical
artifact location or explicitly retired with its checksum and disposition
recorded. A legacy directory containing artifacts is not considered removed
until those contents have been dealt with and the directory itself is gone.

## Current baseline

The package under `src/thg_protocol` is the supported interface. The following
work is already recorded as complete in `CURRENT_STATE.md`:

- setuptools packaging and the `src/` layout;
- package APIs for maintained annotation, GPR, model-building, merge,
  gapfill, pathway, comparison, analysis, figures, and cell-specific helpers;
- service client boundaries and offline adapters;
- installed commands `thg-gapfill`, `thg-pathway`, and `thg-compare`;
- central tests, wheel validation, and targeted Git LFS migration;
- compatibility adapters for selected legacy functions and workflows.

The remaining legacy code is divided into three categories:

1. **Compatibility wrappers**: old import paths that delegate to package APIs.
2. **Historical workflows**: source-checkout scripts that are not part of the
   installed release contract.
3. **Data, reports, and research artifacts**: files outside `src` that are not
   Python package implementations and require separate ownership decisions.

This plan primarily governs categories 1 and 2. It does not authorize deleting
models, datasets, reports, or research outputs.

## Non-negotiable compatibility rule

“Functionally equivalent” means equivalent supported behavior, not identical
implementation. For every retained legacy surface, the comparison must cover
the documented contract:

- accepted input types and defaults;
- return values, schemas, ordering, and identifiers;
- model mutations and object ownership;
- created, modified, or deleted files;
- network, solver, and other external side effects;
- warnings, logging, and exceptions;
- CLI arguments, exit codes, and help behavior where applicable.

Intentional differences are allowed only when they are documented with a
migration path. Examples already documented include explicit output paths and
the package merge API returning `MergeReport` instead of legacy positional
overlap lists.

## Phase A: Freeze the legacy inventory

Create a tracked inventory of every legacy Python module, public function,
class, CLI entry point, and import alias that is in scope for removal.

The inventory must record:

| Field | Requirement |
| --- | --- |
| Legacy path | Exact checkout path and import path |
| Symbol | Function, class, or CLI name |
| Package replacement | Exact `thg_protocol` module and symbol |
| Status | Equivalent, intentionally changed, archived, or no replacement |
| Evidence | Test file and fixture used for the decision |
| Consumers | Repository callers and known documented callers |
| Removal condition | Specific condition required before deletion |

Use repository search to find imports and direct script execution. Include
legacy tests and documentation references in the inventory. Do not classify a
symbol as unused solely because it is not imported by the installed package.

Deliverable:

- `docs/legacy-api-inventory.md`

Exit gate:

- Every Python file under the legacy compatibility/workflow directories is
  classified, including explicit archived/unsupported entries.

## Phase B: Define contracts before comparing implementations

For each legacy symbol with a package replacement, write a concise contract
before running parity tests. The contract must state inputs, outputs,
mutation, filesystem behavior, external services, optional dependencies, and
errors.

For each archived workflow with no replacement, document one of:

- a supported package replacement;
- an approved deprecation and removal decision; or
- an explicit unsupported source-checkout status.

Deliverable:

- Extend `docs/api-contracts.md` and `docs/legacy-api-inventory.md` with the
  contract and migration decision.

Exit gate:

- No legacy symbol is tested against an undefined notion of “same.”

## Phase C: Build characterization and parity tests

For each mapped legacy/package pair, add tests that exercise the same inputs
against both implementations. Prefer small deterministic fixtures and static
service clients. Use temporary directories for filesystem behavior and toy
COBRA models where possible.

Required parity coverage:

1. Pure utilities: GPR parsing, annotation, reaction matching, formula and
   mass-balance helpers, ID normalization, and configuration handling.
2. Model operations: merge, consistency, network cleanup, reconstruction,
   exchange handling, and model I/O.
3. Workflow functions: gapfill, pathway implementation, comparison, database
   parsing/building, and promoted cell-specific helpers.
4. External-service workflows: compare normalized results using injected fake
   or recorded clients; do not use live services in the default parity gate.
5. CLIs: compare accepted options, exit status, help output, and documented
   output artifacts.

Tests must distinguish meaningful results from unstable details such as
timestamps, temporary paths, object identities, or unordered dictionaries.
Where exact equality is not appropriate, define a normalized comparison in
the contract.

Required test result categories:

- **Equivalent**: parity test passes and the package implementation becomes
  the maintained source of behavior.
- **Intentional difference**: difference is documented, tested, and has a
  migration path.
- **Archived**: no package replacement; source-checkout behavior is explicitly
  unsupported and excluded from the installed release contract.
- **Blocked**: insufficient evidence; the legacy implementation remains.

Exit gate:

- No mapped legacy symbol remains untested.
- Every difference is either resolved or recorded as intentional.
- The default offline suite remains green.

## Phase D: Migrate callers and enforce the new API

Update maintained source, tests, examples, and documentation to import from
`thg_protocol`. Keep compatibility wrappers only for callers that are still
within the documented migration window.

Add a test that fails if maintained code introduces new imports from the legacy
namespace. Keep explicit compatibility tests separate from maintained package
tests.

For archived source-checkout workflows, make the status clear in their module
docstrings and documentation. They must not be presented as installed CLI
commands or release-gate evidence.

Exit gate:

- Maintained code has no legacy imports except the explicitly tested adapter
  boundaries.
- Documentation points users to package APIs and installed commands.
- No compatibility wrapper is needed by the supported test suite except those
  listed in the inventory.

## Phase E: Remove legacy implementations and close every legacy directory

After Phases A–D pass, remove the legacy directories in small, reviewable groups. The order is:

1. duplicate pure utilities;
2. wrappers whose parity tests now target package APIs;
3. migrated workflow scripts;
4. archived scripts and historical test suites after their replacement or
   explicit retirement decision;
5. non-Python contents and empty directories, so every directory in the final
   removal manifest is absent.

Before each deletion group:

- confirm the inventory lists the exact files and symbols;
- run the relevant parity and maintained tests;
- search the repository for imports, path-based execution, documentation, and
  CI references;
- update migration documentation;
- verify that no data or model artifacts are included in the deletion.

Delete only Python source and obsolete compatibility tests/wrappers. Preserve
research artifacts, canonical models, approved fixtures, and documented user
outputs unless a separate artifact decision authorizes their removal.

After each deletion group:

- run the full default offline suite;
- run Ruff and package import checks;
- build a wheel and verify that it installs outside the checkout;
- run installed CLI `--help` smoke tests;
- inspect the diff for accidental artifact or API removal.

The final legacy-removal commit must include the exact path manifest, updated
artifact checksums/dispositions, and an inventory showing every former legacy
entry as `Removed` or as a preserved artifact relocated outside the legacy
directories. No compatibility adapter, archived workflow, README, fixture, or
generated report may be left behind solely to keep one of the legacy
directories alive.

## Phase F: Complete the original plan’s remaining release gates

Carry forward these unfinished items from `CURRENT_STATE.md`:

### F1. Current-head CI matrix

Run the supported Python 3.10–3.12 package matrix against the current head.
Record each job result in `CURRENT_STATE.md`. If the matrix is green, mark
Phase 7 of the original plan complete.

### F2. Historical test ownership

Decide the final status of duplicated suites under `test_algorithms/` and the
additional MEMOTE checks. Either:

- migrate maintained cases into `tests/` with markers and fixtures; or
- record an explicit retirement decision, then remove the archived source
  suites in the legacy-removal batches.

An archive decision is documentation for the migration/removal step, not a
reason to retain the legacy directories. They must not remain ambiguous or be
treated as default release evidence.

### F3. API contract maintenance

Keep `docs/api-contracts.md` aligned with all promoted APIs during parity and
removal. Every public workflow must document types, return schema, mutation,
side effects, and errors.

### F4. Git LFS verification

When publishing or cloning from a new remote, verify the seven approved LFS
objects, run `git lfs fsck`, and compare checked-out content with the recorded
checksums. Do not perform history rewrites without explicit maintainer
approval and recorded affected refs.

### F5. Optional online validation

Keep the credential-gated BioCyc fixture opt-in. Run it when credentials are
available, but do not make it a blocker for the offline release gate.

## Final definition of done

This closeout is complete when all of the following are true:

- Every legacy Python symbol has an inventory entry and a defined contract.
- Every replacement has parity evidence or a documented intentional difference.
- Maintained callers use `thg_protocol`, not legacy imports.
- Every directory in the final removal manifest is deleted after its contents
  are migrated or explicitly retired.
- No legacy Python implementation, compatibility adapter, archived workflow,
  or historical test suite remains outside `src/` and maintained `tests/`.
- Preserved artifacts have approved canonical destinations outside the legacy
  directories; none are retained merely as a reason to keep a legacy folder.
- No supported workflow silently loses historical behavior.
- Default tests pass without network access or full-size model files.
- The supported Python 3.10–3.12 CI matrix passes on the current head.
- The wheel installs and imports successfully outside the repository.
- Installed CLI help checks pass without optional heavy dependencies.
- The seven approved Git LFS objects pass verification when applicable.
- `CURRENT_STATE.md` records the final evidence, remaining intentional
  exceptions, and the completed legacy-removal decision.

## Reviewable commit sequence

Use focused commits at these boundaries:

1. `docs: inventory legacy APIs and removal scope`
2. `test: add legacy and package parity contracts`
3. `refactor: migrate maintained callers to package APIs`
4. `refactor: remove verified legacy compatibility group`
5. `docs: archive historical workflows and update contracts`
6. `ci: complete current-head release matrix`
7. `refactor: remove final approved legacy sources`

Do not combine unrelated artifact cleanup or history rewrites with legacy
source removal.
