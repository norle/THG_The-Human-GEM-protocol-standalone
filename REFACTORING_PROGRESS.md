# THG Protocol Refactoring Progress

This document records completed work and dated validation snapshots for the
refactoring described in `REFACTORING_PLAN.md`. It is historical: the current
status, open decisions, phase gates, and next pull requests live in the plan.
Later repository-state notes may qualify historical claims when a temporary
recovery ref or another local-only validation artifact is no longer available.

When adding an entry:

- use the date on which the validation was performed;
- describe the behavior or boundary that changed;
- record the exact validation commands and results when they are useful;
- identify any known follow-up work;
- include the commit hash once the checkpoint commit exists.

## 2026-07-28

### Retry metabolite/reaction workflow service boundary

- Characterized `metabolite_reac_identification/metabolite_reac_identification_with_retry.py`.
  It now provides an import-safe argument parser and delegates execution to
  `thg_protocol.annotation.metabolite_reactions` instead of loading models or
  running annotation at import time.
- Added `retry_metabolite_annotations` and `MetaboliteRetryResult`. Retry
  rounds use the injected PubChem client, append successful records to the
  explicit annotation report, and rewrite the final unresolved-record report.
  The workflow API exposes optional retry-round and stopping-threshold
  controls while retaining single-pass defaults for existing callers.
- Added static PubChem coverage for successful retry records, unresolved
  failure reporting, configuration validation, and CLI `--help` import safety.
  Updated the legacy workflow README and service-boundary audit.
- Validation:
  - Installed this checkout into `/tmp/thg-refactor-validation.BnvTQF` with
    `pip install --no-deps --no-build-isolation --target ... .`.
  - The installed-package focused retry suite passed with 6 tests.
  - The full offline gate passed: `68 passed, 1 skipped, 2 warnings` for
    `pytest -m "not slow and not online and not solver and not gurobi and not memote" -q`.
  - `ruff check src tests` passed.
  - `python -m compileall -q src/thg_protocol metabolite_reac_identification tests/unit`
    and `git diff --check` passed.
  - The retry CLI `--help` smoke test passed from the installed package target.
- Follow-up: characterize and migrate the remaining batch KEGG, single-model
  location, and legacy database service fallbacks listed in the plan.
- Checkpoint commit: `42ad990` (`refactor: isolate retry annotation workflow`).

## 2026-07-28

### Autonomous checkpoint commit cadence

- Clarified the implementation plan so agents create frequent, narrowly scoped
  commits automatically after independently validated boundaries, without
  waiting for a separate user request.
- Required agents to isolate unrelated working-tree changes and record any
  unavailable validation tools when committing a reviewable change.
- Validation: reviewed the plan diff and ran `git diff --check`.

## 2026-07-28

### Explicit model-derived figure workflow and service audit

- Added `thg_protocol.figures.models` with dependency-light model summaries,
  unannotated-metabolite statistics, new-reaction annotation group statistics,
  and lazy matplotlib rendering for model-component, annotation-group,
  MEMOTE, and supplied algorithm-result charts.
- Replaced import-time execution in `generate_figures/create_figure.py` with an
  explicit-path compatibility CLI. It loads models only after parsing,
  delegates report and model work to package APIs, and accepts optional score
  JSON files instead of embedding historical values in production code.
- Removed unused direct network-library imports from the single-model and
  database-builder orchestrators and recorded remaining compatibility-helper
  fallbacks in `docs/service-boundary-audit.md`.
- Added offline fake-model coverage for the new pure statistics and a guarded
  rendering smoke test when matplotlib is installed.
