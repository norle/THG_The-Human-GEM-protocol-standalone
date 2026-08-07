# THG Documentation Information Architecture Implementation Plan

**Repository:** `norle/THG_The-Human-GEM-protocol-standalone`  
**Target branch/context:** `refactoring-cleanup`  
**Assumption:** `docs/plans/thg-functional-implementation-plan.md` has been completed. The maintained THG workflows described there should therefore be documented as finished product functionality rather than as migration-era candidates or incomplete protocol mappings.  
**Purpose:** simplify the published documentation structure, reduce navigation overload, remove overlap between guides and reference material, and separate user documentation from historical/refactoring evidence.

---

## 1. Goals

Restructure the documentation so that a reader can quickly answer one of five questions:

1. **How do I get started?**
2. **How do I run a THG scientific workflow?**
3. **How do I perform a specific optional/local task?**
4. **What is the exact CLI, Python API, configuration, or file-format reference?**
5. **How do I contribute to or maintain the package?**

The documentation should present THG as a mature scientific package, not as a record of the refactoring project that produced it.

### Primary outcomes

- Reduce the number of first-class navigation destinations.
- Remove project history and migration material from onboarding.
- Make THGβ1, THGβ2, Human Database, final THG, and validation the central workflow documentation.
- Eliminate the conceptual overlap between **Individual operations** and **Reference**.
- Merge short maintainer pages into a few substantial pages.
- Archive or exclude migration/parity/audit records that are not useful to normal users.
- Keep detailed generated API reference available without allowing it to dominate the user journey.
- Remove duplicate or alias-only pages from navigation.
- Rewrite implementation-era warnings and limitation language to reflect the completed functional implementation.

---

## 2. Documentation design rules

Every published page should primarily belong to one documentation type.

| Type | Question it answers |
|---|---|
| Getting started | How do I begin using THG? |
| Workflow guide | How do I accomplish this scientific goal? |
| Tool guide | How do I perform this optional or focused operation? |
| Reference | Exactly what interface, configuration, or data format exists? |
| Contributing | How do I change, test, release, or maintain THG? |
| About | What is the scientific and software background? |

### Rules

1. A workflow guide should explain a task, not duplicate full generated API documentation.
2. A reference page should describe exact interfaces and contracts, not teach a scientific workflow.
3. Historical/refactoring evidence should not occupy normal user navigation.
4. Small pages that only contain a few related facts should normally become sections of a larger page.
5. β1, β2, Human Database, final THG, and validation are first-class workflows and should remain separate pages.
6. Examples should be placed near the task they demonstrate rather than exposed as a generic top-level destination.
7. The homepage should route readers to the correct documentation area instead of reproducing most of the site.

---

## 3. Target navigation

Replace the current navigation with approximately the following structure.

```yaml
nav:
  - Home: index.md

  - Getting started:
      - Installation: installation.md
      - Quickstart: quickstart.md
      - How THG works: guide/overview.md

  - THG workflows:
      - Workflow overview: workflows/index.md
      - THGβ1 — Curate a reference GEM: workflows/beta1.md
      - THGβ2 — Expand by GPR and location: workflows/beta2.md
      - Human Database: workflows/human-database.md
      - Final THG — Merge and validate: workflows/final-thg.md
      - Validation: workflows/validation.md
      - Reproducible and resumable runs: workflows/runs.md

  - Tools:
      - Model construction and enrichment: tools/model-construction.md
      - Annotation and GPRs: tools/annotation.md
      - Pathways and gap filling: tools/pathways-gapfill.md
      - Model comparison and analysis: tools/analysis.md
      - Cell-specific models: tools/cell-specific.md
      - Figures and reports: tools/figures.md

  - Reference:
      - Inputs, outputs, and configuration: reference/io-and-config.md
      - CLI: reference/cli.md
      - Python API:
          - Overview: api/index.md
          - Core and I/O: api/core.md
          - Construction: api/construction.md
          - Annotation and GPR: api/annotation.md
          - Workflows: api/workflows.md
          - Analysis: api/analysis.md
          - Services: api/services.md

  - Contributing:
      - Development and releases: contributing/development.md
      - Architecture: contributing/architecture.md
      - Repository and data management: contributing/repository.md

  - About:
      - Scientific background and project history: about/history.md
```

