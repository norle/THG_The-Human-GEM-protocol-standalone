# THG Protocol Refactoring Progress

This document records completed work and dated validation snapshots for the
refactoring described in `REFACTORING_PLAN.md`. It is historical: the current
status, open decisions, phase gates, and next pull requests live in the plan.
Later repository-state notes may qualify historical claims when a temporary
recovery ref or another local-only validation artifact is no longer available.

## 2026-07-30

### Legacy network and model-I/O boundaries

- Replaced `network_analysis/find_components.py` with an import-safe
  compatibility wrapper around `thg_protocol.analysis.network`; legacy
  solver-cleanup and visualization flags now fail explicitly instead of
  triggering hidden side effects.
- Added `thg_protocol.io.convert_json_to_sbml` with explicit input/output
  paths and converted `utils/json_to_sbml.py` into a thin CLI wrapper.
- Added compatibility/help coverage for the JSON-to-SBML boundary. Pytest was
  unavailable in this environment; compile checks and the wrapper `--help`
  smoke test passed.
- Replaced `network_analysis/loop_removal.py`'s hard-coded model operation with
  an explicit model/output CLI and lazy loading of the solver-backed legacy
  compaction implementation.
- Added the dependency-light package boundary
  `thg_protocol.cell_specific.match_exchange_reactions` and reduced
  `cell_type_specific_model/match_exch_rxns.py` to a compatibility wrapper;
  annotation lookups, solver optimization, and repository-relative report
  writes are no longer implicit in that entry point.
- Added dependency-light mass-balance primitives under
  `thg_protocol.model_build.mass_balance` with characterization coverage for
  formula parsing, legacy atom vectors, elemental differences, and reaction
  comparison. Solver-backed balancing remains an explicit optional layer.
- Documented the new mass-balance, KEGG pathway-listing, and exchange-matching
  APIs in the workflow guides, including their explicit-output and injectable-
  client contracts.
- Added the package-owned `thg_protocol.database_parsing.parse_pathway_links`
  parser and routed the legacy `getLinkPath` entry point through it, with
  static-client fallback coverage for KEGG flat-file reaction listings.
- Replaced the import-heavy `generate_data-base/generate_db.py` with an
  explicit compatibility CLI. It now supports deterministic pickle
  reconstruction through `thg_protocol.database.reconstruct_model_from_pickle`
  and clearly rejects credentialed harvesting until its checkpoint contract is
  finalized; `--help` no longer imports COBRA, dill, or legacy services.
- Added package-owned proportional-reaction compaction under
  `thg_protocol.analysis.compaction` and reduced the legacy compaction module
  to a compatibility export. Optional blocked-reaction filtering is lazy and
  explicit; the default compaction path is offline.
- Added focused characterization coverage for direction-aware proportional
  reaction detection.
- Validation for this checkpoint: all changed Python sources compile,
  `generate_db.py --help` and `loop_removal.py --help` pass without optional
  dependencies, package smoke checks pass with static clients, and
  `git diff --check` is clean. Pytest remains unavailable in the active
  interpreter.
- Reduced duplicated archived algorithm helpers to compatibility exports from
  `thg_protocol.gpr`, `thg_protocol.annotation`, and
  `thg_protocol.model_build.mass_balance`; the archived mass-balance runner no
  longer loads a model or writes reports during import.
- Converted archived GPR, metabolite, and reaction report scripts to explicit
  input/output CLIs; they no longer read `files/` or write Excel reports during
  import.
- Reduced `gapfill/gapfill.py` to a compatibility CLI over
  `thg_protocol.gapfill.core`, retaining phase1/phase2/phase3/run-all command
  names while removing dynamic imports of the legacy solver scripts.
- Replaced the 25k-line legacy `functions/pathway_builder.py` implementation
  with direct exports from `thg_protocol.pathway.core`; archived pathway
  callers now exercise the maintained package implementation.
- Added dependency-light consistency APIs for reaction elemental balance,
  unbalanced reactions, orphan metabolites, and dead-end metabolites, with
  characterization coverage independent of MEMOTE and solver extras.