- Validation:
  - targeted Ruff checks for the figure package and figure tests passed;
  - the shared Python 3.12.9 environment at
    `/home/reinism/THG_igor_repo/THG_The-Human-GEM-protocol/.venv` provides
    pytest 9.1.1 and Ruff 0.15.20;
  - full offline validation passed: `64 passed, 1 skipped, 2 warnings` for
    `python -m pytest -m "not slow and not online and not solver and not gurobi and not memote" -q`;
  - `ruff check src tests` passed;
  - `python -m compileall -q src/thg_protocol build_model functions generate_data-base metabolite_reac_identification generate_figures tests/unit` passed with the known legacy invalid-escape warnings;
  - `generate_figures/create_figure.py --help` passed without COBRA or
    matplotlib;
  - `pip wheel --no-deps --no-build-isolation .` passed, and the wheel was
    installed into `/tmp/thg-installed-check-20260728` and imported from
    `/tmp` outside the checkout;
  - the rendering smoke test was skipped because matplotlib is not installed
    in this validation environment.
- Follow-up: migrate the retry annotation script and legacy database/location
  service fallbacks with static-client tests.

## 2026-07-28

### Current checkpoint packaging validation

- Reviewed the combined service-boundary, metabolite/reaction, and figure API
  checkpoint against the phase status and remaining gates in
  `REFACTORING_PLAN.md`.
- Built the wheel without dependency resolution, installed it into a temporary
  target outside the checkout, and imported the new annotation, figure, and
  service APIs from that installed artifact.
- Validation:
  - `python -m compileall -q src/thg_protocol build_model functions generate_data-base metabolite_reac_identification tests/unit`
    passed, with pre-existing invalid-escape warnings in legacy modules.
  - `pip wheel --no-deps --no-build-isolation .` passed.
  - `pip install --no-deps --target <temporary-target> <built-wheel>` passed.
  - Outside-checkout public API smoke testing against the installed wheel
    passed.
  - `git diff --check` passed.
  - Full pytest and Ruff gates remain pending because neither tool is installed
    in the active environment.

### Report-driven figure workflow characterization

- Characterized the reproducible portion of
  `generate_figures/create_figure.py`: Excel workbook sheets 4, 5, and 6
  provide annotation-group tables, which produce the metabolite, reaction, and
  gene SVG charts.
- Added `thg_protocol.figures.comparison` with pure annotation-group
  summaries, explicit report/output paths, structured results, and lazy imports
  for pandas and plotting dependencies. Added a `figures` optional dependency
  extra for the rendering environment.
- Added offline tests for import safety and the legacy cumulative group
  calculation. The API does not load COBRA models or perform work on import.
- Validation:
  - `python -m compileall -q src/thg_protocol/figures tests/unit/test_figures_api.py`
    passed.
  - `git diff --check` passed.
  - A `PYTHONPATH=src` pure-summary API smoke test passed.
  - The complete offline pytest/Ruff gates remain pending because pytest, Ruff,
    and COBRA are unavailable in the active environment.
- Follow-up: migrate the model-dependent and hard-coded legacy figure outputs,
  then audit remaining direct service calls in deferred workflows.

## 2026-07-28

### Metabolite/reaction workflow service boundary

- Characterized `metabolite_reac_identification/metabolite_reac_identification.py`:
  it gathers model metabolites, writes the PubChem annotation and failure
  reports, matches reactions against the reference database, and writes the
  two legacy SBML outputs.
- Added `thg_protocol.annotation.metabolite_reactions` with an explicit-path
  workflow API and structured result. COBRA is imported only when the workflow
  runs, and the legacy script now provides guarded argparse-based execution
  with explicit model, database, report, and SBML output paths.
- Extended `generate_met_annotation` to pass an injected PubChem client to each
  lookup. The package workflow uses `PubChemClient` by default or a supplied
  static/fake adapter, so its service path no longer depends on PubChemPy.
- Moved the model annotation/SBML normalization implementation to
  `thg_protocol.annotation.model` and retained
  `functions.function_annotate_cobra_model` as an import-safe compatibility
  wrapper.
- Added offline tests for PubChem client propagation and workflow/legacy import
  safety.