### Navigation acceptance target

The exact final count is not important, but the normal published sidebar should be approximately **20–30 meaningful destinations**, not 50+ narrowly scoped or historical pages.

The two overview pages have distinct ownership:

- `guide/overview.md` is the conceptual explanation of THG, its model states,
  and its scientific terminology.
- `workflows/index.md` is the task chooser and directory of executable
  workflows.

No third overview route should remain under `protocol/`.

---

## 4. Phase 1 — Simplify Getting Started

### 4.1 Move project history out of Getting Started

**Current:** `docs/project-history.md`  
**Target:** `docs/about/history.md`

Rewrite it as a concise background page covering:

- scientific origin of THG;
- relationship to the 2023 protocol paper;
- software lineage where useful;
- distinction between scientific protocol and package implementation.

Remove or heavily shorten refactoring-closeout details that are no longer useful to normal users.

### 4.2 Merge API smoke test into Installation

**Current:** `docs/api-smoke-test.md`

Move its useful content into:

```text
docs/installation.md
└── Verify your installation
```

The standalone `api-smoke-test.md` page should then be removed from navigation and deleted or retained only as a redirect if preserving old links is important.

### 4.3 Keep Getting Started to three destinations

The final section should be:

```text
Getting started
├── Installation
├── Quickstart
└── How THG works
```

### Acceptance criteria

- Project history is not visible under Getting Started.
- API smoke test is not a standalone navigation item.
- A new user can install THG, verify it, run a representative quickstart, and understand the workflow model without reading migration/history pages.
- `mkdocs build --strict` passes.

---

## 5. Phase 2 — Make THG workflows the center of the site

The completed functional implementation plan defines the principal workflow model:

```text
Reference GEM
    |
    v
  THGβ1
    |
    v
  THGβ2 ------------------+
                          |
                          v
                       Final THG
                          ^
                          |
Human Database -----------+
```

Validation and comparison operate across these model states.

### 5.1 Create a concise workflow overview

Create or rewrite:

`docs/workflows/index.md`

It should contain:

- what THG is;
- a workflow diagram;
- short descriptions of β1, β2, Human Database, final THG, validation, and comparison;
- a “which workflow should I use?” table;
- links to the individual workflow guides.

It should **not** contain detailed function listings or migration status matrices.

Comparison is a cross-workflow analysis tool rather than a lifecycle stage. It
should be linked from this overview and documented under Tools → Model
comparison and analysis; it should not introduce a second protocol overview
route.

### 5.2 THGβ1 workflow guide

Use the current β1 documentation as source material, but restructure it as:

```text
# THGβ1 — Curate a reference GEM

## What this workflow does
## Inputs
## Scientific stages
## Run with the CLI
## Run with Python
## Configuration
## Proposals and decisions
## Outputs and artifacts
## Validation
## Troubleshooting
## Next: THGβ2
```

Remove candidate-stage warnings and release-status language that is obsolete after completion of the functional implementation plan.

Keep only a small number of high-value API links. Exact function signatures belong in generated API reference.

### 5.3 THGβ2 workflow guide

Structure similarly:

```text
# THGβ2 — Expand by GPR and location

## What this workflow does
## Required β1 input
## GPR and localization behavior
## Expansion rules
## Run with the CLI
## Run with Python
## Configuration
## Outputs and artifacts
## Validation
## Troubleshooting
## Next: Final THG
```

Remove migration-era candidate/release-gate framing where it no longer represents the finished package.

### 5.4 Human Database workflow guide

Rewrite the current Human Database page around the implemented workflow rather than around what was historically missing.

Suggested structure:

```text
# Human Database

## What this workflow does
## Inputs and supported sources
## Evidence collection and normalization
## Reconstruction stages
## Run with the CLI
## Run with Python
## Configuration
## Outputs and artifacts
## Validation
## Troubleshooting
## Next: Final THG
```

