# THG Protocol Refactoring and Packaging Plan

This document captures the current maintainability issues in the repository and
lays out an implementation plan for turning it into a maintainable Python
package with tests, documentation, and large-file handling through Git LFS.

This document is the authoritative source for current decisions, open work,
phase gates, and next pull requests. Dated implementation notes and validation
snapshots belong in `REFACTORING_PROGRESS.md`.

## Plan Maintenance

- Update the "last reviewed" date whenever the status table or open decisions
  change.
- Keep only pending work and durable architectural decisions in this file.
- Record completed implementation details and historical test counts in
  `REFACTORING_PROGRESS.md`.
- Remove completed entries from "Next Pull Requests" instead of retaining them
  as historical suggestions.
- Do not mark a phase complete until every acceptance criterion for that phase
  has passed and the result has been recorded in the progress log.

## Commit and Pull Request Checkpoints

Use frequent commits as validated recovery points, not as a record of every
small edit. Agents are expected to commit autonomously once a coherent,
reviewable boundary has been implemented and its available validation has
passed; they should not wait for a separate user request to commit.

Prefer one commit per independently testable module, workflow, service
boundary, or documentation gate. As a practical upper bound, split work before
it combines unrelated subsystems or becomes difficult to review. Commit before
moving on to the next boundary, and make at least one checkpoint during any
work session that completes a validated boundary.

Never include unrelated working-tree changes in an agent-created commit. If a
validation tool is unavailable, run the strongest available checks, record the
limitation in the progress log, and keep the commit narrowly scoped.

- Commit the approved baseline inventories and decisions before moving more
  code.
- Commit packaging and test infrastructure after the clean-wheel gate passes.
- Commit each characterized module move together with its tests and any legacy
  compatibility wrapper. Do not leave either import path broken between
  commits.
- Commit each workflow API separately from unrelated workflows. Add its CLI in
  the same commit only when import-safety and `--help` tests pass; otherwise add
  the CLI in a later focused commit.
- Commit the reviewed artifact inventory before any Git LFS tracking or index
  removal. Keep LFS pointer changes and generated-artifact removals in a
  dedicated commit.
- Commit documentation and CI changes alongside the behavior or gate they
  describe when practical, rather than deferring all documentation to the end.
- Record the checkpoint commit hash in `REFACTORING_PROGRESS.md` after
  validation.

Before each checkpoint commit:

1. Review `git diff` and exclude unrelated working-tree changes.
2. Run the validation commands for the affected phase.
3. Update the current status and next pull requests in this plan.
4. Add a dated progress-log entry with the validation result.
5. Use a message that names the completed boundary, for example
   `refactor: move reaction annotation API`.

History rewrites such as `git lfs migrate import` are coordinated repository
operations, not normal checkpoint commits. They require explicit maintainer
approval, recorded affected refs, and fresh-clone verification.

## Goals

- Make the repository installable as a Python package.
- Make reusable workflow logic available through a documented Python API.
- Keep command-line workflows usable during the migration, but treat CLIs as
  thin wrappers around stable Python APIs rather than the primary interface.
- Move reusable logic out of top-level scripts into importable modules.
- Add tests before and during refactoring so behavior changes are visible.
- Move large model/data artifacts to Git LFS or remove generated artifacts from
  git entirely.
- Improve documentation for installation, usage, development, and data/model
  management.

## Current Issues

### Repository Layout (baseline reviewed 2026-07-13)

- Source code, scripts, generated models, logs, reports, notebooks, caches, and
  backups are mixed together.
- Package metadata and central pytest configuration now exist in
  `pyproject.toml`; the remaining Phase 1 gate is validating them against an
  installed wheel. Older implementation observations are retained in
  `REFACTORING_PROGRESS.md`.
- Several directories are not valid or ideal Python package names:
  - `generate_data-base` contains a hyphen.
  - `merge_metabolic_netowrks_and_network_consistency` is misspelled.
  - `functions` is too generic for a public package namespace.
- There is a stray `functions/__init.py__` next to `functions/__init__.py`.
- Large generated outputs and platform/editor files are present, including
  `.DS_Store`, notebook checkpoints, log files, and Excel lock files.