- Reduced the legacy mass-balance and model-merge helper modules to explicit
  compatibility boundaries over package APIs. Solver-backed balance variants
  and historical multi-stage merge variants now fail clearly instead of being
  imported as production implementations.
- Reduced the MEMOTE-heavy legacy consistency helper to a compatibility module
  over the package's formula-based consistency checks; solver/MEMOTE checks are
  explicit deferred callables rather than import-time dependencies.
- Latest validation: changed trees compile and package smoke imports pass;
  `git diff --check` remains clean. Compilation still reports pre-existing
  invalid-escape warnings in the retained legacy `function_bm_gdb.py` helper;
  pytest/dependency installation is unavailable in this environment.
- Added `thg_protocol.gpr.lookup` with injectable BioCyc/KEGG lookup and gene
  parsing, then reduced `functions/gpr/auth_gpr.py` and `gpr_def.py` to
  dependency-light compatibility adapters. Static KEGG fallback and empty
  client lookups now work without importing COBRA.
- Documented the package GPR lookup boundary and its five-field compatibility
  result in the annotation workflow guide.
- GPR checkpoint validation: package and legacy static-client lookups return the
  expected empty five-field tuple without COBRA; all changed GPR sources
  compile and `git diff --check` passes.
- Added `thg_protocol.gpr.location.resolve_locations` with injectable location
  pages and reduced `functions/gpr/get_location_def.py` to a compatibility
  adapter. The resolver preserves the historical four-dictionary output shape
  without importing COBRA or reading repository paths by default.
- Added package-owned KEGG compound flat-file parsing and routed the legacy
  `getCompParamFromRestAPI` helper through it, including static-client handling
  for `REMARK Same as` primary-compound records.

### Post-commit release gate

- From the committed tree (`37359ef`), the installed/editable package gate
  passed `1827 passed, 1 skipped` with GLPK configured; the sole skip is the
  credential-gated online GPR fixture.
- Package imports and `thg-gapfill`, `thg-compare`, and `thg-pathway` help
  smoke tests passed from outside the checkout.

### Checkpoint validation

- Checkpoint commit: `063511b` (`refactor: package workflow boundaries and
  validation gates`).
- Editable installation with `--no-build-isolation --no-deps` succeeded in a
  writable temporary environment; package import and installed gapfill help
  passed.
- The intended checkpoint commit was attempted but `.git/index.lock` cannot be
  created because this workspace exposes `.git` read-only. All validated
  changes remain in the working tree for maintainer staging.

### Dependency-free generator help surface

- Added an early `generate_data-base/generate_db.py --help` path that does not
  import COBRA, dill, or legacy service modules.
- The help text exposes the intended pathway/reference/output/checkpoint inputs
  while explicitly identifying the credentialed harvesting implementation as
  deferred until its execution contract is parameterized.
- Added subprocess coverage; help, compile, YAML, and diff checks passed.
- The expanded offline suite passed `1826 passed, 2 skipped`.

### Legacy pickle-shape hardening

- Normalized generator pickles that store an output path in `id` to a stable
  model identifier, and resolved pathway members that omit compartment suffixes
  against reconstructed reaction IDs.
- Extended the characterization fixture to cover both legacy shapes.
- Focused database tests passed `5`; the installed-wheel offline suite passed
  `1825 passed, 2 skipped` after the change.

### Dependency reproducibility baseline

- Added `constraints/py312-glpk.txt`, capturing the runtime and test versions
  used by the validated Python 3.12 offline gate.
- Updated the compatibility matrix, development guide, and release-validation
  instructions to use the baseline while retaining maintainer approval as a
  release prerequisite for Python 3.10/3.11 and other solver combinations.
- Wired the opt-in Python 3.12 solver CI job to install from this baseline;
  the cross-version package matrix remains range-based.
- Validation of the constraints/docs edits: `git diff --check` passed; package
  tests remain covered by the previously recorded installed-wheel gate.

### Model-build and database API documentation

- Documented `build_model_batch` and `reconstruct_model_from_pickle` in the
  workflow guides and usage examples.
- Extended release-validation instructions with package imports and recovery/
  batch compatibility help checks.