- Validation:
  - `python -m compileall -q src/thg_protocol/annotation src/thg_protocol/services metabolite_reac_identification functions/function_annotate_cobra_model.py tests/unit/test_metabolite_annotation_api.py tests/unit/test_metabolite_reaction_workflow.py` passed.
  - `git diff --check` passed.
  - A `PYTHONPATH=src` package import/static PubChem smoke test passed.
  - A `PYTHONPATH=src` legacy script `--help` smoke test passed without COBRA
    or model files, and a static one-metabolite annotation smoke test passed.
  - `python -m pytest -m "not slow and not online and not solver and not gurobi and not memote" -q` is blocked because pytest is unavailable, and `ruff check src tests` is blocked because Ruff is unavailable. COBRA is also unavailable; the full offline pytest/Ruff gates and end-to-end SBML workflow remain pending in the development environment.
- Follow-up: run the pending offline pytest/Ruff gates, then characterize the
  next deferred workflow and migrate any remaining direct service calls.

## 2026-07-28

### Database-builder service injection

- Characterized `generate_data-base/generate_db.py` as the next deferred
  workflow after the batch and single-model builders.
- Extended the injectable KEGG client with generic page and batched-entry
  operations, including database prefixes, response caching, and static
  offline fixtures. The existing reaction-entry API remains compatible.
- Routed the database builder’s KEGG pathway, reaction, compound, and
  same-as lookups through the injected client. Its GPR construction now
  receives the package BioCyc and KEGG clients, and location/whole-model gene
  annotation receives the package Ensembl client.
- Threaded the client through the legacy `pathway`, `reaction`, `compound`,
  and `gpr` classes and through KEGG fallback helpers. Callers that do not
  provide a client retain their previous network fallback behavior.
- Added offline coverage for static database-builder pages/entries and the
  production client’s compound batch URL/parsing behavior.
- Validation:
  - `python -m compileall -q src/thg_protocol/services functions/class_generate_database.py functions/function_bm_gdb.py generate_data-base/generate_db.py tests/unit/test_biocyc_kegg_clients.py` passed with the pre-existing invalid-escape warnings.
  - A `PYTHONPATH=src` static KEGG database-boundary smoke test passed.
  - `python -m pytest --version` confirms pytest is unavailable, and
    `ruff --version` confirms Ruff is unavailable. COBRA is also unavailable;
    the full offline pytest/Ruff gates and legacy database-builder runtime
    remain pending in the development environment.
- Follow-up: run the pending offline pytest/Ruff gates, then characterize the
  next deferred workflow, `metabolite_reac_identification`.

## 2026-07-28

### Single-model builder service injection

- Characterized `build_model/build_model.py` as the next deferred workflow
  after the batch model-builder boundary.
- Routed its GPR calls through the injectable BioCyc and KEGG package clients,
  replaced direct Ensembl page lookups with the package Ensembl client, and
  passed that client into the legacy location helper.
- Updated `getLocationnew` to prefer its supplied cache/client and retain the
  old Ensembl URL fallback only for callers that do not provide a client. This
  keeps existing positional callers compatible while allowing the characterized
  builder workflows to run with an offline/static Ensembl adapter.
- Verified the published `refactoring-cleanup` branch at
  `36dedbd2cb39f7482277a5e79a77c121db4e3caf`, fetched its seven LFS objects,
  and passed `git lfs fsck refactoring-cleanup`.
- Validation:
  - `python -m compileall -q src/thg_protocol/services build_model/build_model.py build_model/build_model_batch.py functions/gpr/get_location_def.py tests/unit/test_biocyc_kegg_clients.py tests/unit/test_ensembl_client.py` passed with the pre-existing invalid-escape warnings.
  - A static Ensembl/KEGG client smoke test passed.
  - `pytest` and Ruff are unavailable in the active environment; the pending
    offline test and lint gates remain unrun. `cobra` is also unavailable, so
    the legacy builder runtime was not executed.