Historical limitations should only be mentioned where scientifically relevant.

### 5.5 Final THG workflow guide

Rename/rework the current merge-and-validation guide as:

`docs/workflows/final-thg.md`

Suggested structure:

```text
# Final THG — Merge and validate

## Inputs
## Merge process
## Matching and conflict resolution
## Consistency and validation checks
## Run with the CLI
## Run with Python
## Outputs and artifacts
## Acceptance/release criteria
## Troubleshooting
```

Do not lead with migration differences or descriptions of what the previous merge API did.

### 5.6 Validation workflow guide

Create a first-class validation page that brings together:

- structural checks;
- chemical/formula checks;
- solver-backed consistency;
- metabolic tasks;
- MEMOTE integration;
- validation artifacts;
- interpretation of pass/fail results.

This replaces the current scattering of validation information across merge, network-analysis, MEMOTE, release, and implementation-status pages.

### Acceptance criteria

- β1, β2, Human Database, final THG, and validation are visible directly under **THG workflows**.
- Each workflow page has a clear beginning, inputs, execution method, outputs, and validation.
- Workflow pages do not duplicate large API inventories.
- Migration-era warnings are removed or rewritten where the completed implementation makes them obsolete.
- A user can follow the scientific workflow without visiting legacy/parity pages.

---

## 6. Phase 3 — Replace “Individual operations” with “Tools”

Remove the **Individual operations** concept from navigation.

The current grouping reflects internal code decomposition more than user intent. Replace it with a smaller **Tools** section for optional or focused tasks.

### 6.1 Model construction and enrichment

Merge material from:

- `workflows/database.md`
- `workflows/model-build.md`

into:

`docs/tools/model-construction.md`

Suggested structure:

```text
# Model construction and enrichment

## Construct a model from normalized records
## Enrich an existing model
## Choosing reconstruction vs enrichment
## Inputs and outputs
## External services
## Examples
## Related API reference
```

### 6.2 Annotation and GPRs

Merge relevant material from annotation/identification and GPR-related operation docs into:

`docs/tools/annotation.md`

Cover:

- metabolite/reaction identification;
- annotation inventory;
- GPR lookup and normalization;
- location lookup;
- injected service-client boundaries.

Avoid duplicating β1/β2 workflow orchestration.

### 6.3 Pathways and gap filling

Merge:

- pathway implementation;
- gapfill.

Target:

`docs/tools/pathways-gapfill.md`

Keep distinct sections for the two operations but explain when each should be used.

### 6.4 Model comparison and analysis

Merge or consolidate:

- network analysis;
- model comparison;
- applicable non-workflow consistency utilities.

Target:

`docs/tools/analysis.md`

Validation procedures required for release remain on the first-class Validation workflow page.

### 6.5 Keep optional extensions separate where useful

Retain concise pages for:

- cell-specific modeling;
- figures and reports.

These are distinct enough to justify separate task guides.

### 6.6 Remove implementation-foundation pages from user navigation

`workflows/phase0-foundations.md` should not remain a normal user-visible operation.

Move permanent architectural concepts into Contributing → Architecture, then archive or delete the old page.

### 6.7 Move resumability to workflow infrastructure

`workflows/resumable-run.md` should become:

`docs/workflows/runs.md`

It should document:

- run directories;
- manifests;
- artifact chaining;
- resume behavior;
- stage invalidation;
- provenance;
- restart/reproducibility behavior.

It should be framed as common workflow execution infrastructure, not an individual scientific operation.

### Acceptance criteria

- “Individual operations” no longer appears in the navigation.
- β1 and β2 are not categorized as tools.
- “Phase 0 foundations” is not presented as a user operation.
- Tool pages are organized by user task rather than package module count.
- Each tool guide points to generated API reference for exact signatures.

---

## 7. Phase 4 — Make Reference strictly reference material

Reference should answer exact interface questions, not duplicate workflow tutorials.

### 7.1 Consolidate data/configuration reference

Create:

`docs/reference/io-and-config.md`

Merge or link the durable reference material for:

- supported model formats;
- normalized record formats;
- configuration structure;
- run directory conventions;
- output/artifact roles;
- relevant optional dependencies;
- provenance files where appropriate.

Machine-readable schemas or large inventories should remain separate files and be linked rather than manually reproduced.

### 7.2 CLI reference

Create or retain a single:

`docs/reference/cli.md`

Document all installed commands in one place, including:

- command purpose;
- synopsis;
- required inputs;
- major options;
- exit/failure behavior;
- links to workflow guides.

Generated or exact parser details can be included where appropriate.

### 7.3 Python API

Retain generated `mkdocstrings` API pages, but group them visually under **Python API**.

Recommended visible pages:

- Overview
- Core and I/O
- Construction
- Annotation and GPR
- Workflows
- Analysis
- Services

If `api/figures.md` is small, fold it into Analysis or Workflows instead of preserving a separate navigation entry.

### 7.4 Remove generic Examples navigation

Do not expose `examples/README.md` as a standalone Reference destination.

Keep example files under `docs/examples/`, but link to them from:

- Quickstart;
- β1;
- β2;
- Human Database;
- tools;
- CLI/API pages where relevant.

Fold the fixture catalog and usage notes from `examples/README.md` into the
relevant guides or `reference/io-and-config.md`, then remove the standalone
README page from the published site. The JSON fixtures remain repository
assets and must continue to be covered by the practical example tests.

### 7.5 Migrate API inventories and page ownership

The repository has checked-in inventories that are part of the documentation
contract. Update them in the same change as the page moves:

- update `docs/api/api-inventory.json` page values for any renamed API pages;
- update `docs/api/workflow-api-inventory.json` for every merged or renamed
  workflow guide, including the new validation, Human Database, final THG,
  tools, and runs pages;
- preserve one canonical generated location for every Python symbol;
- keep `reference/cli.md` as the user-facing command reference, while retaining
  a clearly owned generated Python API page for CLI modules if those modules
  remain in the canonical API inventory;
- update all tests and CI policy checks that read these inventories or assert
  paths such as `api/cli.md`.

Moving a generated API page is not complete until its inventory entry,
mkdocstrings directive, workflow links, and tests all agree on the new owner.

### Acceptance criteria

- Reference pages contain exact contracts, formats, options, or generated API documentation.
- Tutorials and scientific procedures are not duplicated in Reference.
- Generic “Examples” is removed from the nav.
- Generated Python API remains discoverable in no more detail than is useful.

---

## 8. Phase 5 — Reduce Maintainers to three substantial pages

Rename **Maintainers** to **Contributing**.

Target:

```text
Contributing
├── Development and releases
├── Architecture
└── Repository and data management
```

### 8.1 Development and releases

Merge:

- `development.md`
- `documentation-contributing.md`
- `release-validation.md`
- durable content from `dependency-compatibility.md`

into:

`docs/contributing/development.md`

Suggested structure:

```text
# Development and releases

## Development environment
## Tests and linting
## Optional test groups
## Documentation development
## Dependency compatibility policy
## Building distributions
## Installed-wheel verification
## Release checklist
## GitHub Pages/docs deployment
```

Avoid repeating the same commands in multiple sections where one canonical release gate is sufficient.

### 8.2 Architecture

Merge permanent architectural concepts from:

- `architecture.md`
- `api-contracts.md`
- `service-boundary-audit.md`
- workflow foundation documentation

into:

`docs/contributing/architecture.md`

Suggested structure:

```text
# Architecture

## Package boundaries
## Workflow architecture
## Model ownership and mutation
## Evidence → proposal → decision → mutation model
## Artifact chaining and resumability
## External service boundaries
## API design principles
## Optional dependency boundaries
```

Do not preserve audit/checkpoint wording such as “reviewed as part of the refactoring checkpoint” in the primary architecture page.

### 8.3 Repository and data management

Merge durable material from:

- `repository-map.md`
- `artifact-inventory.md`
- `git-lfs-standalone-repository.md`
- related artifact/checksum policy

into:

`docs/contributing/repository.md`

Suggested structure:

```text
# Repository and data management

## Repository layout
## Canonical/reference inputs
## Generated run artifacts
## Git LFS
## Checksums
## Large files
## What belongs in Git
## What belongs in run/output directories
```

Large generated inventories/checksum lists may remain machine-readable support files rather than rendered navigation pages.

### Acceptance criteria

- No more than three primary Contributing destinations.
- Release instructions have one canonical location.
- Architecture has one canonical location.
- Repository/artifact/LFS ownership has one canonical location.
- Short maintainer pages no longer exist only to hold a few paragraphs.

---

## 9. Phase 6 — Archive migration, parity, audit, and closeout material

The published documentation should not require users to navigate refactoring evidence.

Review the following for archive/removal from navigation:

```text
service-boundary-audit.md
legacy-workflows.md
legacy-api-inventory.md
parity/README.md
parity/contracts/**
api-contracts.md
protocol/implementation-status.md
protocol/capability-status.md
workflows/phase0-foundations.md
```

### 9.1 Preserve durable concepts

Before archiving, extract permanent information:

- API ownership semantics;
- explicit-path policy;
- service injection boundaries;
- meaningful intentional behavior differences that remain part of supported behavior;
- provenance/artifact rules;
- scientific caveats that still matter.

Move these into Architecture, workflow guides, or Reference.

### 9.2 Archive historical evidence

Historical records may be retained under a non-published location such as:

```text
docs/internal/
docs/history/
docs/plans/archive/
```

Extend `exclude_docs` in `mkdocs.yml` as needed.

Example:

```yaml
exclude_docs: |
  plans/**
  internal/**
  history/**
```

Use an archive rather than deletion when the records remain useful for repository history, auditability, or future maintainers.

### 9.3 Remove duplicate status pages

`protocol/capability-status.md` is an alias to the implementation-status page and should not remain as a separate destination.

After functional implementation completion, reassess whether the large migration-era implementation/evidence matrix needs to be published at all.

If retained, move it to historical/internal documentation rather than keeping it in the core protocol journey.

### 9.4 Preserve the evidence contract while removing status navigation

`docs/protocol/capability-evidence.json` and
`docs/protocol/implementation-status.md` are currently consumed by executable
tests, not just displayed as pages. Do not archive either file in isolation.

Choose one of these explicit outcomes before moving them:

1. retain the machine-readable registry at a stable non-navigation path and
   update the status tests to consume that registry; or
2. move the registry and status matrix together to a new internal/reference
   location, update every test and link, and verify that the evidence paths in
   the registry still exist.

The final site may omit the human-readable migration matrix from navigation,
but the maintained evidence source must have one canonical owner and a tested
schema. “Archive” is not sufficient unless its consumers and replacement path
are recorded.

### Acceptance criteria

- No alias-only page appears in the nav.
- Legacy/parity material is not required to understand supported current functionality.
- Refactoring audits are not primary published documentation.
- Permanent design rules extracted from archived pages remain documented elsewhere.
- Historical files that are retained are excluded from the normal MkDocs site or clearly separated under About/History.
- Capability evidence and status tests have a canonical maintained source after archival.

---

## 10. Phase 7 — Rewrite the Home page

The homepage should route users, not duplicate the documentation site.

Suggested content:

```text
# THG Protocol

Short description of THG and the maintained package.

[Install THG] [Quickstart] [Run the THG workflow]

Reference GEM → THGβ1 → THGβ2 ──┐
                                 ├→ Final THG
Human Database ──────────────────┘

## What you can do

- Curate a reference human GEM
- Expand it using GPR/localization evidence
- Construct the Human Database
- Build and validate final THG
- Validate or compare models independently
- Use supporting model-analysis tools

## Documentation

Getting Started
THG Workflows
Tools
Reference
Contributing
```

### Remove from Home

- detailed project/software lineage;
- long implementation-status discussion;
- migration warnings;
- exhaustive terminology;
- duplicate protocol explanations;
- maintainer-plan references.

A short scientific citation/background link is sufficient.

### Acceptance criteria