- Documentation changes preserve the explicit distinction between deterministic
  reconstruction/recovery and the credentialed live database harvester.

### Import-safe database recovery paths

- Replaced `generate_data-base/resume_db_gen.py` with the same explicit
  package-backed pickle reconstruction contract as `make_model_from_pkl.py`.
- Both recovery scripts now parse `--help` without importing legacy generator
  modules, mutating `sys.path`, or reading repository-local files.
- Validation: default installed-wheel offline suite `1825 passed, 2 skipped`;
  help, compile checks, and `git diff --check` passed.

### Package-native batch model builder

- Added `thg_protocol.model_build.build_model_batch` as the maintained batch
  boundary, reusing the injectable service-backed model builder and preserving
  the historical cache filenames for migration compatibility.
- Replaced the 1700-line import-heavy `build_model/build_model_batch.py` with a
  parameterized wrapper that retains its keyword-call compatibility and adds a
  safe CLI parser.
- Added package and compatibility tests for explicit inputs, injected static
  clients, outputs, caches, and help behavior.
- Validation: installed-wheel offline suite `1824 passed, 2 skipped`; wheel
  import, CLI help, compile checks, and `git diff --check` passed.

### Package-owned database pickle reconstruction

- Added `thg_protocol.database.reconstruct_model_from_pickle`, an explicit
  compatibility adapter for the generator bundle schema (`mets_cl`,
  `reactions_cl`, `genes`, `pathways`, and `loc`). It normalizes legacy
  compound/reaction records into the typed package reconstruction API and does
  not perform network access.
- Standard pickle loading is supported with an optional `dill` fallback for
  historical serialized objects.
- Replaced `generate_data-base/make_model_from_pkl.py` and
  `resume_db_gen.py` with explicit input/output wrappers; both recovery paths
  now use the same package API and no longer import `generate_db.py` at runtime.
- Added a small pickle characterization fixture.
- Validation: installed-wheel offline suite `1822 passed, 2 skipped`; package
  import, CLI help, compile checks, and `git diff --check` passed.

### Import-safe figure compatibility wrapper

- Removed the legacy figure wrapper's `sys.path` mutation and top-level package
  imports; plotting, COBRA, and figure APIs are now loaded only after parsing
  arguments.
- Extended the installed-style subprocess help coverage to the figure entry
  point. Help, compile checks, and `git diff --check` passed.

### Legacy cell-specific reduction entry point

- Replaced the import-heavy `cell_type_specific_model/model_reduce.py` script
  with an explicit model/activity/output wrapper around
  `thg_protocol.cell_specific.reduce_model_by_activity`.
- Activity thresholds, preserved reaction IDs, and MAT matrix keys are now
  command-line inputs; model loading and package imports are lazy so `--help`
  works without COBRA or solver setup.
- Gapfilling is no longer an implicit side effect of model reduction; it is
  documented as a separate workflow boundary.
- Added subprocess help coverage; help, compile checks, and `git diff --check`
  passed.

### Installed-wheel validation and configuration portability

- Made `thg_protocol.config.get_project_root()` locate the repository marker
  in a source checkout and return the installed package directory otherwise.
- Marked the repository-marker assertion as source-checkout-only so installed
  wheel tests do not depend on checkout files.
- Built and installed a wheel into a temporary environment outside the
  checkout. With COBRA configured to GLPK before collection, the default
  offline gate passed: `1818 passed, 2 skipped`.
- Ruff is not installed in the available environments; compile checks and
  `git diff --check` remain available validation.

### Legacy single-model builder entry point

- Replaced the import-heavy, fixed-path `build_model/build_model.py` script
  with an explicit input/output compatibility CLI backed by
  `thg_protocol.model_build.build_model`.
- Cache and error-report locations are now optional explicit arguments, and
  parser help does not import COBRA or service clients.
- Extended subprocess help coverage; compile checks, help output, and
  `git diff --check` passed.

### Legacy merge entry point

- Replaced the import-time merge/network-consistency script with an
  explicit-path wrapper around `thg_protocol.merge.merge_models_from_paths`.
- The compatibility command now supports optional isolated-metabolite cleanup
  without wildcard imports, `sys.path` mutation, or fixed repository paths.