### Import and Execution Model

- Many scripts modify `sys.path` to import local modules.
- Several scripts assume repository-relative `models/`, `files/`, and `logs/`
  paths.
- Some modules perform heavy work at import time instead of exposing functions
  and using a guarded `main()` entry point.
- There are many wildcard imports from `functions.*`, making dependencies and
  public APIs hard to understand.
- Many scripts write directly into fixed repository folders, which makes tests
  and repeated runs harder to isolate.
- The repository has some script-level CLI support, but not a cohesive installed
  command-line interface. For example, `gapfill/gapfill.py` and
  `implement_pathway/pathway_implementation.py` expose useful `--help` output,
  while other workflows still run work at import/top level or fail before help
  because heavy dependencies are imported before argument parsing.

### Code Maintainability

- Core modules are very large and combine unrelated responsibilities.
- Several workflows mix configuration, I/O, external API calls, model mutation,
  logging, and report generation in the same script.
- There are many print/debug statements and `pdb` imports in production code.
- Dependency versions are split across subdirectories and sometimes conflict
  with the current Python version.
- External services such as BioCyc, KEGG, PubChem, and Ensembl are called
  directly from workflow code, which makes testing unreliable.

### Tests

- Earlier review could not verify test collection because `pytest` was not
  installed in the active environment. Current validation must use the dev
  extra and record the environment and command used.
- Existing tests often import copied helper files from test directories instead
  of testing production modules.
- Some tests depend on live external services.
- Some fixtures are very large SBML/XML files.
- There is no central test marker policy for slow, online, solver-dependent, or
  memote tests.

### Large Files

- The repository currently tracks roughly 963 MB of files.
- About 50 tracked files larger than 1 MB account for roughly 944 MB.
- No files are currently tracked by Git LFS.
- `.gitignore` contains entries for `models`, `files`, and `logs`, but many
  files in those directories are already tracked, so the ignore rules do not
  affect them.

## Target Package Structure

Use a `src/` layout so imports are tested against the installed package rather
than accidentally resolving local files.

```text
.
├── pyproject.toml
├── README.md
├── REFACTORING_PLAN.md
├── REFACTORING_PROGRESS.md
├── docs/
│   ├── index.md
│   ├── installation.md
│   ├── usage.md
│   ├── development.md
│   └── data-and-model-files.md
├── src/
│   └── thg_protocol/
│       ├── __init__.py
│       ├── config.py
│       ├── io/
│       ├── annotation/
│       │   ├── metabolites.py
│       │   └── reactions.py
│       ├── gpr/
│       ├── database/
│       ├── model_build/
│       ├── merge/
│       ├── gapfill/
│       ├── cell_specific/
│       ├── pathway/
│       │   ├── __init__.py
│       │   ├── core.py
│       │   └── cli.py
│       ├── analysis/
│       ├── figures/
│       └── cli/
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── data/
│   └── conftest.py
└── examples/
```

Suggested mapping from existing folders:

| Current path | Target package area |
| --- | --- |
| `functions/function_metabolite_identification.py` | `thg_protocol.annotation.metabolites` |
| `functions/function_reac_identification.py` | `thg_protocol.annotation.reactions` |
| `functions/gpr/` | `thg_protocol.gpr` |
| `generate_data-base/` | `thg_protocol.database` |
| `build_model/` | `thg_protocol.model_build` |
| `merge_metabolic_netowrks_and_network_consistency/` | `thg_protocol.merge` |
| `gapfill/` | `thg_protocol.gapfill` |
| `cell_type_specific_model/` | `thg_protocol.cell_specific` |
| `implement_pathway/` | `thg_protocol.pathway` |
| `compare_models/` | `thg_protocol.analysis.compare` |
| `generate_figures/` | `thg_protocol.figures` |
| `network_analysis/` | `thg_protocol.analysis.network` |
| `utils/` | `thg_protocol.io` or `thg_protocol.utils` |

