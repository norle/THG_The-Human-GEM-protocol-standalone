# THG Protocol Refactoring Progress

This document records completed work and dated validation snapshots for the
refactoring described in `REFACTORING_PLAN.md`. It is historical: the current
status, open decisions, phase gates, and next pull requests live in the plan.

When adding an entry:

- use the date on which the validation was performed;
- describe the behavior or boundary that changed;
- record the exact validation commands and results when they are useful;
- identify any known follow-up work;
- include the commit hash once the checkpoint commit exists.

## 2026-07-27

### Branch-local Git LFS migration and artifact cleanup

- Created checkpoint commits `2750cad` (package and approved artifact policy)
  and `e54c81f` (generated-artifact index cleanup) before rewriting history.
- Rewrote only the local `refactoring-cleanup` branch. The seven approved
  canonical model/reference paths are now LFS pointers; the pre-rewrite tip is
  retained locally as `refactoring-cleanup-pre-lfs` for recovery. No remote refs
  were changed.
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
- Follow-up: coordinate the force-push of the rewritten branch and upload its
  LFS objects before collaborators use the new remote history.

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