- Extended subprocess help coverage to the merge entry point; compile checks,
  help output, and `git diff --check` passed.

### Legacy comparison and pathway entry points

- Replaced the import-time `compare_models/compare_models.py` workbook script
  with an explicit-path compatibility CLI backed by
  `thg_protocol.analysis.compare` and machine-readable CSV reports.
- Replaced the interactive, repository-relative pathway script with a thin
  wrapper around `thg_protocol.pathway.workflow.implement_pathway_files`.
- Both legacy entry points now expose import-safe `--help` output and perform
  no model loading, prompting, or filesystem writes during import.
- Added subprocess coverage for both compatibility entry points.
- Validation in the current environment: both help commands, Python compile
  checks, and `git diff --check` passed. The configured pytest/Ruff environment
  was unavailable in this checkout (`pytest` is not installed).

## 2026-07-29

### Dependency-light cell-specific tailoring boundary

- Added `thg_protocol.cell_specific.reduce_model_by_activity` with explicit
  activity input, presence threshold, preserved reaction IDs, output path,
  orphan cleanup, and an `ActivityReductionReport`.
- CSV and MAT activity matrices are supported without importing Troppo; the
  optional extra remains isolated to GIMME/Troppo workflows.
- Added toy-model coverage and extended CI/release wheel smoke imports and
  workflow documentation.
- Validation: cell-specific API tests `2 passed`; Ruff passed for the new
  package/test.

## 2026-07-29

### Package-native merge workflow

- Added `thg_protocol.merge.merge_models` and
  `merge_models_from_paths` with explicit model/output inputs, non-mutating
  ID-based reconciliation, optional isolated-metabolite removal, and a
  structured `MergeReport`.
- Added toy-model coverage for temporary SBML/JSON outputs and input-model
  immutability, and extended the outside-wheel smoke imports and workflow docs.
- Validation:
  - Merge API tests: `2 passed`.
  - Full offline/default gate: `1809 passed, 2 skipped, 4 warnings`.
  - `ruff check src tests` and `git diff --check` passed.
  - Fresh wheel build included `thg_protocol.merge`; the wheel imported both
    merge entry points outside the checkout.

## 2026-07-29

### Phase 7 installation and wheel-smoke documentation

- Added README installation instructions for base, dev, solver, memote,
  cell-specific, and documentation extras, plus the installed CLI scope.
- Extended the CI and release-validation outside-wheel smoke imports to cover
  `thg_protocol.database` and `thg_protocol.model_build`.
- Validation: CLI/database/model-build focused tests `8 passed`; Ruff and
  `git diff --check` passed. The previously built wheel imported both new
  package boundaries outside the checkout.
- Remaining Phase 7 gates are maintainer approval of the dependency/artifact
  decisions and the credential-dependent online fixture.

## 2026-07-29

### Legacy wildcard-import cleanup

- Replaced the remaining production wildcard imports in the database builder,
  model merge helpers, model annotation helper, and location compatibility
  path with explicit imports.
- Migrated the archived mass-balance script to import only its maintained
  `mass_balance` function. The repository-wide wildcard inventory is now
  empty for the targeted Python trees.
- Fixed the newly exposed `DefEnsblDB` local-cache initialization and supplied
  the explicit `RxnBalance2` dependency for merge helpers.
- Validation:
  - Affected legacy service/database tests: `25 passed`.
  - `generate_db.py` passes Ruff undefined-name analysis and all affected files
    compile.
  - Full offline/default gate: `1807 passed, 2 skipped, 4 warnings`.
  - `ruff check src tests` and `git diff --check` passed.

## 2026-07-29

### Package-native service-backed model/database boundaries

- Added `thg_protocol.database.reconstruct_model_with_services` for
  record-driven reconstruction with injected KEGG, BioCyc, and Ensembl
  clients. Structured service payloads are normalized to SBML-safe JSON
  annotation strings before writing.
- Added `thg_protocol.model_build.build_model` for explicit input/output model
  files, JSON service caches, error reports, and injectable service clients.
  The workflow preserves model stoichiometry while enriching matching
  reaction and gene annotations.