`thg_protocol.pathway` is intentionally a package, not a single
`pathway.py` module. Before adding the `thg-pathway` command, move the current
`src/thg_protocol/pathway.py` implementation to `pathway/core.py` and re-export
its stable public helpers from `pathway/__init__.py`. This preserves the
`thg_protocol.pathway` import path while leaving room for `pathway.cli` and
future workflow-specific modules.

## Packaging Plan

### Minimal `pyproject.toml`

Start with a conservative package definition and expand dependency groups as the
code is migrated. Do not add console scripts until the corresponding command has
an import-safe module, a stable Python API, argument parsing, and at least a help
smoke test.

```toml
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "thg-protocol"
version = "0.1.0"
description = "Protocol tools for constructing and analyzing human genome-scale metabolic models."
readme = "README.md"
requires-python = ">=3.10,<3.13"
license = { file = "LICENSE" }
authors = [
  { name = "THG contributors" }
]
dependencies = [
  "cobra>=0.26",
  "numpy",
  "pandas",
  "scipy",
  "requests",
  "python-libsbml",
  "tqdm",
]

[project.optional-dependencies]
dev = [
  "build",
  "pytest",
  "pytest-cov",
  "ruff",
  "black",
]
memote = [
  "memote",
]
solver = [
  "swiglpk",
]
cell-specific = [
  "troppo",
  "pathos",
]
docs = [
  "mkdocs",
  "mkdocs-material",
]

# Add [project.scripts] entries only as commands are migrated.
# Likely first stable commands:
# thg-gapfill = "thg_protocol.gapfill.cli:main"
# thg-compare = "thg_protocol.analysis.compare_cli:main"
# thg-pathway = "thg_protocol.pathway.cli:main"
```

### Packaging Validation

Do not add `src` to pytest's `pythonpath`: doing so bypasses installation and
can hide packaging defects. Unit tests should run against an installed package.
During the transition, checkout-local tests may still resolve the legacy
top-level `functions` namespace, but clean-environment tests must not depend on
that accidental import path. Migrate those tests to `thg_protocol` APIs, or
explicitly package a documented compatibility namespace before removing the
legacy imports.
In addition to editable-install checks during development, CI should build both
the source distribution and wheel, install the wheel into a clean environment,
change to a directory outside the repository, and run package-import and CLI
smoke tests there. This catches missing modules, package data, and entry points
that an editable install can mask.

### Python API Principles

- The Python API is the primary interface for reusable logic.
- Core functions should accept explicit inputs such as models, paths, client
  objects, configuration objects, and output directories.
- Core functions should return structured results or write only to explicitly
  provided paths.
- Every promoted public function must document its input model type, output
  schema, mutation behavior, and error behavior. Do not expose an untyped mix
  of COBRA models and ad-hoc dictionaries without an explicit compatibility
  contract.
- Importing a module should not load large models, write files, open network
  sessions, or start long-running work.
- External services should be isolated behind client modules and injected into
  workflow functions where practical. Each service boundary must define a small
  client protocol, a production implementation, and a fake/static implementation
  for tests. The client owns timeouts, retries, rate limits, caching,
  authentication, and response normalization; workflow code must not mutate
  global proxy state or call service SDKs directly.
- Any Phase 2 or Phase 3 migration that touches BioCyc, KEGG, PubChem, or Ensembl
  must establish that client boundary as part of the same migration; it must not
  stabilize a new public API around direct network calls while waiting for a
  later cleanup phase.
- Existing import paths may remain temporarily as thin compatibility wrappers
  during migration, but new code should import from `thg_protocol`.

### CLI Principles

- Add CLI commands for stable, repeatable workflows, not for every helper or
  exploratory script.
- Prefer Python APIs for lower-level annotation, matching, mass-balance, model
  manipulation, and analysis functions.
- Each workflow should expose a `main(argv: list[str] | None = None) -> int`.
- CLI wrappers should only parse arguments, load configuration, call package
  functions, and return an exit code.
- All input/output paths should be arguments or config values.
- No workflow should write to `models/`, `files/`, or `logs/` unless explicitly
  requested.
- `--help` should work without importing optional heavy dependencies or loading
  models.
