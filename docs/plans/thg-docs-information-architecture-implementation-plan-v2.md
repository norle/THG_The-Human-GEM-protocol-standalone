# THG Documentation Information Architecture Implementation Plan

**Repository:** `norle/THG_The-Human-GEM-protocol-standalone`  
**Target branch/context:** `refactoring-cleanup`  
**Assumption:** `docs/plans/thg-functional-implementation-plan.md` has been completed and its verified functionality is the current implementation baseline.  
**Purpose:** simplify the published documentation structure, reduce navigation overload, remove overlap between guides and reference material, and separate current product documentation from historical refactoring/parity evidence.

---

## 1. Goals

Restructure the documentation so that a reader can quickly answer one of five questions:

1. **How do I get started?**
2. **How do I run a THG scientific workflow?**
3. **How do I perform a specific optional or focused task?**
4. **What is the exact CLI, Python API, configuration, or file-format reference?**
5. **How do I contribute to or maintain the package?**

The documentation should present THG as a maintained scientific package rather than as a record of the refactoring project that produced it.

### Primary outcomes

- Reduce the number of first-class navigation destinations.
- Remove project history and migration material from onboarding.
- Make THGβ1, THGβ2, Human Database, final THG, and validation the central workflow documentation.
- Replace **Individual operations** with a smaller task-oriented **Tools** section.
- Remove conceptual overlap between guides and reference material.
- Merge short maintainer pages into a few substantial pages.
- Archive or exclude migration/parity/audit records that are no longer useful to normal users.
- Keep detailed generated API reference available without allowing it to dominate the user journey.
- Remove duplicate or alias-only pages from navigation.
- Rewrite implementation-era warnings so that they describe current supported behavior accurately.
- Preserve real scientific limitations, release-gate semantics, and publication-reproduction boundaries.

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
8. “Verified implementation” does not mean “every generated artifact is automatically a released scientific artifact.”
9. Candidate → release gate → promoted artifact semantics must remain documented where they are part of the real interface.
10. Publication-artifact reproduction must not be implied unless separately verified.

---

## 3. Phase 0 — Reconcile the current product surface before restructuring

Before moving or rewriting documentation, establish the current supported product surface from the implemented repository.

This phase prevents the documentation migration from inheriting stale inventories or migration-era status files.

### 3.1 Audit registered workflows

Record the currently registered workflow IDs and their supported entry points.

At minimum verify:

- `beta1`
- `beta2`
- `validate`
- `compare`
- `human-database`
- `final-thg`

Create a small source-of-truth table in the implementation work notes covering:

- workflow ID;
- config section;
- CLI invocation;
- Python entry point;
- primary artifacts;
- release semantics;
- important limitations.

### 3.2 Audit the actual CLI surface

Document the current command matrix rather than inferring command names from workflow IDs.

Expected current surface:

| Workflow/task | Current CLI |
|---|---|
| β1 | `thg-run beta1 config.json` |
| β2 | `thg-run beta2 config.json` |
| Validation | `thg-run validate config.json` |
| Compare registered workflow | `thg-run compare config.json` |
| Human Database | `thg-run start config.json` with `workflow: "human-database"` |
| Final THG | `thg-run start config.json` with `workflow: "final-thg"` |
| Model comparison | `thg-compare ...` |
| Semantic comparison | `thg-compare ... --semantic` |
| Gapfill | `thg-gapfill ...` |
| Pathway workflow | `thg-pathway ...` |

Do not write documentation that implies named commands such as:

```text
thg-run human-database
thg-run final-thg
```

unless the implementation is changed to add them.

### 3.3 Reconcile the public Python API inventory

Audit the current intended public API against:

```text
docs/api/api-inventory.json
docs/api/workflow-api-inventory.json
```

The inventory must be updated before or during the information-architecture migration, not merely have its page paths renamed.

Explicitly review newer implemented surfaces including:

- `thg_protocol.validation`
- `thg_protocol.tasks`
- `thg_protocol.memote`
- semantic comparison functions;
- workflow configuration APIs;
- new gapfill strategy types;
- Phase 4 Human Database and final-THG entry points.