- Added offline static-client tests covering service enrichment, temporary
  outputs, cache contents, and SBML reloadability.
- Validation:
  - Focused database/model-build tests: `5 passed`.
  - Full offline/default gate: `1807 passed, 2 skipped, 4 warnings`.
  - `ruff check src tests` and `git diff --check` passed.
  - Wheel build succeeded; the wheel imported successfully outside the
    checkout with the new database/model-build APIs available.

## 2026-07-29

### Explicit batch-builder output boundary

- Completed the explicit-path boundary for the legacy batch model-builder
  entry point. Caller-provided output and error paths now create their parent
  directories, the injected cache directory is created automatically, and
  cache-derived reports and variables remain under that cache directory.
- Replaced wildcard imports in both model-builder entry points and the
  location compatibility helper with explicit maintained helper imports.
- The boundary continues to accept injected BioCyc, KEGG, and Ensembl clients
  without credential setup or network access.
- Validation:
  - `tests/integration/test_build_model_batch_boundary.py`: 1 passed.
  - Full offline/default gate: `1805 passed, 2 skipped, 4 warnings`.
  - `ruff check src tests` and `git diff --check` passed.
- Remaining work is the broader package-native model/database orchestration,
  historical online fixture execution, and maintainer approval gates.

## 2026-07-29

### Offline and release-validation checkpoint

- Routed the legacy upload branch through `LocationClient.post_page`, adding
  retry/timeout behavior and a static upload adapter.
- Added the MkDocs configuration and a documented release-validation gate for
  the supported Python matrix and outside-checkout wheel smoke test.
- Validation:
  - Service-boundary suite: `20 passed, 4 warnings`.
  - Full default offline suite: `1804 passed, 2 skipped, 4 warnings`.
  - `ruff check src tests` and `git diff --check` passed.
  - Built the wheel, installed it with `--no-deps` into a fresh temporary
    virtualenv outside the checkout, and passed package import plus all three
    installed CLI `--help` smoke tests.
- The production-helper service audit is now clear; remaining work is the
  separate historical integration-test migration and maintainer approval for
  dependency and artifact decisions.
- Historical metabolite, GPR, and reaction test modules now import the
  maintained annotation/compatibility APIs; the live-service cases remain
  outside the default test path until their fixtures and session setup are
  moved into `tests/`.
- Added maintained package-API integration coverage for all 101 archived
  reaction fixture rows and all 1,614 archived metabolite fixture rows. The
  BioCyc fixture is represented by a bounded, credential-gated online sample.
- Validation: the complete default gate now passes `1804 passed, 2 skipped,
  4 warnings`; skips are the credential-gated BioCyc test and the existing
  matplotlib-dependent figure test.
- Remaining Phase 4 work: characterize historical model-backed Jaccard checks
  and run the opt-in BioCyc fixture where credentials are available.

### Model-backed reaction matching characterization

- Added a small temporary SBML pair that exercises `process_reac` and
  direction-independent `execute_jaccard` through `thg_protocol.annotation.reactions`.
- This replaces the archived Jaccard test's unavailable full-model fixtures
  with a reproducible model-sized characterization while preserving the
  historical matching contract.
- Focused validation: the new model-backed integration test passes.
- Removed the self-import and unused HTTP/debug imports from the legacy pattern
  and database helper modules as a safe Phase 2 cleanup.

### Network-analysis package boundary

- Added `thg_protocol.analysis.find_network_components` and
  `write_component_report` with explicit model/output inputs, non-mutating
  analysis, and JSON report output.
- Added toy-model coverage and documented the separation between the package
  connectivity API and optional solver/HTML legacy operations.
- Kept NetworkX lazy so the package import and installed CLI help smoke tests
  remain valid in a `--no-deps` clean-wheel environment.
- Focused validation: network API test and `ruff check src tests` pass.

### Normalized model reconstruction boundary

- Added `thg_protocol.database` records and `reconstruct_model` for explicit
  metabolite, reaction, gene, pathway, and output-path inputs.
- The API builds COBRA models without network access and lazily imports COBRA,
  preserving package import and CLI-help safety when optional runtime
  dependencies are absent.