- Home is substantially shorter than the current page.
- The primary calls to action are visible without scrolling through implementation history.
- The full protocol is explained in the workflow overview, not duplicated on Home.

---

## 11. Proposed current-to-target mapping

| Current page/area | Target action |
|---|---|
| `project-history.md` | Move/shorten to `about/history.md` |
| `api-smoke-test.md` | Merge into Installation |
| `workflow-overview.md` | Merge/rework into `guide/overview.md` and/or `workflows/index.md` |
| `protocol/index.md` | Rework into workflow overview; remove migration status discussion |
| `protocol/reference-model.md` | Split useful content between β1 and β2 guides; retire duplicate route page if no longer needed |
| `workflows/beta1.md` | Promote to primary β1 workflow guide |
| `workflows/beta2.md` | Promote to primary β2 workflow guide |
| `protocol/human-database.md` | Promote/rewrite as primary Human Database workflow guide |
| `protocol/merge-and-validate.md` | Rename/rewrite as Final THG guide |
| `protocol/end-to-end-example.md` | Fold into Quickstart or the relevant workflow guide; remove the duplicate standalone route |
| `usage.md` | Convert to Tools overview or remove from nav after tool consolidation |
| `workflows/database.md` | Merge into Model construction and enrichment |
| `workflows/model-build.md` | Merge into Model construction and enrichment |
| `workflows/annotation.md` | Merge into Annotation and GPRs |
| `workflows/pathway.md` | Merge into Pathways and gap filling |
| `workflows/gapfill.md` | Merge into Pathways and gap filling |
| `workflows/network-analysis.md` | Merge into Model comparison and analysis / Validation |
| `workflows/comparison.md` | Merge into Model comparison and analysis |
| `workflows/memote.md` | Merge core usage into Validation |
| `workflows/resumable-run.md` | Rework as `workflows/runs.md` |
| `workflows/merge.md` | Fold into Final THG and update its workflow-inventory entry |
| `workflows/phase0-foundations.md` | Move durable concepts to Architecture; archive/remove |
| `workflows/cell-specific.md` | Retain as concise Tool guide |
| `workflows/figures.md` | Retain as concise Tool guide |
| `examples/README.md` | Remove from nav; link examples contextually |
| `data-and-model-files.md` | Rework/merge into Reference → I/O and configuration |
| `development.md` | Merge into Development and releases |
| `documentation-contributing.md` | Merge into Development and releases |
| `release-validation.md` | Merge into Development and releases |
| `dependency-compatibility.md` | Merge durable policy/table into Development and releases |
| `architecture.md` | Base for Contributing → Architecture |
| `api-contracts.md` | Move durable API principles to Architecture; archive migration detail |
| `service-boundary-audit.md` | Move permanent rules to Architecture; archive audit |
| `repository-map.md` | Merge into Repository and data management |
| `artifact-inventory.md` | Summarize/link from Repository and data management |
| `git-lfs-standalone-repository.md` | Merge essential procedure into Repository and data management |
| `legacy-workflows.md` | Archive |
| `legacy-api-inventory.md` | Archive |
| `parity/**` | Archive |
| `protocol/capability-status.md` | Remove duplicate alias |
| `protocol/implementation-status.md` | Archive or retain only if there is a continuing product need |
| `protocol/capability-evidence.json` | Preserve as the machine-readable evidence source, or move it together with its status matrix and update all consuming tests |
| `api/cli.md` | Split user-facing command reference from generated CLI-module API ownership; update inventory and CI checks |
| `api/figures.md` | Retain as the canonical figures API page or fold its symbols into Analysis and update the inventory |
| `api/**` | Keep generated API reference, with reduced visible grouping |

---

## 12. Content cleanup rules during migration

While moving pages, also clean the language.

### Remove or rewrite obsolete wording

Search for phrases such as:

- “candidate-stage implementation”;
- “not implemented” where the completed functional plan now provides the feature;
- “current package does not contain…” statements that are no longer true;
- “conceptual mapping only” where the workflow is now implemented;
- “refactoring checkpoint”;
- “parity remediation plan”;
- “closeout requirements”;
- references to the functional implementation plan as a future roadmap.