Every supported public symbol must have one canonical generated API owner.

Compatibility-only re-exports must not be rendered a second time.

### 3.4 Establish the new current capability registry

Do not continue using the legacy/parity-oriented capability matrix as the canonical current product-status source.

Create the capability registry model defined by the completed functional implementation plan.

Suggested schema:

```yaml
capability:
support_tier:
owner:
entry_point:
scientific_status:
implementation_status:
verification:
workflow_coverage:
known_limitations:
decision_log_refs:
```

Supported tiers should include:

```text
release-supported
research-supported
experimental
archived
rejected
```

The new registry should be the canonical source for current supported capability claims.

The older capability/parity registry and implementation-status matrix should become historical migration evidence after the new registry and tests exist.

### Acceptance criteria

- Every registered workflow has a documented canonical user entry point.
- Every installed command has one canonical CLI reference.
- Every supported public Python symbol has one generated API owner.
- New Phase 3–6 APIs are included where intended.
- A new current-product capability registry exists.
- Current documentation does not depend on stale migration-status data for product claims.

---

## 4. Target navigation

Use a smaller user-oriented navigation.

Recommended structure:

```yaml
nav:
  - Home: index.md

  - Getting started:
      - Installation: installation.md
      - Quickstart: quickstart.md
      - Workflow overview: workflows/index.md

  - THG workflows:
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

  - Reference:
      - Inputs, outputs, and configuration: reference/io-and-config.md
      - CLI: reference/cli.md
      - Python API:
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

  - About THG: about/history.md
```

### Optional MkDocs improvement

Consider enabling Material's section-index behavior so that:

- `workflows/index.md` can serve as the clickable **THG workflows** section index;
- `api/index.md` can serve as the clickable **Python API** section index.

If this is used, avoid an additional visible “Overview” child.

### Navigation acceptance target

The exact final count is not important, but the normal published sidebar should contain roughly **20–30 meaningful destinations**, not 50+ narrowly scoped or historical pages.

---

## 5. Phase 1 — Simplify Getting Started

### 5.1 Move project history out of Getting Started

**Current:** `docs/project-history.md`  
**Target:** `docs/about/history.md`

Rewrite it as a concise background page covering:

- scientific origin of THG;
- relationship to the 2023 protocol paper;
- software lineage where useful;
- distinction between scientific protocol, maintained implementation, and publication-artifact reproduction.

Remove or heavily shorten refactoring-closeout details that are no longer useful to normal users.

### 5.2 Merge API smoke test into Installation

**Current:** `docs/api-smoke-test.md`

Move useful content into:

```text
docs/installation.md
└── Verify your installation
```

The standalone page should then be removed from navigation.

Retain a compatibility stub only if required by the chosen URL migration policy.

### 5.3 Keep Getting Started minimal

The final section should be approximately:

```text
Getting started
├── Installation
├── Quickstart
└── Workflow overview
```

### Acceptance criteria

- Project history is not visible under Getting Started.
- API smoke test is not a standalone navigation item.
- A new user can install THG, verify it, run a representative quickstart, and understand the workflow model without reading migration/history pages.
- `mkdocs build --strict` passes.

---

## 6. Phase 2 — Make THG workflows the center of the site

The implemented workflow model is:

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

### 6.1 Workflow overview

Use:

`docs/workflows/index.md`

It should contain:

- a short explanation of THG;
- the lifecycle/workflow diagram;
- brief descriptions of β1, β2, Human Database, final THG, validation, and comparison;
- a “which workflow should I use?” table;
- links to the workflow guides;
- a clear publication-reproduction boundary.

It should **not** contain:

- detailed function listings;
- migration-status matrices;
- parity evidence;
- full API reference.

Comparison is a cross-workflow analysis capability rather than a lifecycle stage. Link it from the overview but document it under Tools → Model comparison and analysis.

