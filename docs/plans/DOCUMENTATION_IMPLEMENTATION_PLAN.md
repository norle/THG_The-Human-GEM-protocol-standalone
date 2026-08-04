# THG Documentation Implementation Plan

## Document control

- **Status:** Blocked at Phase 7 pending repository publication and Pages activation
- **Last updated:** 2026-08-04
- **Owner:** Codex / THG maintainers
- **Tracking rule:** This file is the source of truth for documentation progress.

## Progress tracking

Update this file whenever work begins or ends on a phase. At minimum, update
the status, checklist items, evidence, and the changelog in the same pull
request or commit that changes the documentation.

Use these statuses consistently:

- `[ ]` Not started
- `[-]` In progress
- `[x]` Complete
- `[!]` Blocked; explain the blocker in the phase notes

For every phase, record:

1. The current status.
2. The date of the latest update.
3. The person or pull request responsible.
4. Links to the files, tests, build logs, or deployed pages that provide
   evidence of completion.
5. Any remaining follow-up work.

### Phase summary

| Phase | Status | Last updated | Evidence / notes |
| --- | --- | --- | --- |
| 1. Documentation foundation | `[x]` | 2026-08-03 | `pyproject.toml`, `mkdocs.yml`, `docs/documentation-contributing.md`; editable docs install and strict build pass locally. |
| 2. Information architecture | `[x]` | 2026-08-04 | `docs/index.md`, `quickstart.md`, `usage.md`, `workflow-overview.md`, complete navigation, and explicit `plans/**` exclusion. |
| 3. API and code reference | `[x]` | 2026-08-04 | `docs/api/`, `api-inventory.json`, and `workflow-api-inventory.json`; strict build renders curated canonical symbols and installed command pages. |
| 4. Tutorials and executable examples | `[x]` | 2026-08-03 | `docs/workflows/`, `docs/examples/`, `tests/docs/test_examples.py`; 3-phase offline examples pass. |
| 5. Repository and artifact reference | `[x]` | 2026-08-03 | Artifact, data/model, service-boundary, legacy, and Git LFS pages are navigable and cross-linked. |
| 6. Documentation validation and CI | `[x]` | 2026-08-04 | `.github/workflows/docs.yml`, `tests/docs/test_documentation.py`; fresh-site anchor/link checks, local strict build, and offline docs tests pass. |
| 7. GitHub Pages publishing | `[!]` | 2026-08-03 | Local workflow is ready, but it is not present on the remote default branch; publication, Pages source activation, and deployment require authorized external state changes. |

### Progress update checklist

When updating this plan:

- [x] Update the phase summary table.
- [x] Update the relevant phase checklist and status.
- [x] Add validation evidence or explain the blocker.
- [x] Update **Last updated** at the top of this file.
- [x] Add an entry to the changelog below.

### Changelog

| Date | Update | Evidence / link |
| --- | --- | --- |
| 2026-08-03 | Initial implementation plan created. | — |
| 2026-08-03 | Implemented documentation foundation, site structure, generated API reference, deterministic examples, artifact reference, and CI/Pages workflow. | `mkdocs build --strict`; `pytest tests/docs`; offline package suite. |
| 2026-08-03 | Audited repository Pages state: default branch is `refactoring-cleanup`; intended URL returns HTTP 404 until Pages Actions source and deployment are enabled. | GitHub repository metadata; read-only Pages URL check. |
| 2026-08-03 | Added the administrator handoff for enabling the repository Pages source and verifying the deployment before closing Phase 7. | `docs/documentation-contributing.md` |
| 2026-08-03 | Reconfirmed the blocker: the remote default branch does not yet contain `.github/workflows/docs.yml` (GitHub API 404), so no deployment run can exist. | GitHub repository metadata and default-branch file inspection. |
| 2026-08-04 | Implemented the documentation UX plan: canonical task chooser, published data/examples references, excluded plans, curated API inventories, Autorefs workflow links, reduced API clutter, consistent workflow templates, and fresh-site validation. | `mkdocs build --strict`; `pytest tests/docs`; `tests/docs/test_documentation.py` |

## Repository assessment

The repository already contains:

- MkDocs configuration: `mkdocs.yml`.
- Existing user, developer, release, artifact, legacy, and workflow pages in
  [`docs/`](../index.md).
- Python package code under `src/thg_protocol/`.
- A broad test suite under `tests/`.
- Existing GitHub Actions package validation in
  `.github/workflows/ci.yml`.

The main documentation gaps are:

- No generated API reference for the Python package.
- Few tested, end-to-end examples using small deterministic inputs.
- Some existing reference pages are not included in the main MkDocs
  navigation.
- No documentation-specific CI or deployment workflow.
- No explicit progress-tracking mechanism for the documentation work itself.

## Phase 1 — Documentation foundation

