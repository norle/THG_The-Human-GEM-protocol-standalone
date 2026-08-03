# Legacy Python Removal Plan

This plan follows 'REFACTORING_PLAN_NEXT.md'. Its purpose is to remove the
remaining source-checkout legacy Python implementations and workflows after
their supported behavior, migration path, and ownership decisions have been
verified.

The target is a repository with:

- maintained Python implementation under 'src/thg_protocol';
- maintained tests under 'tests/';
- no legacy Python implementation or historical Python workflow outside those
  trees;
- preserved models, datasets, reports, fixtures, and other non-Python research
  artifacts under an explicitly documented owner;
- no installed command or documented workflow depending on a removed path.

The final state is directory-level, not only file-level: every legacy
directory named in the removal manifest must be absent. `Archived` and
`compatibility adapter` describe temporary migration batches only. They are
not final retention categories. Artifacts that are still valuable must be
moved out of those directories before the directory-closing batch.

This plan authorizes planning and verification. It does not authorize deleting
files during the planning phase. Deletion must happen in the reviewable batches
and only after the gates below pass.

## Current baseline

The authoritative inventory is
'docs/legacy-api-inventory.md'. It currently classifies 82 Python files outside
'src/' and the maintained 'tests/' tree as:

1. compatibility adapters whose imports remain temporarily supported;
2. migrated workflow entry points with an intentional package-level
   difference; or
3. archived/no-replacement workflows and historical test suites.

The package replacement contracts are in 'docs/api-contracts.md'; archive
ownership and opt-in historical commands are in 'docs/legacy-workflows.md'.
The current release snapshot is in 'CURRENT_STATE.md'.

The current-head hosted Python 3.10–3.12 matrix is still an external
prerequisite. Local Python 3.10/3.12 suites, wheel smoke tests, and static CI
policy checks pass, but removal batches must not be presented as release
complete until the hosted matrix has run against the commit containing them.

## Non-scope and preservation rules

Do not delete or move any of the following merely because they are adjacent to
legacy Python code:

- 'models/', 'files/', 'data/', report directories, approved fixtures, or
  canonical Git LFS objects;
- generated outputs whose ownership has not been separately decided;
- configuration, credentials, or research artifacts needed to reproduce a
  documented result;
- maintained 'src/thg_protocol' modules or tests that exercise the package
  contract.

If a legacy directory contains both Python and artifacts, first migrate the
approved artifacts to the canonical destination in the directory-closure
ledger below, or explicitly retire them under the artifact inventory. Then
delete the remaining contents and the legacy directory itself. No artifact
owner may keep a legacy directory alive. Do not use recursive deletion against
a broad repository path.

## Directory-closure ledger

This is the complete top-level directory manifest. The listed directories must
all be absent at the end of Batch 5. The destinations are defaults that must be
recorded in `docs/artifact-inventory.md` and checked for path references during
the batch; a different destination requires a documented maintainer decision
before the move.

| Legacy directory | Code and documentation action | Contents disposition before closure |
| --- | --- | --- |
| `functions/` | Migrate all imports to package APIs; remove every Python file and the nested `gpr/` package. | No supported non-Python artifact is owned here; retire checkout-only files. |
| `build_model/` | Migrate build/report callers to `thg_protocol.model_build` and docs. | Fold `README.md` into package/release docs; retire `.DS_Store`. |
| `cell_type_specific_model/` | Migrate supported reduction/exchange/transcriptomics callers; retire solver-only scripts. | Move dependency notes to `docs/dependency-compatibility.md`; retire the legacy `requirements.txt`. |
| `compare_models/` | Migrate callers and CLI checks to `thg_protocol.analysis.compare`/`thg-compare`; remove Python sources. | Move the approved final comparison report to `supplementary_material/model_comparisons/`; delete duplicate/generated reports and migrate the README guidance. |
| `gapfill/` | Migrate the maintained CLI/workflow to `thg_protocol.gapfill`; remove all phase scripts. | Move any retained input fixture to `files/` or `tests/fixtures/`; migrate README/requirements guidance to package docs; retire generated outputs. |
| `generate_data-base/` | Migrate database/model-build callers to package APIs; remove all Python sources. | Move approved input fixtures to `files/`; migrate README/requirements guidance; retire generated caches and outputs. |
| `generate_figures/` | Migrate figure callers to `thg_protocol.figures`; remove the legacy generator. | Move approved final figures to `supplementary_material/figures/`; retire generated run figures/reports and migrate the README. |
| `implement_pathway/` | Migrate callers/examples to `thg_protocol.pathway` and `thg-pathway`; remove all legacy Python workflows. | Move configs and example inputs to `files/pathway/`, published PDFs to `supplementary_material/pathway/`, and approved figures/reports to `supplementary_material/pathway/`; migrate README/docs and retire generated duplicates. |
| `memote_and_task_analysis/` | Migrate maintained checks into `tests/` with markers; remove archived task modules and tests. | Move still-required small task fixtures to `tests/fixtures/memote/`; apply the artifact inventory decision to model files; migrate README guidance. |
| `merge_metabolic_netowrks_and_network_consistency/` | Migrate callers to `thg_protocol.merge` and `thg_protocol.analysis.consistency`; remove Python sources. | Migrate README guidance to package docs; no retained artifact is allowed to keep this directory. |
| `metabolite_reac_identification/` | Migrate callers to `thg_protocol.annotation.metabolite_reactions`; remove Python and monitoring scripts. | Move an approved report snapshot to `supplementary_material/metabolite_reaction/`; retire generated reports and migrate README guidance. |
| `network_analysis/` | Migrate callers to `thg_protocol.analysis`; remove all legacy analysis scripts. | Move the visualization template to `docs/assets/` if still documented; migrate README guidance and retire it otherwise. |
| `test_algorithms/` | Migrate representative cases to `tests/`; delete every archived Python test suite. | Move only small, maintained characterization fixtures to `tests/fixtures/legacy_characterization/`; remove duplicate large model fixtures per the artifact inventory; migrate README guidance. |
| `tools/` | Replace the pathway helper with a package API or documented command, then remove the Python source. | No retained artifact; delete the directory. |
| `utils/` | Replace the SBML helper with the package I/O API, then remove the Python source. | No retained artifact; delete the directory. |