### 6.2 THGβ1 workflow guide

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
## Candidate and release-gate lifecycle
## Validation
## Troubleshooting
## Next: THGβ2
```

Remove wording that describes the implementation itself as an unfinished candidate.

Retain the real operational lifecycle:

```text
candidate artifacts
→ beta1 release gate
→ release_beta1()
→ promoted THGβ1 artifacts
```

Do not imply that a workflow run automatically makes every candidate artifact a released THGβ1 artifact.

### 6.3 THGβ2 workflow guide

Suggested structure:

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
## Candidate and release-gate lifecycle
## Validation
## Troubleshooting
## Next: Final THG
```

Retain:

- verified β1 upstream requirements;
- candidate output semantics;
- `beta2_release_gate`;
- `release_beta2`;
- real limitations around external β1-equivalent inputs and evidence.

Remove obsolete “β2 is not implemented” language.

### 6.4 Human Database workflow guide

Rewrite the current Human Database documentation around the implemented workflow.

Suggested structure:

```text
# Human Database

## What this workflow does
## Offline snapshot mode
## Live/adapted collection mode
## Inputs and normalized records
## Evidence collection and caching
## Reconstruction stages
## Run with the CLI
## Run with Python
## Configuration
## Outputs and artifacts
## Validation
## Limitations
## Troubleshooting
## Next: Final THG
```

The guide must clearly state:

- offline reconstruction is a first-class supported path;
- live access is injected through an adapter;
- credentials/network access are not implicit;
- a paper-specific live pathway adapter is not automatically implied by workflow verification.

### 6.5 Final THG workflow guide

Target:

`docs/workflows/final-thg.md`

Suggested structure:

```text
# Final THG — Merge and validate

## Inputs
## Semantic merge plan
## Matching and conflict resolution
## Merge policies
## Apply and bounded repair
## Validation and task suite
## Run with the CLI
## Run with Python
## Configuration
## Outputs and artifacts
## Candidate/final artifact semantics
## Acceptance criteria
## Troubleshooting
```

Do not lead with legacy merge differences.

Do not imply exact reconstruction of the publication artifact.

The page should explain the maintained final-THG workflow and its current scientific/support boundary.

### 6.6 Validation workflow guide

Create:

`docs/workflows/validation.md`

It should clearly distinguish three related interfaces.

#### A. Registered validation workflow

The `validate` workflow covers:

- model input;
- reusable validation profiles;
- structural/chemical/topology checks;
- optional solver-backed checks;
- optional MEMOTE execution.

#### B. Metabolic task API

Document metabolic tasks as a separate versioned, non-mutating API.

Do not imply that `thg-run validate` currently executes an arbitrary task suite unless the implementation is changed to do so.

Explain that task suites are also used by final-THG validation where configured.

#### C. MEMOTE integration

Document:

- the maintained wrapper;
- optional dependency/install;
- command/version/log capture;
- JSON and HTML outputs;
- thresholds where available;
- distinction between MEMOTE tool failure and model-test results.

### 6.7 Reproducible and resumable runs

Rework:

`workflows/resumable-run.md`

into:

`docs/workflows/runs.md`

Document:

- run directories;
- manifests;
- artifact references;
- configuration snapshots;
- stage fingerprints;
- resume behavior;
- targeted invalidation;
- checksum recovery;
- interrupted-stage recovery;
- provenance;
- deterministic outputs where guaranteed.

### Acceptance criteria

- β1, β2, Human Database, final THG, and validation are directly visible under THG workflows.
- Each workflow page has clear inputs, execution, configuration, outputs, validation, and limitations.
- Workflow pages do not duplicate large API inventories.
- Obsolete migration warnings are removed.
- Real candidate/release-gate behavior remains documented.
- Publication-reproduction claims remain explicit and conservative.
- A user can follow the maintained workflow without visiting legacy/parity pages.

---

## 7. Phase 3 — Replace “Individual operations” with “Tools”

Remove the **Individual operations** concept from navigation.

The current grouping reflects internal code decomposition more than user intent.

Replace it with a smaller **Tools** section.

### 7.1 Model construction and enrichment

Merge material from:

- `workflows/database.md`
- `workflows/model-build.md`

into:

`docs/tools/model-construction.md`

Suggested structure:

```text
# Model construction and enrichment

## Constructing a model from normalized records
## Enriching an existing model
## Choosing reconstruction vs enrichment
## Inputs and outputs
## External services
## Examples
## Related API reference
```

Avoid duplicating the Human Database workflow guide.

### 7.2 Annotation and GPRs

Merge relevant material from annotation/identification and GPR-related operation docs into:

`docs/tools/annotation.md`

Cover:

- metabolite/reaction identification;
- annotation inventory;
- GPR lookup and normalization;
- location lookup;
- injected service-client boundaries.

Avoid duplicating β1/β2 workflow orchestration.

### 7.3 Pathways and gap filling

Merge:

- pathway implementation;
- gapfill.

Target:

`docs/tools/pathways-gapfill.md`

Keep distinct sections for:

- pathway implementation;
- deterministic gapfill;
- MILP-compatible strategy boundary;
- candidate universe;
- outputs and failure states.

Do not imply that gapfill is part of core β1/β2 correctness.

### 7.4 Model comparison and analysis

Merge or consolidate:

- network analysis;
- model comparison;
- semantic comparison;
- applicable consistency utilities;
- figures/reports if this keeps the Tools section simpler.

Target:

`docs/tools/analysis.md`

Cover:

- structural/network analysis;
- ordinary reaction comparison;
- semantic model comparison;
- workflow-run comparison;
- report generation;
- related visualization outputs.

Validation procedures required for release remain on the first-class Validation workflow page.

### 7.5 Cell-specific models

Retain a concise:

`docs/tools/cell-specific.md`

Keep it explicitly separate from core THG construction.

### 7.6 Remove Phase 0 foundations from user navigation

`workflows/phase0-foundations.md` should not remain a normal user-facing operation.

Move permanent concepts to Contributing → Architecture, then archive/remove the old page from published navigation.

### Acceptance criteria

- “Individual operations” no longer appears in navigation.
- β1 and β2 are not categorized as tools.
- “Phase 0 foundations” is not presented as a user operation.
- Tool pages are organized by user task.
- Tool guides link to generated API reference for exact signatures.
- Gapfill and cell-specific workflows remain explicitly optional extensions.

---

## 8. Phase 4 — Make Reference strictly reference material

Reference should answer exact interface questions, not duplicate workflow tutorials.

### 8.1 Inputs, outputs, and configuration

Create:

`docs/reference/io-and-config.md`

Cover or link:

- supported model formats;
- normalized record schema;
- task-suite schema;
- workflow configuration;
- run directory conventions;
- artifact roles;
- candidate vs promoted artifacts;
- provenance files;
- optional dependencies;
- solver/MEMOTE requirements.

Machine-readable schemas or large inventories should remain separate files and be linked rather than copied manually.

### 8.2 CLI reference

Create:

`docs/reference/cli.md`

Document all installed commands in one place.

For each command include:

- purpose;
- syntax;
- major arguments/options;
- installed entry point;
- workflow/task relationship;
- failure/exit behavior;
- links to user guides.

Explicitly document the difference between:

```text
thg-run start
thg-run beta1
thg-run beta2
thg-run validate
thg-run compare
thg-compare
```

and note that Human Database/final THG currently use generic `thg-run start` unless the CLI is expanded.

### 8.3 Python API

Retain generated `mkdocstrings` pages with one canonical owner per symbol.

Recommended visible grouping:

- Core and I/O
- Construction
- Annotation and GPR
- Workflows
- Analysis
- Services

Review whether Figures should remain a standalone generated page or fold into Analysis.

Add newly supported public modules/symbols to the inventory where appropriate.

### 8.4 Remove generic Examples navigation

Do not expose `examples/README.md` as a generic Reference destination.

Keep fixtures/examples under `docs/examples/`, but link them contextually from:

- Quickstart;
- β1;
- β2;
- Human Database;
- Validation;
- Tools;
- CLI/API pages.