### 12.1 Verify claims before rewriting completion language

Do not rewrite a limitation solely because the functional implementation plan
labels a workstream `verified`. For each changed claim, record the supporting
acceptance test or release-gate evidence and distinguish:

- supported offline behavior;
- injected/live-service behavior;
- intentionally out-of-scope scientific or solver-heavy behavior;
- historical implementation differences that remain meaningful to users.

In particular, preserve documented limitations for live service access,
publication-specific reproduction, online pathway discovery, and solver-heavy
extensions where they still apply. The result should present verified
functionality confidently without implying broader scientific coverage than the
package supports.

### Replace implementation-history framing with user framing

Prefer:

> Run the β2 workflow using a verified β1 artifact.

over:

> The maintained branch should instead reference the β1 export.

Prefer:

> The workflow writes the following artifacts…

over:

> The current maintained implementation exposes…

### Avoid repeated caveats

Scientific caveats should remain where important, but implementation/migration caveats should not be repeated on Home, workflow overview, individual workflow pages, status pages, and tool pages.

Choose one canonical place for each permanent caveat.

---

## 13. Link and redirect strategy

Before deleting or renaming pages:

1. Find inbound links in `docs/`, README files, issue templates, and code comments.
2. Update links to canonical replacement pages.
3. Choose a compatibility policy for each high-risk route before deletion:
   configure and test a redirect mechanism, or retain a minimal link-bearing
   compatibility page. Do not assume that an ordinary Markdown alias redirects
   an external URL.
4. Do not keep duplicate full pages solely for link compatibility.
5. Run strict link validation through the documentation tests.

Potential high-risk renamed pages include:

- `protocol/reference-model.md`;
- `protocol/merge-and-validate.md`;
- `usage.md`;
- `development.md`;
- `data-and-model-files.md`.

The compatibility decision must cover README links, published repository links,
issue templates, code comments, and likely GitHub Pages URLs. Add a redirect
plugin/dependency only if the deployment workflow and generated-site tests
exercise it; otherwise keep explicit compatibility stubs until the next
documented URL migration.

---

## 14. Validation and tests

The documentation restructuring is complete only when the site builds and the new information architecture is internally consistent.

### Required checks

```bash
python -m pip install -e ".[docs,dev]"
mkdocs build --strict
pytest tests/docs
```

Run any link/navigation tests already present in the repository.

Add documentation checks that:

- assert the required top-level sections and canonical pages are present in
  `mkdocs.yml`;
- assert forbidden labels/routes such as Individual operations, capability
  aliases, and Phase 0 foundations are absent from navigation;
- assert archived/internal files are absent from the generated site;
- assert every renamed workflow/API inventory page exists and every inventory
  symbol is generated exactly once;
- assert the fixture files used by the practical examples remain present even
  though `examples/README.md` is no longer a published page;
- check user-facing published HTML for obsolete implementation warnings without
  treating the intentionally retained history page or internal source files as
  current product guidance.

Update the existing path assertions in `tests/docs` and the API/status contract
tests as part of the migration. The final verification should include
`pytest tests/docs tests/unit/test_ci_matrix_policy.py
tests/unit/test_capability_evidence.py` in addition to the strict MkDocs build.

### Manual review checklist

- [ ] Homepage is concise and routes users correctly.
- [ ] Getting Started contains only onboarding material.
- [ ] β1, β2, Human Database, final THG, and Validation are obvious from the sidebar.
- [ ] No first-time user must understand legacy parity terminology.
- [ ] No duplicate status/alias pages appear in the nav.
- [ ] “Individual operations” is gone.
- [ ] “Phase 0 foundations” is gone from user navigation.
- [ ] Maintainer material is consolidated into three substantial pages.
- [ ] Examples are linked from relevant guides instead of exposed generically.
- [ ] Workflow guides do not reproduce full generated API reference.
- [ ] API reference remains complete and discoverable.
- [ ] Archived/internal documentation is excluded from MkDocs.
- [ ] Search results do not prominently surface obsolete implementation warnings.
- [ ] All renamed/moved internal links resolve.
- [ ] `mkdocs build --strict` passes.
- [ ] `pytest tests/docs` passes.