- Follow-up: run the full offline pytest/Ruff gates when development
  dependencies are available, then characterize the next deferred workflow.

### Batch model-builder service injection

- Characterized `build_model/build_model_batch.py` as the next legacy workflow
  with direct external-service access.
- Added a cached, retrying KEGG reaction-entry batch operation to
  `thg_protocol.services.kegg` and routed the legacy batch helper through its
  injectable client protocol. The static adapter now supports offline reaction
  entry fixtures.
- Updated the batch workflow to accept BioCyc, KEGG, and Ensembl clients. Its
  KEGG reaction prefetch, BioVelo query, BioCyc protein/location XML lookups,
  and Ensembl annotation prefetch now use those clients. The legacy session is
  retained only for compatibility with the unchanged `getLocation` call path.
- Validation:
  - `python -m compileall -q src/thg_protocol/services build_model/build_model_batch.py tests/unit/test_biocyc_kegg_clients.py tests/unit/test_ensembl_client.py` passed with the pre-existing invalid-escape warning in the legacy batch script.
  - A `PYTHONPATH=src` static Ensembl/KEGG client smoke test passed.
  - `python -m pytest --version` and `ruff --version` confirm that pytest and
    Ruff are unavailable in the active environment; the pending offline test
    and lint gates remain unrun.
- Follow-up: migrate the next characterized deferred workflow and run the full
  offline pytest/Ruff gates once the development dependencies are available.

### BioCyc and KEGG GPR service boundaries

- Added `thg_protocol.services.biocyc` and `thg_protocol.services.kegg` with
  injectable protocols, retrying and timeout-bound production clients,
  per-client response caches, normalized request errors, and static offline
  adapters.
- Updated the legacy `functions.gpr.gpr_def.getGPR` path to accept the package
  clients while preserving its existing positional `session` argument. Its
  BioCyc EC/page lookups and KEGG fallback/link lookups now route through those
  clients.
- Added offline static-client coverage, including a legacy GPR call that can
  run without network access when the GPR dependency set is installed.
- Validation:
  - `python -m compileall -q src/thg_protocol/services functions/gpr/gpr_def.py tests/unit/test_biocyc_kegg_clients.py` passed (with pre-existing invalid-escape warnings in the legacy parser).
  - Direct GPR smoke testing is blocked in this environment because `cobra` is
    absent; `pytest` and `ruff` are also unavailable. Run the normal offline
    test and lint gates in the project development environment before a
    checkpoint commit.
- Current-tree validation status: this file adds three tests beyond the last
  fully validated 49-test checkpoint; they have not yet passed a full `pytest`
  run in the current working tree.
- Follow-up: migrate the remaining direct service calls when their deferred
  workflows are characterized.

### Ensembl annotation service boundary

- Moved Ensembl REST access into `thg_protocol.services.ensembl`, with a
  normalized annotation type, injectable client protocol, production client,
  static offline adapter, explicit timeout/retry behavior, and per-client
  request caching.
- Converted `functions.ensembl_client.fetch_ensembl_annotations` to a thin
  compatibility wrapper that preserves its dictionary-shaped return value.
- Added offline coverage for static-client normalization and unknown identifier
  handling.
- Validation:
  - `python -m compileall -q src/thg_protocol/services functions/ensembl_client.py` passed.
  - A direct package import and static-client lookup passed.
  - The active environment does not include `pytest` or `ruff`; run the normal
    offline test and lint gates in the project development environment before a
    checkpoint commit.
- Current-tree validation status: this file adds one test beyond the last fully
  validated 49-test checkpoint; it has not yet passed a full `pytest` run in the
  current working tree.
- Follow-up superseded later on 2026-07-28: the BioCyc and KEGG GPR boundaries
  are recorded above. Remaining direct service calls will move behind those
  clients as their deferred workflows are characterized.

## 2026-07-27

### Branch-local Git LFS migration and artifact cleanup