The fixture catalog and usage notes should move into the relevant guides or I/O/config reference.

### 8.5 API and workflow inventory migration

Update in the same change:

```text
docs/api/api-inventory.json
docs/api/workflow-api-inventory.json
```

Requirements:

- every renamed page path is updated;
- every newly public supported symbol is represented;
- every workflow guide links to its canonical symbols;
- every canonical symbol is generated exactly once;
- compatibility exports remain non-duplicated;
- CLI inventory ownership remains consistent with packaging and CI tests.

### Acceptance criteria

- Reference pages contain exact contracts, formats, options, or generated API documentation.
- Tutorials and scientific procedures are not duplicated in Reference.
- Generic “Examples” is removed from navigation.
- Newly implemented public APIs are not missing from the generated reference.
- Inventory tests pass.

---

## 9. Phase 5 — Reduce Maintainers to three substantial pages

Rename **Maintainers** to **Contributing**.

Target:

```text
Contributing
├── Development and releases
├── Architecture
└── Repository and data management
```

### 9.1 Development and releases

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

### 9.2 Architecture

Merge permanent architectural concepts from:

- `architecture.md`
- `api-contracts.md`
- `service-boundary-audit.md`
- Phase 0/foundation documentation

into:

`docs/contributing/architecture.md`

Suggested structure:

```text
# Architecture

## Package boundaries
## Workflow registry and DAGs
## Model ownership and mutation
## Evidence → proposal → decision → mutation
## Artifact chaining and resumability
## External service boundaries
## API design principles
## Validation boundaries
## Optional dependency boundaries
```

Do not preserve audit/checkpoint wording in the primary architecture page.

### 9.3 Repository and data management

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

Large generated inventories/checksum lists may remain machine-readable support files rather than navigation pages.

### Acceptance criteria

- No more than three primary Contributing destinations.
- Release instructions have one canonical location.
- Architecture has one canonical location.
- Repository/artifact/LFS ownership has one canonical location.
- Short maintainer pages no longer exist only to hold a few paragraphs.

---

## 10. Phase 6 — Replace current-status migration evidence with the new capability model

The published documentation should not require users to navigate refactoring/parity evidence.

### 10.1 Create the new current product capability registry

Implement the support-tier registry defined in Phase 0.

The registry should describe:

- current entry point;
- support tier;
- scientific status;
- implementation status;
- verification level;
- workflow coverage;
- known limitations;
- ownership.

Use it for current support claims.

### 10.2 Reconcile stale old status data before archival

Before archiving old capability/status files:

- compare old claims with the completed functional implementation tracker;
- identify stale entries;
- do not silently preserve stale product-status claims;
- move any durable scientific caveats to current user/reference documentation.

### 10.3 Archive historical migration evidence

Review for archival/removal from normal navigation:

```text
service-boundary-audit.md
legacy-workflows.md
legacy-api-inventory.md
parity/README.md
parity/contracts/**
api-contracts.md
protocol/implementation-status.md
protocol/capability-status.md
protocol/capability-evidence.json
workflows/phase0-foundations.md
```

Potential archive locations:

```text
docs/internal/
docs/history/
docs/plans/archive/
```

Extend `exclude_docs` as needed.

Example:

```yaml
exclude_docs: |
  plans/**
  internal/**
  history/**
```

### 10.4 Update tests to consume the new registry

Replace tests that require the public implementation-status matrix to exactly mirror the legacy capability-evidence file.

New tests should instead validate:

- support-tier schema;
- controlled values;
- current entry points;
- evidence/test paths where applicable;
- known limitations;
- unique capability IDs;
- no contradiction with intended current support claims.

Historical migration evidence may still have integrity tests, but it should no longer be the canonical source for current product support.

### Acceptance criteria

- Current support claims come from the new capability registry.
- Old parity/migration status files are clearly historical.
- Stale claims such as “β2 not implemented” or “tasks archived” are not treated as current product truth.
- No alias-only capability page appears in navigation.
- Historical evidence remains available where worth preserving.
- Current and historical status systems have clearly different ownership.