The ledger is a closure requirement, not permission to preserve a legacy
directory as an artifact archive. After the moves, an executable check must
assert that every path in this table is absent and that every approved moved
artifact exists at its new path with the recorded checksum.

## Required preconditions

Before the first deletion batch:

1. Confirm that 'docs/legacy-api-inventory.md' lists every legacy Python file,
   symbol, replacement, status, evidence, consumer, and removal condition.
2. Search imports, string-based imports, direct script execution, CI,
   documentation, notebooks, shell scripts, and packaging manifests with
   repository-wide 'rg'.
3. Classify every reference as maintained, compatibility-only, historical,
   artifact-only, or external/unknown.
4. Migrate maintained callers and examples to 'thg_protocol'.
5. Decide whether each compatibility adapter has any documented external
   consumer. Do not infer that it is unused from the repository search alone.
6. Record an owner and a removal decision for every archived/no-replacement
   workflow.
7. Confirm the current package import-policy, compatibility, CLI, and
   characterization tests are green.
8. Create a clean-clone or disposable worktree for each deletion batch so the
   pre-deletion tree can be recovered without history rewriting.

No batch may begin while an entry is 'Blocked', has an unknown consumer, or
depends on an unresolved artifact decision.

## Deletion batches

Each batch is a separate commit. The path lists below are derived from the
inventory; the inventory remains authoritative if a path is regrouped.

### Batch 0: prepare the removal branch

Update the inventory with a removal-batch column and add a machine-checkable
manifest of the exact paths assigned to each batch. Add or update tests that:

- fail on imports from legacy namespaces in 'src', maintained tests, examples,
  and documentation snippets, except explicitly named compatibility tests;
- verify every inventory path is in exactly one batch;
- verify no package entry point or wheel manifest includes a legacy path;
- verify the seven approved LFS objects and artifact checksums are unchanged.

Do not delete code in this batch. Commit the preparation separately.

### Batch 1: remove pure compatibility re-exports

First migrate all repository callers and compatibility tests to package imports.
Then remove only the wrappers whose supported symbols are exact package
re-exports and whose consumer audit is closed:

- 'functions/__init__.py'
- 'functions/config.py'
- 'functions/pathway_builder.py'
- 'functions/function_reac_identification.py'
- 'functions/gpr/ast_gpr.py'
- 'functions/analyze_annotations.py'
- 'build_model/print_biocyc_compartments.py'
- 'cell_type_specific_model/match_exch_rxns.py'
- 'network_analysis/compaction.py'
- 'tools/list_pathway_reactions.py'
- 'utils/json_to_sbml.py'

The batch must update imports, examples, inventory status, and removal
documentation in the same commit. It must not remove the corresponding
'src/thg_protocol' implementation.

### Batch 2: remove intentional-difference adapters

After callers have migrated to explicit package contracts, remove adapters that
exist only to preserve historical defaults, tuple shapes, output conventions,
or source-checkout command names:

- 'functions/function_annotate_cobra_model.py'
- 'functions/function_metabolite_identification.py'
- 'functions/functions_mass_balance.py'
- 'functions/equations_bm_gdb.py'
- 'functions/functions_merge_metabolic_networks.py'
- 'functions/functions_network_consistency.py'
- 'functions/gpr/auth_gpr.py'
- 'functions/gpr/gpr_def.py'
- 'functions/gpr/get_location_def.py'
- 'functions/ensembl_client.py'
- 'functions/build_id_database.py'
- 'build_model/build_model.py'
- 'build_model/build_model_batch.py'
- 'compare_models/compare_compartements.py'
- 'compare_models/compare_models.py'
- 'gapfill/gapfill.py'
- 'generate_data-base/generate_db.py'
- 'generate_data-base/make_model_from_pkl.py'
- 'generate_data-base/resume_db_gen.py'
- 'generate_figures/create_figure.py'
- 'implement_pathway/pathway_implementation.py'
- 'cell_type_specific_model/model_reduce.py'
- 'network_analysis/find_components.py'
- 'metabolite_reac_identification/metabolite_reac_identification.py'
- 'metabolite_reac_identification/metabolite_reac_identification_with_retry.py'
- 'merge_metabolic_netowrks_and_network_consistency/merge_metabolic_networks.py'