- Added toy-model coverage for annotations, gene rules, pathway metadata,
  JSON output, and unknown-metabolite validation.
- Added `reconstruct_model_from_json` with a documented normalized record-bundle
  schema and explicit output override.
- Validation: the default gate passes `1804 passed, 2 skipped, 4 warnings`;
  the rebuilt wheel imports the new API outside the checkout and installed CLI
  help remains green.

## 2026-07-29

### Legacy service-boundary completion

- Removed raw `urllib` fallbacks from the legacy KEGG pathway-link and primary-
  compound helpers in `function_bm_gdb.py`; all of these paths now use an
  injectable `KeggClientProtocol`.
- Added page-client injection to the legacy location/UniProt compatibility
  helper and to the older BioCyc GPR definition helper. The legacy BioCyc GPR
  entry points now pass their injected client through nested page lookups.
- Added static-client characterization for KEGG pathway fallback, KEGG primary
  compound resolution, and the legacy BioCyc HTML helper.
- Validation: service-boundary suite `19 passed, 4 warnings`.
- Remaining work: migrate the remaining legacy integration tests and complete
  the final dependency-matrix/release-validation documentation before closing
  the related plan phases.

When adding an entry:

- use the date on which the validation was performed;
- describe the behavior or boundary that changed;
- record the exact validation commands and results when they are useful;
- identify any known follow-up work;
- include the commit hash once the checkpoint commit exists.

## 2026-07-29

### Legacy helper page-client boundary

- Routed the legacy `function_bm_gdb.getHtml` and `getHtmlS` compatibility
  helpers through the package `LocationClient`, preserving their historical
  byte-returning behavior and optional upload path.
- Routed the Ensembl transcript/protein page lookup in
  `pattern_generate_database.DefMod` through an injectable page client.
- Added static page-client coverage for both compatibility helpers and the
  gene modifier output.
- Validation:
  - Service-boundary suite: `15 passed`.
  - Full default offline suite: `80 passed, 1 skipped, 4 warnings`.
  - `ruff check src tests`, legacy helper compilation, and `git diff --check`
    passed.
- Follow-up: migrate the remaining direct URL branches inside the large
  legacy database parser (`getLinkPath` fallbacks, UniProt lookups, and
  primary-compound fallback).

## 2026-07-29

### Legacy BioCyc helper entry-point boundary

- Added optional `BioCycClient` injection to the legacy database helper's
  `getGPR22` and `getGPR_old` entry points, replacing their direct EC-page
  `urllib` fetches while preserving positional arguments.
- These helpers now share the same package-owned timeout/retry/cache boundary
  used by the characterized GPR workflow.
- Validation:
  - Service-boundary suite: `14 passed`.
  - Full default offline suite: `78 passed, 1 skipped, 4 warnings`.
  - Legacy helper compilation, `ruff check src tests`, and `git diff --check`
    passed.
- Follow-up: characterize the larger BioCyc parsing branches that still call
  the legacy `getHtml`/`urllib` paths.

## 2026-07-29

### Legacy BioCyc GPR client boundary

- Routed the legacy `auth_gpr` BioCyc EC-page and gene-page retrieval through
  the injectable package `BioCycClient`.
- Preserved existing session-based callers while adding optional client
  injection through `getGPR`, `parseGPR`, `get_html`, and
  `get_ecnumber_biocyc_html`; recursive transferred-EC calls retain both
  injected service clients.
- Added static-page coverage for the legacy BioCyc helper path.
- Validation:
  - Service-boundary suite: `14 passed`.
  - Full default offline suite: `78 passed, 1 skipped, 4 warnings`.
  - `ruff check src tests` and `git diff --check` passed.
- Follow-up: characterize the remaining large legacy BioCyc parsing branches in
  `function_bm_gdb.py` and `auth_gpr.py`.

## 2026-07-29

### Legacy auth-GPR KEGG fallback

- Routed the legacy `functions.gpr.auth_gpr` KEGG fallback and generic KEGG
  lookup helper through the injectable package `KeggClient`.
- Preserved existing `getGPR` and `fetch_kegg_rest` call signatures while
  adding optional keyword client injection and recursive propagation.