---

## 11. Phase 7 — Rewrite the Home page

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
- Merge and validate final THG candidates
- Validate or compare models independently
- Use supporting analysis and extension tools

## Documentation

Getting Started
THG Workflows
Tools
Reference
Contributing
About THG
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
- Primary calls to action are immediately visible.
- The full workflow is explained in the workflow overview, not duplicated on Home.
- Home does not imply publication-artifact reproduction.

---

## 12. Current-to-target mapping

| Current page/area | Target action |
|---|---|
| `project-history.md` | Move/shorten to `about/history.md` |
| `api-smoke-test.md` | Merge into Installation |
| `workflow-overview.md` | Merge/rework into `workflows/index.md` |
| `protocol/index.md` | Fold durable current workflow material into `workflows/index.md`; retire duplicate overview |
| `protocol/reference-model.md` | Split useful content between β1 and β2 guides |
| `protocol/human-database.md` | Promote/rewrite as primary Human Database workflow guide |
| `protocol/merge-and-validate.md` | Rename/rewrite as Final THG guide |
| `protocol/end-to-end-example.md` | Fold into Quickstart and/or relevant workflow guides |
| `workflows/beta1.md` | Promote/rewrite as primary β1 workflow guide |
| `workflows/beta2.md` | Promote/rewrite as primary β2 workflow guide |
| `usage.md` | Convert useful chooser content into workflow/tools overview; remove standalone route if redundant |
| `workflows/database.md` | Merge into Model construction and enrichment |
| `workflows/model-build.md` | Merge into Model construction and enrichment |
| `workflows/annotation.md` | Merge into Annotation and GPRs |
| `workflows/pathway.md` | Merge into Pathways and gap filling |
| `workflows/gapfill.md` | Merge into Pathways and gap filling |
| `workflows/merge.md` | Fold into Final THG and update workflow/API inventories |
| `workflows/network-analysis.md` | Merge into Model comparison and analysis / Validation |
| `workflows/comparison.md` | Merge into Model comparison and analysis |
| `workflows/memote.md` | Fold current content into Validation |
| `workflows/resumable-run.md` | Rework as `workflows/runs.md` |
| `workflows/phase0-foundations.md` | Move durable concepts to Architecture; archive/remove |
| `workflows/cell-specific.md` | Retain as concise Tool guide |
| `workflows/figures.md` | Fold into Analysis unless its content warrants a separate Tool page |
| `examples/README.md` | Remove from nav; link examples contextually |
| `data-and-model-files.md` | Rework/merge into Reference → I/O and configuration |
| `development.md` | Merge into Development and releases |
| `documentation-contributing.md` | Merge into Development and releases |
| `release-validation.md` | Merge into Development and releases |
| `dependency-compatibility.md` | Merge durable policy into Development and releases |
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
| `protocol/implementation-status.md` | Archive as historical migration status after replacement registry exists |
| `protocol/capability-evidence.json` | Archive as historical evidence after replacement registry exists |
| `api/**` | Keep generated API reference, after current-surface reconciliation |

---

## 13. Content cleanup rules

### 13.1 Rewrite obsolete implementation wording

Search for phrases such as:

- “candidate-stage implementation” when referring to implementation maturity;
- “not implemented” where the capability is now verified;
- “current package does not contain…” statements that are no longer true;
- “conceptual mapping only” where a real workflow now exists;
- “refactoring checkpoint”;
- “parity remediation plan”;
- “closeout requirements”;
- references to the functional implementation plan as future work.

### 13.2 Preserve real candidate/release wording

Do **not** blindly remove the word “candidate.”

Keep it when describing real output lifecycle such as:

```text
candidate model
→ validation/release gate
→ promoted release artifact
```

Remove only wording that incorrectly describes the implementation itself as unfinished.

### 13.3 Verify claims before rewriting

For each completion-language change, verify support against:

- implementation source;
- unit/integration acceptance tests;
- release-gate behavior;
- current product capability registry.

Distinguish:

- release-supported behavior;
- research-supported behavior;
- external integrations;
- injected/live-service behavior;
- solver-heavy optional behavior;
- publication-reproduction status.

### 13.4 Use user-oriented framing

Prefer:

> Run the β2 workflow using a verified β1 artifact.

over:

> The maintained branch should instead reference the β1 export.

Prefer:

> The workflow writes the following artifacts…

over:

> The current maintained implementation exposes…

### 13.5 Avoid repeated caveats

Each permanent caveat should have one canonical owner.

Examples:

- publication-artifact reproduction;
- live-service injection;
- solver dependency;
- candidate/release promotion;
- external β1-equivalent policy.

Workflow pages may link to the canonical explanation rather than reproducing paragraphs of repeated warnings.

---

## 14. Link and URL migration strategy

Before deleting or renaming pages:

1. Find inbound links in `docs/`, README files, issue templates, code comments, and tests.
2. Update links to canonical replacement pages.
3. Choose a compatibility policy for each high-risk route:
   - redirect mechanism; or
   - minimal compatibility stub.
4. Do not keep duplicate full pages solely for link compatibility.
5. Ensure the deployment workflow and tests exercise the chosen compatibility behavior.

Potential high-risk routes include:

```text
protocol/reference-model.md
protocol/merge-and-validate.md
protocol/end-to-end-example.md
usage.md
development.md
data-and-model-files.md
examples/README.md
workflows/memote.md
workflows/resumable-run.md
```

Do not assume a Markdown alias automatically creates an external HTTP redirect.

---

## 15. Validation and tests

The restructuring is complete only when the generated site, API inventory, workflow inventory, capability registry, and executable documentation all agree.

### Required checks

```bash
python -m pip install -e ".[docs,dev]"
mkdocs build --strict
pytest tests/docs
pytest tests/unit/test_ci_matrix_policy.py
```

Update or replace capability/status tests to validate the new support-tier registry.

### Add navigation tests

Assert that required top-level sections and pages exist.

Assert that obsolete labels/routes are absent, including:

```text
Individual operations
Phase 0 foundations
Capability and evidence status
Published protocol coverage
```

unless retained intentionally outside normal navigation.

### Add generated-site archive tests

Assert that archived/internal files do not appear in the generated site.

### Add API inventory tests

Assert that:

- every canonical symbol is generated exactly once;
- every inventory page exists;
- every workflow guide links to its canonical API symbols;
- every installed CLI command is represented;
- newly supported validation/tasks/MEMOTE/comparison/gapfill surfaces are included where intended.

### Add executable workflow documentation tests

Every first-class workflow guide should have at least one small deterministic example/config covered by tests.

Recommended smoke coverage:

- β1;
- β2;
- validation;
- Human Database;
- final THG;
- semantic comparison.

These tests do not need large scientific models. Use small deterministic fixtures.

They should catch drift in:

- workflow IDs;
- config section names;
- supported config keys;
- CLI syntax;
- artifact roles;
- run-directory behavior.

### Preserve practical example fixtures

Removing `examples/README.md` from navigation must not remove the JSON/model fixtures used by documentation tests.

### Manual review checklist

- [ ] Homepage is concise and routes users correctly.
- [ ] Getting Started contains only onboarding material.
- [ ] β1, β2, Human Database, final THG, and Validation are obvious from the sidebar.
- [ ] No first-time user must understand legacy parity terminology.
- [ ] No duplicate status/alias pages appear in navigation.
- [ ] “Individual operations” is gone.
- [ ] “Phase 0 foundations” is gone from user navigation.
- [ ] Maintainer material is consolidated into three substantial pages.
- [ ] Examples are linked from relevant guides instead of exposed generically.
- [ ] Workflow guides do not reproduce full generated API reference.
- [ ] Validation docs distinguish validate workflow, metabolic-task API, and MEMOTE.
- [ ] Human Database/final THG docs use the actual current CLI surface.
- [ ] Candidate/release-gate semantics remain accurate.
- [ ] Publication-artifact reproduction is not implied.
- [ ] API reference contains all intended current public surfaces.
- [ ] Archived/internal documentation is excluded from MkDocs.
- [ ] Search results do not prominently surface obsolete implementation warnings.
- [ ] All renamed/moved internal links resolve.
- [ ] `mkdocs build --strict` passes.
- [ ] `pytest tests/docs` passes.