- Every installed CLI command should have a smoke test for `--help`.
- Help smoke tests must run with optional heavy dependencies absent, proving
  argument parsing does not eagerly import solvers, model files, or network
  clients.
- Good initial CLI candidates are `thg-gapfill`, `thg-compare`, and
  `thg-pathway`. Defer `thg-build` and `thg-generate-db` until their inputs,
  outputs, credentials, and dependency requirements are cleanly parameterized.

## Git LFS and Artifact Plan

### Decide File Ownership

Use three categories:

1. **Source-controlled text**: Python, Markdown, config templates, small JSON
   examples, small TSV/CSV fixtures.
2. **Git LFS artifacts**: canonical model files and large curated datasets that
   are required for reproducible workflows.
3. **Ignored generated artifacts**: logs, temporary outputs, checkpoints, local
   caches, backup folders, generated reports, and exploratory figures.

### Recommended `.gitattributes`

Do not add broad LFS rules until file ownership has been decided. Prefer a
targeted `.gitattributes` generated from the artifact inventory, with canonical
large model/data files tracked by LFS and small fixtures kept as normal text.

A starting point might look like this after ownership is decided. Use explicit
approved paths from the artifact inventory, not broad directory rules:

```gitattributes
models/<approved-canonical-model>.xml filter=lfs diff=lfs merge=lfs -text
memote_and_task_analysis/models/<approved-memote-model>.xml filter=lfs diff=lfs merge=lfs -text
files/<approved-large-dataset>.gct filter=lfs diff=lfs merge=lfs -text
```

Be careful with broad `*.xml`, `*.json`, `*.csv`, `*.xlsx`, or `*.pdf` LFS rules
because the repository also contains small configs, useful text fixtures,
published reports, and documentation assets. Prefer targeted rules for known
large canonical artifacts. Do not use broad rules such as `models/**` unless the
whole directory has been reviewed and approved as canonical LFS content.

### Recommended `.gitignore` Additions

```gitignore
# Python
__pycache__/
*.py[cod]
.pytest_cache/
.coverage
htmlcov/
*.egg-info/
build/
dist/

# Local environment
.env
.venv/
venv/

# Generated outputs
logs/
backups/
*.log
run_full.log
run_full_db.log
run_subset.log

# Local/editor files
.DS_Store
**/.DS_Store
**/.ipynb_checkpoints/
~$*

# Caches and checkpoints
files/caches/
files/*cache*
files/*checkpoint*
*.tmp
```

### LFS Migration Steps

Run this on a dedicated branch. The history rewrite should be coordinated with
all collaborators.

```bash
git checkout -b chore/package-refactor-plan
git lfs install
# After reviewing the artifact inventory, track only approved canonical artifacts.
# Replace the placeholders below with exact paths from the approved inventory.
git lfs track "models/<approved-canonical-model>.xml"
git lfs track "memote_and_task_analysis/models/<approved-memote-model>.xml"
git lfs track "files/<approved-large-dataset>.gct"
git add .gitattributes
git commit -m "Track large model artifacts with Git LFS"
```

If existing history must be cleaned:

```bash
# Replace this example with the reviewed comma-separated path list.
git lfs migrate import --include="models/<approved-canonical-model>.xml,memote_and_task_analysis/models/<approved-memote-model>.xml,files/<approved-large-dataset>.gct"
```

After migration:

```bash
git lfs ls-files
git status
```

The approved artifact inventory must record each path's ownership, provenance,
size, SHA-256 checksum, and whether it is expected in a normal clone. A
fresh-clone check must verify both the LFS pointer checkout and fetched content
against those checksums. Record rewritten branches and tags before publishing
rewritten refs.

## Testing Strategy

### Test Categories

- **Unit tests**: pure functions, small inputs, no network, no large models.
- **Fixture integration tests**: small COBRA models stored in `tests/data`.
- **Workflow smoke tests**: one tiny end-to-end example per CLI.
- **Slow tests**: full or near-full model workflows.
- **Online tests**: BioCyc, KEGG, PubChem, Ensembl.
- **Solver tests**: tests that require GLPK, Gurobi, or another solver.
- **Memote tests**: custom memote/task analysis.