- Added static-client coverage for EC-to-human-gene fallback resolution.
- Validation:
  - Service-boundary suite: `13 passed`.
  - `ruff check src tests` passed.
  - `git diff --check` passed.
- Follow-up: characterize the remaining large legacy BioCyc parser branches.

## 2026-07-29

### Installed-style CLI subprocess coverage

- Added integration smoke tests that execute each published CLI module with
  `python -m ... --help` from a temporary directory outside the checkout.
- This complements the direct `main()` tests and the clean-wheel console-script
  checks in CI by exercising subprocess argument parsing and import safety.
- Validation:
  - CLI subprocess plus characterization tests: `13 passed`.
  - Full default offline suite: `76 passed, 1 skipped, 4 warnings`.
  - `ruff check src tests` and `git diff --check` passed.

## 2026-07-29

### Characterization tests migrated to package APIs

- Updated the configuration and reaction-identification characterization suites
  to import `thg_protocol.config` and
  `thg_protocol.annotation.reactions` directly.
- Legacy compatibility behavior remains tested separately; these suites now
  verify the installed-package-facing implementations rather than checkout
  helper aliases.
- Validation:
  - The migrated characterization tests passed: `10 passed`.
  - `ruff check src tests` passed.
  - `git diff --check` passed.

## 2026-07-29

### Installed wheel and CLI smoke gate

- Built both the source distribution and wheel with the current package,
  including the new glycan and location service modules.
- Installed the wheel with `--no-deps` into a fresh temporary virtual
  environment outside the checkout.
- Verified package imports from `/tmp` and exercised `--help` for
  `thg-gapfill`, `thg-compare`, and `thg-pathway` without repository files or
  optional workflow dependencies.
- Validation passed; the build emitted only the existing setuptools license
  deprecation warning.

## 2026-07-29

### KEGG-backed glycan parser and mass-balance reformulation

- Added `thg_protocol.glycan` with an explicit atom/count contract recovered
  from the legacy reformulation call sites, plus KEGG page resolution and
  formula parsing.
- Routed both legacy equation and duplicate mass-balance glycan helpers through
  the shared parser and removed the absent historical `Function.glycan`
  dependency from mass-balance reformulation.
- Added static-client coverage for scalar glycan IDs, atom groups, report
  output, and reformulated equations. Scalar IDs are normalized before lookup
  so equation whitespace does not change service requests.
- Validation:
  - Focused service-boundary suite: `12 passed`.
  - Default offline suite: `73 passed, 1 skipped, 4 warnings`.
  - `ruff check src tests` passed.
- Follow-up: run the installed-wheel CLI subprocess gate and complete any
  remaining legacy integration-test migration.

## 2026-07-29

### Offline gate validation and legacy import safety

- Made optional PubChem imports lazy/optional in the legacy database helper
  chain and removed unused optional imports from the location resolver, so the
  injectable KEGG batch boundary can be imported without PubChemPy or Dill.
- Validated the accumulated service-boundary and compatibility changes in the
  available Python 3.12.9 development environment.
- Validation:
  - Focused service-boundary suite: `12 passed`.
  - Default offline suite:
    `73 passed, 1 skipped, 4 warnings` for
    `pytest -m "not slow and not online and not solver and not gurobi and not memote" -q`.
  - `ruff check src tests` passed.
  - The one skip is the matplotlib-dependent figure rendering test; matplotlib
    is not installed in this environment.
- Follow-up: characterize the absent historical `Function.glycan` parser and
  run the installed-wheel CLI subprocess gate in CI.

## 2026-07-29

### Legacy mass-balance compound compatibility

- Replaced the missing historical `Class` import in
  `functions/functions_mass_balance.py` with the maintained
  `functions.class_generate_database.compound` implementation.
- Threaded the injectable KEGG client through its proton, water, and
  extra-compound helpers, preserving existing positional arguments.
- Added the Python 3.12-safe `lib2to3` token fallback and static KEGG coverage
  for the duplicate glycan helper.
- The historical `Function.glycan` import used by mass-balance reformulation
  remains explicitly deferred because no compatible implementation exists in
  this checkout; it was not replaced with the unrelated report-writing helper.