- Created checkpoint commits `2750cad` (package and approved artifact policy)
  and `e54c81f` (generated-artifact index cleanup) before rewriting history.
- Rewrote only the local `refactoring-cleanup` branch. The seven approved
  canonical model/reference paths are now LFS pointers. At validation time, the
  pre-rewrite tip was retained in the migration worktree as
  `refactoring-cleanup-pre-lfs` for recovery. No remote refs were changed by the
  rewrite operation itself.
- Generated backups, logs, caches, duplicate models, intermediate reports and
  figures, and large test fixtures were removed from Git tracking but remain in
  the working tree. Final published reports/figures remain ordinary Git files.
- Validation:
  - `git lfs ls-files --long` lists exactly the seven approved paths.
  - `git lfs fsck refactoring-cleanup` passed.
  - A temporary fresh clone of `refactoring-cleanup`, populated from the local
    LFS object cache, checked out all seven files and matched every recorded
    SHA-256 checksum.
- Rewritten target tip at migration validation: `b23c438`; validation record
  commit: `122b7f8`; final inventory wording commit: `4011255`; pre-rewrite
  recovery tip: `e54c81f`.
- Original follow-up: coordinate the force-push of the rewritten branch and
  upload its LFS objects before collaborators use the new remote history.
- Repository-state note, 2026-07-28: this checkout no longer contains
  `refactoring-cleanup-pre-lfs`, and commit `e54c81f` is not available as a
  local Git object. The local `origin/refactoring-cleanup` tracking ref equals
  local `HEAD` (`36dedbd`), but it was not refreshed from the network during
  this review. Verify the live remote ref and all seven LFS objects before any
  further push. If pre-rewrite recovery is still required, recreate a durable
  recovery tag or branch from an authoritative clone or backup.

## 2026-07-27

### Maintainer artifact and namespace decisions

- Maintainer approved retaining all large files locally while separating Git
  ownership: canonical models/reference inputs use targeted Git LFS, final
  published reports and figures remain ordinary Git files, and generated,
  duplicate, backup, cache, log, and large test-fixture files are removed from
  Git tracking but not deleted locally.
- Maintainer authorized rewriting the `refactoring-cleanup` branch history for
  this targeted LFS migration and confirmed that the legacy `functions`
  namespace must not ship in wheels; new code uses `src/thg_protocol`.
- Recorded the approved disposition in `docs/artifact-inventory.md` and added
  targeted `.gitattributes`/`.gitignore` rules. No index removal or history
  rewrite has been run yet; the next checkpoint is the validated policy commit.

## 2026-07-27

### Gapfill, comparison, and PubChem workflow boundaries

- Added `thg_protocol.gapfill` JSON APIs for deterministic candidate
  generation and phase 1→2→3 output handling, with an installed `thg-gapfill`
  command that accepts explicit model and output paths.
- Added `thg_protocol.analysis.compare` and `thg-compare` for reaction overlap
  and stoichiometry reports, including optional blocked-reaction comparison.
- Added an injectable PubChem client protocol, retrying production adapter, and
  static offline adapter; metabolite identification accepts the injected
  client while retaining a lazy PubChemPy compatibility path.
- Added offline unit and CLI-help coverage for these boundaries and documented
  the APIs, extras, commands, and initial workflow guides.
- Validation:
  - `.venv/bin/python -m ruff check src tests` passed.
  - `.venv/bin/python -m pytest -m "not slow and not online and not solver and not gurobi and not memote" -q` passed with 49 tests.
  - `.venv/bin/python -m thg_protocol.gapfill.cli --help` passed.
  - `.venv/bin/python -m thg_protocol.analysis.compare_cli --help` passed.
  - `.venv/bin/python -m build --no-isolation` built sdist and wheel; a
    no-dependencies wheel installed in a temporary environment and imported
    `thg_protocol`, `thg_protocol.gapfill`, `thg_protocol.analysis.compare`,
    and `thg_protocol.services.pubchem` from outside the checkout. Installed
    gapfill and comparison `--help` smoke tests passed.