**Status:** `[x]` Complete
**Last updated:** 2026-08-03
**Owner / PR:** Codex / local implementation

### Tasks

- [x] Add `mkdocstrings[python]` to the `docs` extra in
  `pyproject.toml`.
- [x] Configure MkDocs Material for search, code examples, navigation, and
  source links in `mkdocs.yml`.
- [x] Make `mkdocs build --strict` the required local documentation build.
- [x] Add all relevant existing pages to the navigation, including artifact,
  service-boundary, and Git LFS documentation.
- [x] Add a documentation contribution section explaining how this plan must
  be updated as work progresses.

### Acceptance criteria

- [x] `python -m pip install -e ".[docs]"` succeeds.
- [x] `mkdocs build --strict` succeeds.
- [x] Every page intended for publication is reachable through navigation.

**Evidence / notes:**

`python -m pip install -e ".[docs]"` and `mkdocs build --strict` completed on
2026-08-03. Navigation includes all published Markdown pages plus the artifact,
service-boundary, and Git LFS references.

## Phase 2 — Information architecture

**Status:** `[x]` Complete
**Last updated:** 2026-08-03
**Owner / PR:** Codex / local implementation

Organize the site into clear audiences and tasks:

- Home and quickstart
- Concepts and architecture
- Installation and configuration
- Tutorials and major workflows
- API and CLI reference
- Repository, data, model, and output reference
- Development, testing, release, legacy, and maintainer documentation

### Tasks

- [x] Turn [`docs/index.md`](../index.md) into a useful landing page.
- [x] Add a five-minute quickstart using a small model fixture.
- [x] Add an architecture/data-flow page explaining how construction,
  annotation, services, analysis, and reporting fit together.
- [x] Add a repository map covering `src`, `tests`, `models`, `files`,
  `supplementary_material`, `constraints`, and `docs`.
- [x] Separate newcomer-facing guides from historical and maintainer-only
  material.

**Evidence / notes:**

Landing page: [`docs/index.md`](../index.md). Quickstart and concepts:
[`docs/quickstart.md`](../quickstart.md),
[`docs/architecture.md`](../architecture.md), and
[`docs/repository-map.md`](../repository-map.md).

## Phase 3 — API and code reference

**Status:** `[x]` Complete
**Last updated:** 2026-08-03
**Owner / PR:** Codex / local implementation

Document every module under `src/thg_protocol`. Public functions and classes
should have generated API pages; private helpers should be summarized in the
architecture documentation rather than presented as supported interfaces.

### Coverage groups

- [x] Core utilities: `config`, `io`, `glycan`, and `reaction_config`.
- [x] Model construction: `database`, `database_parsing`, and `model_build`.
- [x] Annotation and GPR: `annotation` and `gpr`.
- [x] External services: BioCyc, KEGG, Ensembl, PubChem, and Location.
- [x] Workflows: `gapfill`, `pathway`, `merge`, and `cell_specific`.
- [x] Analysis: comparison, consistency, compaction, and network analysis.
- [x] Figures and report-generation APIs.
- [x] Installed commands: `thg-gapfill`, `thg-pathway`, and `thg-compare`.

### Documentation requirements for public APIs

- [x] Parameters and return values.
- [x] Input/output file formats.
- [x] Exceptions and failure modes.
- [x] Mutation versus copy/ownership behavior.
- [x] Optional dependencies and solver requirements.
- [x] Network access, credentials, caching, and static-client behavior.
- [x] A minimal usage example.

**Evidence / notes:**

The generated reference is grouped under [`docs/api/`](../api/index.md). A local
module audit found all 47 `src/thg_protocol` modules represented in the API
pages; `mkdocs build --strict` rendered them successfully.

## Phase 4 — Tutorials and executable examples

**Status:** `[x]` Complete
**Last updated:** 2026-08-03
**Owner / PR:** Codex / local implementation

Create small deterministic fixtures under `docs/examples/` or
`tests/fixtures/docs/`, and test the examples under `tests/docs/`.

### Required workflow coverage

- [x] Database reconstruction from normalized records, JSON, and historical
  pickle inputs.
- [x] Single and batch model building.
- [x] Metabolite/reaction annotation and GPR lookup.
- [x] Pathway implementation.
- [x] Three-phase gapfilling.
- [x] Model merge and consistency checks.
- [x] Network component analysis and compaction.
- [x] Cell-specific model reduction and transcriptomics helpers.
- [x] Model comparison.
- [x] Figure and report generation.
- [x] Optional solver and MEMOTE workflows.

Each tutorial must show the purpose, prerequisites, inputs, CLI usage, Python
usage, expected outputs, and troubleshooting guidance. Examples must use
explicit paths, avoid repository-relative side effects, and avoid live network
calls in the default documentation test suite.

**Evidence / notes:**