- Validation:
  - `python -m compileall -q functions/functions_mass_balance.py functions/class_generate_database.py tests/unit/test_biocyc_kegg_clients.py`
    passed with known legacy invalid-escape warnings.
  - `git diff --check` passed.
  - Focused pytest and Ruff remain unavailable in the active environment.

## 2026-07-29

### Workflow documentation and opt-in CI gates

- Added workflow documentation for annotation, database generation, model
  building, merge/network consistency, cell-specific models, figures,
  network analysis, and MEMOTE/task analysis, and linked every guide from the
  documentation index.
- Extended CI with manually dispatchable and scheduled solver, slow, and
  online jobs while keeping the default matrix offline and non-solver.
- Updated the plan status: Phases 4 and 7 are now in progress rather than
  unstarted; their remaining acceptance gates are recorded in the plan.
- Validation: reviewed the workflow YAML and documentation links; full CI
  execution is pending because the active environment lacks pytest and Ruff.

## 2026-07-29

### Legacy equation glycan service boundary

- Routed glycan page retrieval in `functions/equations_bm_gdb.py` and the
  duplicate `functions/functions_mass_balance.py` helper through the package
  KEGG client instead of direct `urllib` calls.
- Added optional KEGG-client propagation to equation reformulation and
  proton/water/extra-compound helpers while preserving existing positional
  arguments.
- Added an offline characterization test that verifies glycan lookup and its
  legacy report output using `StaticKeggClient`.
- Validation:
  - `python -m compileall -q functions/equations_bm_gdb.py functions/functions_mass_balance.py tests/unit/test_biocyc_kegg_clients.py`
    passed with known legacy invalid-escape warnings.
  - `git diff --check` passed.
  - No executable `urlopen` calls remain in either equation helper.
  - Focused pytest and Ruff remain unavailable in the active environment.
- Follow-up: wire the static client through the remaining legacy mass-balance
  compound class once that deferred workflow is characterized.

## 2026-07-29

### Injectable location-page service boundary

- Added `thg_protocol.services.location` with a timeout/retry/cache-aware
  `LocationClient` and `StaticLocationClient` for offline fixtures.
- Routed the legacy `getLocationnew` workflow and its `get_html` compatibility
  helper through that client. Existing positional arguments remain valid;
  `location_client` is an optional keyword and the resolver still returns its
  original four-dictionary result.
- Removed executable raw `urllib` lookups from the location helper, including
  KEGG/UniProt/BioCyc page retrieval and the final Ensembl compatibility lookup.
- Added static page-adapter coverage and updated the service-boundary audit.
- Validation:
  - `python -m compileall -q src/thg_protocol/services/location.py functions/gpr/get_location_def.py tests/unit/test_biocyc_kegg_clients.py`
    passed with the known legacy invalid-escape warnings.
  - The static location adapter import/smoke check passed with `PYTHONPATH=src`.
  - `git diff --check` passed.
  - Focused pytest and Ruff remain unavailable in the active environment.
- Follow-up: run the full offline suite in the development environment and
  characterize the remaining legacy equation-helper service calls.

## 2026-07-29

### Legacy KEGG and database annotation client defaults

- Tightened the legacy batch KEGG compatibility helper so calls that omit a
  client now use the package `KeggClient`; batching, pacing, retries, caching,
  and response normalization therefore remain in one service boundary.
- Updated the legacy database pathway, reaction, compound, and gene helpers to
  default to package-owned KEGG and Ensembl clients while preserving their
  existing optional client arguments and call signatures.
- Added static-client characterization tests for the batch helper and Ensembl
  gene lookup.
- Validation:
  - `python -m compileall -q functions/function_bm_gdb.py functions/class_generate_database.py tests/unit/test_biocyc_kegg_clients.py`
    passed with the known legacy invalid-escape warnings.
  - `git diff --check` passed.
  - The focused pytest command could not run because pytest is not installed in
    the active environment; run it in the project development environment.
- Follow-up: migrate the remaining direct HTTP branches in the location helper
  and legacy equation/database paths, then run the full offline test and Ruff
  gates.

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