---

## 16. Suggested implementation order

### Step 1 — Current-interface preflight

Before moving pages, record:

- registered workflows;
- CLI commands;
- config sections and keys;
- current public Python API;
- release-gate semantics;
- current support/limitation claims.

Update the canonical API/workflow inventories as needed.

### Step 2 — Introduce the new capability registry

Create the current-product support-tier registry and tests.

Do not archive the old capability/status files until the new registry is authoritative.

### Step 3 — Create the new documentation skeleton

Create as needed:

```text
docs/
├── about/
├── workflows/
├── tools/
├── reference/
└── contributing/
```

Do not delete old pages yet.

### Step 4 — Rewrite the core user journey

In order:

1. Home
2. Installation
3. Quickstart
4. Workflow overview
5. β1
6. β2
7. Human Database
8. Final THG
9. Validation
10. Reproducible/resumable runs

### Step 5 — Consolidate Tools

Create the target Tool pages and migrate durable operation content.

### Step 6 — Consolidate Reference

Create I/O/config and CLI reference.

Update generated API grouping and inventories in the same change.

### Step 7 — Consolidate Contributing

Build the three maintainer pages before removing their source pages.

### Step 8 — Extract and archive historical material

Move durable concepts first, then archive:

- legacy;
- parity;
- audit;
- migration status;
- old capability evidence;
- Phase 0 implementation notes.

### Step 9 — Replace `mkdocs.yml` navigation

Switch to the new hierarchy only after replacement pages exist.

### Step 10 — Fix links and compatibility routes

Apply the chosen redirect or compatibility-stub policy.

### Step 11 — Run strict validation

Run:

```bash
mkdocs build --strict
pytest tests/docs
pytest tests/unit/test_ci_matrix_policy.py
```

plus the new capability-registry and workflow-doc smoke tests.

### Step 12 — Remove obsolete pages

Delete pages that are fully superseded or retain them only in excluded historical/internal locations.

---

## 17. Definition of done

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
10. Current support claims come from the new capability registry.
11. Stale migration status is not used as current product truth.
12. Obsolete incomplete-implementation language has been updated.
13. Candidate/release-gate semantics remain documented where real.
14. Publication-artifact reproduction is not implied without verification.
15. Home is concise and routes readers to the appropriate documentation.
16. API/workflow inventories match the current supported product surface.
17. Validation/tasks/MEMOTE APIs have clear documentation ownership.
18. Human Database/final-THG docs use the actual current CLI entry points.
19. Required and forbidden navigation routes are checked automatically.
20. First-class workflow examples are executable in docs tests.
21. `mkdocs build --strict` and the documentation contract tests pass.
22. Existing internal links and high-value external-compatible paths are handled deliberately.
23. The documentation reads like documentation for the maintained THG product, not like documentation for an ongoing refactoring project.

---

## 18. Non-goals

This restructuring should **not**:

- collapse all THG workflows into one enormous page;
- remove detailed Python API documentation;
- delete historically useful records without first considering archival value;
- hide real scientific limitations or uncertainty;
- erase candidate/release-gate lifecycle semantics;
- imply publication-artifact reproduction;
- invent CLI commands that are not currently implemented;
- change scientific behavior merely to simplify documentation;
- duplicate the functional implementation plan.

The goal is to improve information architecture and presentation of already implemented functionality.

---

## 19. Final principle

When deciding whether a page deserves its own navigation entry, ask:

> **Does a user intentionally arrive at the documentation wanting to do or look up this specific thing?**

If the answer is no, the material should usually be:

- a section within a broader page;
- linked contextually;
- generated reference;
- or archived/internal documentation.

Use this principle for future documentation additions so that the sidebar does not gradually return to its current level of fragmentation.