---

## 15. Suggested implementation order

Implement the restructuring in this order to minimize broken links and duplicate rewriting.

### Step 1 — Create the new skeleton

Create:

```text
docs/
├── about/
├── guide/
├── workflows/
├── tools/
├── reference/
└── contributing/
```

Do not delete old pages yet.

Before writing replacement content, record the canonical owner for each
overview, workflow, API page, status/evidence source, and high-risk legacy URL.
This ownership table is the source of truth for the later link and inventory
migration.

### Step 2 — Rewrite the core user journey

In order:

1. Home
2. Installation
3. Quickstart
4. How THG works
5. Workflow overview
6. β1
7. β2
8. Human Database
9. Final THG
10. Validation
11. Reproducible/resumable runs

### Step 3 — Consolidate Tools

Create the six target tool pages and migrate useful content from the existing individual-operation pages.

### Step 4 — Consolidate Reference

Create I/O/config and CLI reference, then regroup the generated API pages.
Update the canonical API and workflow API inventories at the same time as the
page regrouping; do not postpone inventory changes until after old pages are
removed.

### Step 5 — Consolidate Contributing

Build the three maintainer pages before removing their source pages.

### Step 6 — Extract and archive historical material

Move durable concepts first, then archive:

- legacy;
- parity;
- audit;
- migration status;
- Phase 0 implementation notes.

Preserve or deliberately relocate the capability evidence registry and its
status-test contract before archiving any status page. Verify all registry
evidence paths after relocation.

### Step 7 — Replace `mkdocs.yml` navigation

Switch to the new hierarchy only after replacement pages exist.

### Step 8 — Fix links and run strict validation

Search the repository for old paths and update them.
Apply the chosen redirect or compatibility-stub policy for high-risk external
routes, then run the generated-site route checks.

### Step 9 — Remove obsolete pages

Delete pages that are fully superseded, or keep them outside published docs where historical retention is useful.

---

## 16. Definition of done

This plan is complete when:

1. The published navigation reflects user intent rather than repository history.
2. Getting Started has approximately three destinations.
3. THG scientific workflows are the primary documentation section.
4. β1, β2, Human Database, final THG, and Validation each have canonical workflow guides.
5. “Individual operations” has been replaced by a smaller Tools section.
6. Reference contains exact interfaces/configuration rather than workflow tutorials.
7. Maintainer material is consolidated into approximately three pages.
8. Legacy/parity/refactoring evidence is archived or excluded from normal documentation.
9. Duplicate/alias-only status pages are removed.
10. Obsolete incomplete-implementation language has been updated for the completed functional plan.
11. Home is concise and routes readers to the appropriate documentation.
12. `mkdocs build --strict` and `pytest tests/docs` pass.
13. Existing internal links and high-value external-compatible paths are handled deliberately.
14. The documentation reads like documentation for the maintained THG product, not like documentation for an ongoing refactoring project.
15. API/workflow inventories, status/evidence registries, and their consuming tests have one consistent canonical path.
16. Required and forbidden navigation routes are checked automatically.
17. Completion-language edits are backed by feature-level acceptance evidence and do not erase supported limitations.

---

## 17. Non-goals

This restructuring should **not**:

- collapse all THG workflows into one enormous page;
- remove detailed Python API documentation;
- delete historically useful records without first considering archival value;
- hide real scientific limitations or uncertainty;
- change scientific behavior merely to simplify documentation;
- duplicate the functional implementation plan.

The goal is to improve information architecture and presentation of the already-implemented functionality.

---

## 18. Recommended final principle

When deciding whether a page deserves its own navigation entry, ask:

> **Does a user intentionally arrive at the documentation wanting to do or look up this specific thing?**

If the answer is no, the material should usually be:

- a section within a broader page;
- linked contextually;
- generated reference;
- or archived/internal documentation.

This principle should also be used for future documentation additions so that the navigation does not gradually return to its current level of fragmentation.