### Pytest Markers

Add central markers in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-ra --strict-markers"
markers = [
  "slow: long-running model or workflow test",
  "online: requires external network service",
  "solver: requires an optimization solver",
  "gurobi: requires Gurobi",
  "memote: requires memote",
]
```

Default CI should run:

```bash
pytest -m "not slow and not online and not solver and not gurobi and not memote"
```

Run solver-dependent tests in a separate job that installs `.[solver]`.
Gurobi tests should remain a distinct opt-in job because they also require a
licensed solver installation.

### Priority Test Coverage

Start with characterization tests before moving code. These tests lock current
behavior and reduce refactoring risk. Each module-move PR should add or preserve
tests for the behavior it moves.

1. GPR parsing and sanitization.
2. Metabolite identification and annotation helpers.
3. Reaction parsing, Jaccard matching, and annotation helpers.
4. Mass-balance equation helpers.
5. Compartment mapping and ID normalization.
6. Pathway builder functions.
7. JSON/SBML load/save helpers.
8. Gapfill phase functions using tiny toy models.
9. Network analysis functions using toy graphs/models.
10. CLI smoke tests with temporary directories.

### Test Data Rules

- Keep unit test fixtures small and text-readable where possible.
- Create tiny COBRA models in Python fixtures when practical.
- Use large full models only in marked integration or slow tests.
- Do not require online services in default tests.
- Mock external API clients and provide recorded/static response fixtures.
- Maintain a supported Python/dependency compatibility matrix and use a
  constraints or lock file for CI and release validation; unbounded dependency
  ranges alone are not sufficient for reproducible model and solver workflows.

## Documentation Plan

Create documentation in `docs/` and keep the README focused on orientation.

Recommended docs:

- `docs/installation.md`: supported Python versions, solver setup, optional
  extras, editable install.
- `docs/usage.md`: Python API examples first, followed by CLI examples for
  stable installed commands.
- `docs/development.md`: test commands, linting, package layout, release steps.
- `docs/data-and-model-files.md`: what lives in Git LFS, what is ignored, where
  to place local/generated files.
- `docs/workflows/`: one page per major pipeline:
  - metabolite/reaction identification
  - database generation
  - model build
  - merge/network consistency
  - gapfill
  - pathway implementation
  - cell-specific models
  - memote/task analysis
  - comparison and figures

## Implementation Plan and Status

### Current Status

Last reviewed: 2026-07-30

The latest fully validated default offline/non-solver checkpoint passed 1827 tests
with two expected skips and `ruff check src tests`. The current tree includes the characterized
metabolite/reaction workflow and its PubChem service boundary in addition to the
earlier service-boundary tests. The retry annotation compatibility script now
delegates to that package API and injected client. The shared Python 3.12.9
environment passed the
default offline suite with 68 tests and one matplotlib-dependent skip, and
`ruff check src tests` passed. The package has passed the local clean-wheel and
outside-checkout smoke gate. Gapfill and
comparison APIs/CLIs now join the pathway workflow, and Ensembl annotation is
behind an injectable package client. BioCyc and KEGG GPR lookups now use
injectable package clients. The characterized batch model-builder workflow now
also receives package clients for KEGG reaction prefetch, BioCyc XML lookups,
and Ensembl annotation. The production-helper service audit is now clear; any
new deferred workflow must continue to receive injected clients. The single-model builder now
passes package clients through its GPR, Ensembl prefetch, and
location-annotation paths. The characterized database-builder workflow now
passes package clients through its KEGG page/entry, GPR, and Ensembl annotation
paths. The report-driven annotation figures and model-derived comparison
figures are now behind import-safe package APIs with a separate plotting extra.
The legacy figure script is an explicit-path wrapper; supplied MEMOTE and
algorithm score data are required for those optional charts rather than being
hard-coded. A service-boundary audit records the production-helper boundary;
historical fixture migration remains a Phase 4 task.

| Phase | Status | Remaining gate |
| --- | --- | --- |
| Phase 0 | Complete | Dependency/artifact policy and source-only legacy namespace decisions were recorded before the completed branch-local LFS migration. |
| Phase 1 | Complete | Baseline CI and local clean-wheel/outside-checkout validation are recorded in the progress log; source-only legacy compatibility tests are an explicit exception to the package-test import rule. |
| Phase 2 | In progress | The targeted wildcard-import inventory is clean; continue characterized helper moves and reduce remaining legacy utility coupling across the deferred workflows. |
| Phase 3 | In progress | Gapfill, pathway, comparison, figure, annotation, network-analysis, merge, cell-specific tailoring, and normalized reconstruction APIs are import-safe; package-native service-backed model/database boundaries now exist, while full legacy script replacement remains. |
| Phase 5 | Complete | PubChem, Ensembl, BioCyc, KEGG, location pages, and legacy upload paths use package-owned injectable clients; the offline gate, static-client characterization, and production-helper audit pass. |
| Phase 6 | Complete | The approved targeted LFS policy and generated-artifact index cleanup passed on `refactoring-cleanup`; fresh-clone checksums are recorded in the progress log. |
| Phase 4 | In progress | Package API/CLI tests and temporary-output coverage exist; reaction/metabolite historical fixtures and a small model-backed Jaccard characterization are migrated, while credential-gated GPR validation remains. |
| Phase 7 | In progress | Workflow documentation, installation instructions, MkDocs configuration, release-validation instructions, and opt-in solver/slow/online CI jobs are present; obtain final maintainer approval for the supported dependency matrix and artifact decisions. |

### Open Decisions

The following decisions block phase acceptance or determine public
compatibility:

- Approve the supported Python and dependency matrix, including optional
  workflow extras.
- The legacy `functions` namespace is source-checkout-only; wheels expose
  `thg_protocol` under `src/`.
- The approved artifact inventory retains canonical models/reference inputs in
  Git LFS, final published reports/figures in ordinary Git, and removes
  generated/duplicate outputs from tracking while keeping them locally.
- The initial installed CLI scope is `thg-gapfill`, `thg-pathway`, and
  `thg-compare`.
- Decide whether package-owned configuration templates or schemas must be
  included as package data.

### Phase 0: Stabilize the Current State

- Create a migration branch.
- Record the current large-file inventory.
- Record current dependency files and active Python version.
- Map existing requirement files into planned base, dev, solver, memote,
  cell-specific, and workflow-specific extras.
- Audit current script entry points: which scripts have usable `--help`, which
  scripts execute at import time, and which scripts require hard-coded repo
  paths.
- Decide initial CLI candidates and deferred CLI candidates. Start with stable,
  repeatable workflows such as gapfill, compare, and pathway implementation.
- Decide the supported Python range. A practical starting point is
  `>=3.10,<3.13` unless dependency constraints require otherwise.
- Decide initial artifact ownership: canonical LFS artifacts, ignored generated
  files, and small fixtures that stay in normal git.
- Do not rename or move large directories yet.

Deliverables:

- `REFACTORING_PLAN.md`
- Initial issue list in GitHub or a local checklist.
- Dependency inventory and proposed extras.
- Large-file inventory and proposed LFS/ignore policy.
- Agreement on Python version, solver support, and initial CLI scope.

Checkpoint commit:

- Commit the reviewed inventories, decisions, and updated plan before additional
  package migrations depend on them.

### Phase 1: Add Packaging and Developer Tooling

- Add `pyproject.toml`.
- Add `src/thg_protocol/__init__.py`.
- Add central pytest config.
- Remove any pytest `pythonpath = ["src"]` setting so tests exercise the
  installed package rather than importing directly from the source tree.
- Migrate package tests away from checkout-only `functions.*` imports.
  Source-checkout compatibility tests whose explicit purpose is to verify the
  legacy `functions` aliases are the only exception; keep them clearly
  identified, and do not use them as evidence that a built wheel is standalone.
- Add `ruff` and `black` configuration.
- Add a `tests/` directory with one trivial import test.
- Add the first characterization tests for the safest pure functions before
  moving their code.
- Add `docs/` skeleton.
- Add updated `.gitignore`.
- Add baseline CI that runs Ruff, the default test selection, and clean-wheel
  import checks.
- Do not add `[project.scripts]` entries yet unless the matching CLI module is
  already import-safe and has a help smoke test.

Validation:

```bash
python -m pip install -e ".[dev]"
pytest -m "not slow and not online and not solver and not gurobi and not memote"
python -c "import thg_protocol; print(thg_protocol.__version__)"
python -m build
```

Also install the built wheel into a clean environment and run the import test
from outside the repository before Phase 1 is considered complete.

Checkpoint commit:

- Commit packaging, baseline CI, and clean-wheel tests together once the chosen
  legacy-namespace policy is proven outside the checkout.

### Phase 2: Move Pure Utilities First

- For each utility, add characterization coverage before or in the same PR as
  the move.
- Move config loading utilities into `thg_protocol.config`.
- Move GPR parsing/sanitization into `thg_protocol.gpr`.
- Move metabolite annotation helpers into `thg_protocol.annotation.metabolites`.
- Move reaction annotation helpers into `thg_protocol.annotation.reactions`.
- For service-backed helpers, land the client protocol, production adapter,
  fake/static test adapter, timeout/retry policy, and response normalization in
  the same change as the public API migration.
- When a moved helper calls BioCyc, KEGG, PubChem, or Ensembl, introduce an
  injectable client interface and mock/static-response tests in the same PR.
  Lazy imports alone are useful for import safety but are not the final service
  boundary.
- Replace wildcard imports with explicit imports.
- Keep old import paths as thin compatibility wrappers during transition when
  existing scripts still depend on them. Add tests for both old and new imports
  until wrappers are removed.

Validation:

```bash
pytest tests/unit tests/characterization
ruff check src tests
```

Checkpoint commits:

- Make one coherent commit per characterized helper cluster. Include the moved
  implementation, tests, explicit imports, and compatibility wrapper together.

### Phase 3: Define Workflow APIs and Refactor Script Entry Points

For each major script:

- Move reusable logic into package modules.
- Expose a Python workflow function with explicit inputs and outputs.
- Add `main(argv=None)`.
- Put execution behind `if __name__ == "__main__": raise SystemExit(main())`.
- Replace hard-coded paths with arguments or config values.
- Use `pathlib.Path`.
- Write outputs to a user-provided output directory.
- Ensure `--help` works without optional heavy dependencies or model files.
- Add a `[project.scripts]` entry only after the command is import-safe,
  parameterized, and covered by a help smoke test.

Initial targets:

1. `gapfill/gapfill.py` -> `thg_protocol.gapfill` API plus `thg-gapfill`.
2. `implement_pathway/pathway_implementation.py` -> `thg_protocol.pathway` API
   plus `thg-pathway`.
3. `compare_models/compare_models.py` -> `thg_protocol.analysis.compare` API
   plus `thg-compare`.

Before target 2 receives a CLI, convert the transitional
`src/thg_protocol/pathway.py` module into the `thg_protocol/pathway/` package
described in the target layout. Keep existing imports working by re-exporting
the public helpers from `pathway/__init__.py`.

Deferred targets until inputs, outputs, credentials, and dependencies are
cleanly parameterized:

1. `build_model/build_model.py`
2. `build_model/build_model_batch.py`
3. `generate_data-base/generate_db.py`
4. `metabolite_reac_identification/metabolite_reac_identification.py`
5. `generate_figures/create_figure.py`

Validation:

```bash
pytest tests/unit tests/integration
thg-compare --help
thg-gapfill --help
thg-pathway --help
```

Checkpoint commits:

- Commit each workflow API independently. Add its entry point in the same or a
  following focused commit only after its help and temporary-output tests pass.

### Phase 4: Expand Integration and CLI Tests

- Convert existing `test_algorithms/` tests to import production modules.
- Move reusable fixtures into `tests/conftest.py`.
- Replace large fixture models with small toy models where possible.
- Mark tests that still require large models as `slow`.
- Mark tests requiring network as `online`.
- Add CLI tests using `tmp_path` for installed commands.
- Add workflow API tests that call Python functions directly without shelling
  out.

Validation:

```bash
pytest -m "not slow and not online and not solver and not gurobi and not memote"
pytest -m "slow and not online and not solver and not gurobi and not memote"
```

Checkpoint commits:

- Group tests by the production workflow they validate; avoid a single
  repository-wide test-migration commit.

### Phase 5: Complete External Service Hardening

- Complete any client modules for BioCyc, KEGG, PubChem, and Ensembl that were
  introduced incrementally during Phases 2 and 3.
- Inject clients into workflow functions instead of calling services directly.
- Add retry, timeout, and cache behavior in one place.
- Add mock/static-response tests for all client-dependent logic.
- Ensure credentials are read only from environment variables or config files
  outside git.
- Audit the public APIs migrated so far and remove any remaining direct service
  calls before declaring the phase complete.

Validation:

```bash
pytest -m "not online and not solver and not gurobi and not memote"
pytest -m "online and not slow and not solver and not gurobi and not memote"
```

Checkpoint commits:

- Commit one service boundary at a time, including its protocol, production
  adapter, static fake, normalized errors, and offline tests.

### Phase 6: Large File Cleanup and Git LFS

- Decide which model/data artifacts are canonical.
- Move canonical large artifacts to Git LFS.
- Remove generated logs, backups, reports, temporary files, and checkpoints from
  git tracking unless they are intentionally published outputs.
- Replace duplicate model copies with one canonical location or documented
  download/LFS paths.
- Keep small test fixtures in normal git.

Validation:

```bash
git lfs ls-files
git lfs fsck
git status
git ls-files | wc -l
```

After any LFS migration or history rewrite, verify a fresh clone in a temporary
directory: fetch LFS objects, check out the canonical artifacts, and compare
their recorded hashes or checksums with the approved inventory. Record exactly
which branches and tags were rewritten, and require collaborators to coordinate
before rewritten refs are pushed.

Checkpoint commits:

- First commit the approved inventory and targeted tracking policy.
- Then commit LFS pointer changes and generated-artifact removals in dedicated,
  reviewable commits before considering any separately approved history rewrite.

### Phase 7: Complete Documentation and Expand CI

- Update `README.md` with a short overview and links to docs.
- Add install instructions for base, dev, solver, memote, and cell-specific
  extras.
- Add examples for the main Python workflow APIs.
- Add CLI examples only for installed, tested commands.
- Expand the baseline CI added in Phase 1:
  - run CLI help smoke tests for installed commands
  - run supported Python/dependency matrix jobs
  - run solver jobs with the matching extras
  - optionally run slow/online tests on a manual schedule

Validation:

```bash
python -m pip install -e ".[dev]"
ruff check src tests
pytest -m "not slow and not online and not solver and not gurobi and not memote"
python -m build
```

CI must additionally install the built wheel into a clean environment and run
imports and installed CLI `--help` smoke tests from outside the checkout.

Checkpoint commits:

- Update workflow documentation with the corresponding stable API or CLI.
- Use a final focused commit for the completed compatibility matrix, expanded
  CI jobs, and release-validation documentation.

## Next Pull Requests

Keep this list limited to pending, reviewable changes. Remove an entry when it
is completed and record the result in `REFACTORING_PROGRESS.md`.

1. Run the opt-in BioCyc fixture where credentials are available and obtain
   maintainer approval for the supported dependency and artifact decisions.

## Definition of Done

The refactor can be considered successful when:

- `pip install -e ".[dev]"` works from a clean checkout.
- A built wheel installs into a clean environment, and package imports plus
  installed CLI smoke tests pass from outside the repository without pytest
  `pythonpath` injection.
- Reusable logic is available through documented Python APIs.
- Core modules can be imported without loading models, writing files, or calling
  external services.
- Default tests run without network access and without full-size model files.
- Stable, repeatable major workflows are available as thin CLI commands where a
  CLI adds value.
- Every installed CLI command supports `--help` and has a smoke test.
- Large canonical artifacts are tracked with Git LFS or documented as external
  downloads.
- Generated artifacts are ignored or written outside the source tree.
- Documentation explains installation, development, model/data handling, and the
  main Python and CLI workflows.