Before deletion, replace every compatibility test with a package-contract
test or move it into an explicitly marked migration test. Preserve tests for
intentional differences as package behavior tests; do not preserve them by
keeping the deleted import path alive.

### Batch 3: remove archived workflow scripts

After an owner has approved the unsupported/removal decision and all
replacement documentation is published, remove archived workflow Python files,
including:

- 'build_model/test_biovelo_query.py';
- solver-heavy cell-specific workflows under 'cell_type_specific_model/';
- archived database, plotting, interactive, and credentialed helpers under
  'functions/';
- historical phase 1/2/3 gapfill scripts under 'gapfill/';
- 'implement_pathway/validate.py' and 'implement_pathway/visualize.py';
- 'network_analysis/loop_removal.py';
- optional MEMOTE/task Python modules under
  'memote_and_task_analysis/'.

Move any models, input tables, reports, or fixtures that survive the artifact
audit to the canonical destinations in the directory-closure ledger before
deleting the enclosing directory. If an artifact is retired, record its
checksum and disposition in the artifact inventory in the same batch.

### Batch 4: remove duplicated historical Python test suites

After representative cases are owned by 'tests/' and the opt-in commands are
no longer needed, remove the archived Python test implementations under:

- 'test_algorithms/gpr_prediction/';
- 'test_algorithms/mass_balance/';
- 'test_algorithms/metabolite_identification/';
- 'test_algorithms/reac_identification/';
- 'memote_and_task_analysis/tests_extra/'.

Move still-needed small fixture data to the destinations in the
directory-closure ledger. If any historical case remains valuable, migrate it
into 'tests/' with an appropriate marker before deleting its source test; no
fixture may keep 'test_algorithms/' or 'memote_and_task_analysis/' alive.

### Batch 5: close every legacy directory and clean references

After Batches 1–4, verify that all artifacts have been moved or explicitly
retired, then remove every directory in the closure ledger and all stale
references. No legacy directory may remain merely because it once owned an
artifact. Update:

- 'docs/legacy-api-inventory.md' with 'Removed' status and commit evidence;
- 'docs/legacy-workflows.md' to remove obsolete opt-in commands;
- 'docs/api-contracts.md' to remove compatibility-only language;
- README, MkDocs navigation, CI, examples, and release documentation;
- 'CURRENT_STATE.md' with the final path manifest and deletion evidence.

## Per-batch deletion protocol

For every batch:

1. Resolve exact paths from the inventory and inspect their consumers.
2. Run the relevant parity and compatibility tests before changing files.
3. Use explicit path arguments for deletion; never delete a repository-wide
   directory recursively.
4. Inspect 'git diff --name-status' and confirm only Python sources, obsolete
   compatibility tests, and approved documentation changed.
5. Run repository-wide searches for removed imports and path-based execution.
6. Run the complete default offline suite and the focused package tests.
7. Run Ruff, package import checks, and legacy-source compilation where
   applicable.
8. Build a source distribution and wheel.
9. Install the wheel outside the checkout and run all installed CLI '--help'
   checks.
10. Verify Git LFS paths, checksums, and 'git lfs fsck'.
11. Record the commit hash and test results in the inventory and state snapshot.

If any check fails, stop the batch, restore only the batch's changes from the
disposable worktree or revert the batch commit, and investigate before
continuing. Do not repair a failed deletion by restoring an undocumented
compatibility import.

## Final completion gates

Removal is complete only when all of the following are true:

- repository search finds no legacy directory from the closure ledger and no
  legacy Python implementation outside 'src' and maintained 'tests';
- no maintained code, test, example, documentation snippet, CI step, or
  installed entry point imports or executes a removed path;
- the inventory marks every former legacy path as 'Removed' and every migrated
  artifact has a new canonical path, checksum, evidence, and owner; there is
  no retained legacy-directory exception;
- package contracts and intentional migration differences remain tested;
- default offline tests pass without network access or full-size model files;
- the supported Python 3.10–3.12 hosted matrix passes on the final removal
  commit;
- the wheel imports successfully outside the repository and all installed CLI
  help checks pass;
- the seven approved LFS objects and checksums remain valid;
- 'CURRENT_STATE.md' records the final removal manifest, preserved artifacts,
  test evidence, and any approved external exception.

## Reviewable commit sequence

1. 'docs: define legacy removal batches and artifact boundaries'
2. 'refactor: migrate callers off pure legacy adapters'
3. 'refactor: remove pure legacy compatibility modules'
4. 'refactor: migrate callers off intentional-difference adapters'
5. 'refactor: remove intentional-difference adapters'
6. 'refactor: remove archived legacy workflows'
7. 'refactor: remove archived historical test suites'
8. 'docs: record final legacy removal and artifact ownership'

Do not combine model/data deletion, Git LFS history changes, or unrelated
workflow rewrites with legacy Python removal.