Workflow pages are under `docs/workflows/`, fixtures under `docs/examples/`,
and executable coverage is in `tests/docs/test_examples.py`. The test suite
uses temporary output paths and static clients; optional solver/MEMOTE guidance
is documented but excluded from the offline gate.

## Phase 5 — Repository and artifact reference

**Status:** `[x]` Complete
**Last updated:** 2026-08-03
**Owner / PR:** Codex / local implementation

- [x] Document canonical inputs, generated outputs, historical reports, test
  fixtures, and Git LFS files.
- [x] Explain which files are safe to use in examples and which are large or
  historical artifacts.
- [x] Document model formats, configuration JSON, report formats, and cache
  ownership.
- [x] Link and reorganize the existing artifact inventory, service boundary
  audit, legacy API inventory, and standalone Git LFS runbook.

**Evidence / notes:**

Artifact ownership is documented in
[`docs/artifact-inventory.md`](../artifact-inventory.md),
[`docs/data-and-model-files.md`](../data-and-model-files.md),
[`docs/service-boundary-audit.md`](../service-boundary-audit.md), and
[`docs/git-lfs-standalone-repository.md`](../git-lfs-standalone-repository.md).

## Phase 6 — Documentation validation and CI

**Status:** `[x]` Complete
**Last updated:** 2026-08-03
**Owner / PR:** Codex / local implementation

Create `.github/workflows/docs.yml` that:

- [x] Runs on pull requests.
- [x] Runs on pushes to the default branch.
- [x] Supports manual execution.
- [x] Installs the `docs` extra.
- [x] Runs `mkdocs build --strict`.
- [x] Executes documentation examples or their dedicated tests.
- [x] Does not require credentials, solvers, large model files, or live
  external services.
- [x] Runs documentation link, API-anchor, and unresolved-markup checks in the
  fresh-site documentation test.

### Release/maintenance policy

- [x] Public API changes require corresponding API/reference documentation.
- [x] Workflow behavior changes require updated tutorials and examples.
- [x] New artifacts require an ownership and publication decision.
- [x] Every documentation change updates this plan’s progress metadata when it
  advances a phase.

**Evidence / notes:**

`.github/workflows/docs.yml` validates pull requests, pushes, and
manual runs; it installs the docs extra, builds strictly, and runs
`pytest tests/docs`. Local evidence: 2 docs tests passed, 1,845 offline package
tests passed (with 2 expected skips), and strict MkDocs build passed. A link
checker remains optional follow-up.

## Phase 7 — GitHub Pages publishing

**Status:** `[!]` Blocked; local changes are not published and repository Pages activation requires external authorization
**Last updated:** 2026-08-03
**Owner / PR:** Codex / THG maintainers; repository settings and deployment run pending

Use GitHub Pages with GitHub Actions as the initial hosting solution.

### Tasks

- [ ] Configure the repository’s Pages source as **GitHub Actions**.
- [x] Build the site with `mkdocs build --strict`.
- [x] Upload the generated `site/` directory as a Pages artifact.
- [x] Deploy only from the default branch.
- [x] Use the `github-pages` environment with the required Pages permissions.
- [x] Add the anticipated deployed URL to the README and documentation homepage.
- [x] Add a `CNAME` file only if a custom domain is later selected; no custom domain is selected.
- [x] Confirm that no credentials or sensitive repository data are published.

GitHub’s custom Pages workflow uses a build step, Pages artifact upload, and
Pages deployment action. The deployment job requires Pages write and OIDC
identity-token permissions. See the [GitHub Pages custom workflow
documentation](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages).

MkDocs produces a static site that can be hosted on GitHub Pages or another
static host. The site should be built and reviewed locally before deployment;
see the [MkDocs deployment guide](https://www.mkdocs.org/user-guide/deploying-your-docs/).

**Evidence / notes:**

The workflow uses `configure-pages`, `upload-pages-artifact`, and
`deploy-pages`, with the `github-pages` environment and Pages/OIDC permissions.
The intended URL is recorded in `README.md` and `docs/index.md`; a read-only
request on 2026-08-03 returned HTTP 404, confirming that it is not live yet.
The repository metadata identifies `refactoring-cleanup` as the default branch.
The GitHub Pages source must be set to GitHub Actions and a default-branch run
must complete before this phase can be marked complete.

## Definition of done

- [x] A new contributor can install the project and complete the quickstart.
- [x] Every major workflow has a CLI or Python example.
- [x] Every public package area has an API/reference page.
- [x] Examples are tested and do not require live services by default.
- [x] Repository artifacts and model/data ownership are documented.
- [x] `mkdocs build --strict` passes in CI.
- [x] Pull requests validate documentation before merge.
- [!] The default branch deploys successfully to GitHub Pages; blocked until the workflow is published and Pages Actions source is enabled.
- [x] This plan accurately records the completed work and remaining follow-up.