- Follow-up: characterize the legacy gapfill and comparison report contracts
  before replacing their repository-relative scripts, and complete the other
  external-service client boundaries.

## 2026-07-27

### Import-safe pathway CLI

- Added `thg_protocol.pathway.implement_pathway` and the file-oriented
  `implement_pathway_files` API for deterministic JSON model transformation.
- Added `thg-pathway` with explicit `--model`, `--config`, `--database`, and
  `--output` arguments. Parsing `--help` does not import optional workflow
  dependencies or load model files.
- Added unit coverage for CLI help and temporary-output behavior.
- Validation:
  - `.venv/bin/python -m ruff check src tests` passed.
  - `.venv/bin/python -m pytest -m "not slow and not online and not solver and not gurobi and not memote" -q` passed with 44 tests.
  - `.venv/bin/python -m thg_protocol.pathway.cli --help` passed.
  - Editable installation with pip was attempted, but build isolation could
    not download `setuptools>=68` in the restricted offline environment.
- Follow-up: migrate the legacy pathway implementation script to delegate to
  this API after its report and annotation-generation contract is characterized.

## 2026-07-27

### Pathway workflow API migration

- Promoted `create_compartment_metabolites` and
  `create_compartment_reactions` to `thg_protocol.pathway`.
- Preserved the legacy `functions` and `functions.pathway_builder` import paths
  as compatibility aliases.
- Added tests covering target metabolite promotion, configured metabolite
  annotation, reaction construction, and legacy alias identity.
- Validation:
  - `.venv/bin/python -m ruff check src tests` passed.
  - `.venv/bin/python -m pytest -m "not slow and not online and not solver and not gurobi and not memote" -q` passed with 42 tests.
- Follow-up: add the import-safe pathway CLI only after its argument contract
  and temporary-output behavior are characterized.

## 2026-07-27

### Pathway package and Phase 1 release gate

- Converted `src/thg_protocol/pathway.py` into the `thg_protocol.pathway`
  package, moving implementation to `pathway/core.py` and re-exporting the
  stable helpers from `pathway/__init__.py`.
- Added baseline GitHub Actions CI for Python 3.10–3.12, Ruff, the default
  offline test selection, source/wheel builds, and an outside-checkout wheel
  import smoke test.
- Added the dependency compatibility matrix and complete tracked-artifact
  inventory with sizes, SHA-256 checksums, proposed handling, and explicit
  pending approval status. No LFS tracking, index removal, or history rewrite
  was performed.
- Validation:
  - `.venv/bin/python -m pip install -e ".[dev]"` passed.
  - `.venv/bin/python -m pytest -m "not slow and not online and not solver and not gurobi and not memote"` passed with 40 tests.
  - `.venv/bin/python -m ruff check src tests` passed.
  - `.venv/bin/python -m build --no-isolation` built the sdist and wheel.
  - The wheel installed with `--no-deps` into a temporary virtualenv outside
    the checkout, and `thg_protocol` plus `thg_protocol.pathway` imported
    successfully.
- Removed stale generated build/egg-info entries so the wheel contains only
  the package layout (`thg_protocol/pathway/__init__.py` and `core.py`), not the
  former `thg_protocol/pathway.py` module.
- The isolated local build could not download its temporary `wheel` dependency
  under the restricted network; CI retains the standard isolated build path.
- Follow-up: obtain maintainer approval for the dependency/artifact inventory
  and legacy `functions` wheel policy before any artifact mutation.

## 2026-07-27

- Current working-tree validation:
  - `.venv/bin/python -m pytest -m "not slow and not online and not solver and not gurobi and not memote"` passed with 38 tests.
  - `.venv/bin/python -m ruff check src tests` passed.
- The package remains installed editable in the active Python 3.12 environment.
- Clean-wheel installation and smoke testing from outside the checkout remain
  Phase 1 gates.
- No Git LFS mutation or history rewrite has been performed.

## 2026-07-13

### Pathway parsing and configuration boundaries

- Added dependency-light pathway helpers in
  `src/thg_protocol/pathway.py`:
  - universal reaction-equation parsing;
  - model-ID resolution through the robust metabolite matcher;
  - compartment abbreviation substitution;
  - compartment-filtered metabolite configuration selection;
  - reaction object construction.
- Updated `functions/pathway_builder.py` to delegate parsing, reaction
  construction, and configuration selection to the package API.
- Added tests for parser output, model-ID resolution, non-mutating
  configuration selection, compartment translation, and optional reaction
  fields.
- The focused pathway suite passed with 8 tests, and the default offline suite
  passed with 37 tests.
- Focused Ruff checks passed. Unrelated findings remain in legacy modules.
- Follow-up: split and characterize the mutation-heavy
  `create_compartment_metabolites` and `create_compartment_reactions`
  workflows before moving them.

## 2026-07-07

### Packaging and project foundation

- Added `pyproject.toml` with package metadata, dependency extras, pytest
  markers, and Ruff/Black configuration.
- Added the initial `src/thg_protocol` package, configuration API, documentation
  skeleton, and expanded `.gitignore`.
- Added initial package import, configuration, characterization, and API tests.
- Removed the stray `functions/__init.py__` file and repaired the legacy
  `functions` package initializer.
- Kept legacy package initializers lightweight and import-safe.

### Reaction annotation migration

- Moved the reaction-identification implementation to
  `thg_protocol.annotation.reactions`.
- Converted `functions.function_reac_identification` into a compatibility
  wrapper.
- Added behavior and public-name tests across the package and legacy paths.

### GPR migration

- Moved the GPR AST implementation to `thg_protocol.gpr.ast_gpr`.
- Converted `functions.gpr.ast_gpr` into a compatibility wrapper.
- Kept `thg_protocol.gpr` lazy so importing it does not require COBRA until a
  helper is accessed.
- Follow-up: add direct helper behavior tests when COBRA is available or the
  parser can be isolated from it.

### Metabolite annotation migration

- Moved metabolite-identification logic to
  `thg_protocol.annotation.metabolites`.
- Converted the legacy module into a compatibility wrapper.
- Made PubChemPy lazy and removed import-time proxy detection.
- Follow-up: remove the transitional file-level Ruff suppression, isolate the
  PubChem client, and remove remaining import-time global configuration.

### Reaction configuration helpers

- Added pure helpers in `thg_protocol.reaction_config` for reaction-entry
  construction, direction-derived bounds, and non-mutating configuration
  upserts.
- Updated the legacy interactive helper to delegate these operations to the
  package API.
- Added tests for validation, bounds, duplicate handling, and mutation safety.

### Pathway helper migration

- Moved dependency-light pathway helpers to `thg_protocol.pathway`, including
  compartment handling, metabolite matching, ID generation, and formula-based
  compartment copying.
- Left broader mutation-heavy pathway workflows as explicit lazy wrappers.
- Follow-up: convert `thg_protocol.pathway` from a module to a package before
  adding the installed pathway CLI.

### Validation snapshots

Validation during the day progressed from 21 to 33 passing default tests as
helpers and tests were added. Focused Ruff and compile checks passed for the
migrated modules. COBRA-dependent GPR behavior was not executed in the earliest
environment because COBRA was not yet installed.

### Artifact-management checkpoint

- No `.gitattributes`, Git LFS tracking, index removal, or history rewrite was
  performed.
- The required next step remains a read-only inventory that records paths,
  sizes, ownership, provenance, tracking status, and proposed disposition.
- Any LFS tracking or history rewrite requires maintainer approval and a
  coordinated checkpoint commit.
