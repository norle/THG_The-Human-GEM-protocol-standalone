# THG Workflow Structure Refactor — Implementation Plan

## 1. Objective

Refactor the THG source tree so that package boundaries match the actual architecture:

```text
scientific domain code
        ↓
workflow-specific stage adapters and DAG definitions
        ↓
generic resumable execution runtime
```

The refactor must preserve the existing public workflow namespace and behavior while moving generic execution mechanics into a separate runtime implementation layer.

The intended end state is:

- `thg_protocol.workflow` remains the only workflow namespace.
- `thg_protocol.runtime` contains generic resumable execution machinery.
- scientific behavior remains in domain packages such as `curation`, `analysis`, `annotation`, `gapfill`, `pathway`, and related packages.
- shared COBRA model loading/saving moves to `thg_protocol.io.models`.
- no `pipelines/` package is introduced.
- no top-level `provenance/` package is introduced.
- workflow IDs, stage IDs, artifact roles, CLI semantics, run configuration semantics, and resumability remain unchanged.

---

## 2. Architectural Boundaries

### 2.1 Dependency direction

The intended dependency direction is:

```text
domain packages
    ↑ called by
workflow adapters
    ↓ provide resolved Stage sequence to
runtime
```

Runtime must not discover or import built-in THG workflows.

A practical module dependency rule is:

```text
runtime
  ├─ may depend on Python stdlib and generic package internals
  └─ must not depend on thg_protocol.workflow or scientific workflow modules

workflow
  ├─ may depend on runtime
  ├─ may depend on domain packages
  └─ owns configuration-to-stage adaptation and DAG composition

domain packages
  ├─ own scientific algorithms and transformations
  └─ should not depend on workflow execution mechanics
```

### 2.2 Temporary compatibility exception

`workflow/proposals.py` and `workflow/ids.py` remain under `workflow/` initially because they are already part of workflow records and compatibility contracts.

Some domain code currently imports these modules. That dependency is accepted temporarily and is not a blocker for this refactor.

Generic helpers currently imported by domain code, such as hashing and parallel execution, should move to `runtime` and callers should be updated.

---

## 3. Target Structure

```text
src/thg_protocol/
├── runtime/
│   ├── __init__.py
│   ├── engine.py
│   ├── stage.py
│   ├── manifest.py
│   ├── artifacts.py
│   ├── locking.py
│   ├── hashing.py
│   └── concurrency.py
│
├── workflow/
│   ├── __init__.py
│   ├── cli.py
│   ├── config.py
│   ├── runner.py
│   ├── registry.py
│   ├── evidence.py
│   ├── proposals.py
│   ├── ids.py
│   ├── foundation.py
│   ├── reference.py
│   │
│   ├── beta1/
│   │   ├── __init__.py
│   │   ├── definition.py
│   │   ├── input.py
│   │   ├── evidence.py
│   │   ├── proposals.py
│   │   ├── apply.py
│   │   ├── validation.py
│   │   └── export.py
│   │
│   ├── beta2/
│   │   ├── __init__.py
│   │   ├── definition.py
│   │   ├── input.py
│   │   ├── evidence.py
│   │   ├── gpr.py
│   │   ├── localization.py
│   │   ├── expansion.py
│   │   ├── validation.py
│   │   └── export.py
│   │
│   ├── gapfill.py
│   ├── validation.py
│   ├── cell_specific.py
│   ├── pathway.py
│   ├── compare.py
│   ├── human_database.py
│   └── final_thg.py
│
├── curation/
│   ├── __init__.py
│   ├── beta1.py
│   ├── beta2.py
│   └── go.py
│
├── analysis/
├── annotation/
├── cell_specific/
├── gapfill/
├── gpr/
├── merge/
├── model_build/
├── pathway/
├── services/
│
├── io/
│   ├── __init__.py
│   └── models.py
│
├── config.py
├── validation.py
├── tasks.py
├── memote.py
├── database.py
├── database_parsing.py
└── reaction_config.py
```

---

## 4. Key Design Decisions

### 4.1 `workflow.runner` remains the public facade

The following imports must continue to work:

```python
from thg_protocol.workflow.runner import start, resume, get_status
```

`workflow.runner` owns:

- loading workflow configuration,
- resolving the selected workflow definition,
- selecting the correct concrete stage sequence,
- validating resume compatibility,
- calling the runtime engine.

It should not own the stage execution loop.

### 4.2 `runtime.engine` receives resolved stages

`runtime.engine` must receive a concrete stage sequence and already-resolved run inputs.

It owns:

- stage iteration,
- restart behavior,
- forced invalidation,
- attempt numbering,
- temporary work directories,
- artifact promotion,
- failure directories,
- interruption handling,
- stage result validation,
- manifest updates,
- artifact verification.

It must not:

- import `workflow.registry`,
- call `get_workflow()`,
- inspect β1/β2/gapfill-specific configuration,
- determine which built-in workflow exists,
- select fixture versus scientific DAGs.

### 4.3 `runtime.stage` is workflow-agnostic

Do not move the current `workflow/stages.py` unchanged.

The runtime `Stage` contract must not import `WorkflowConfig`.

`StageContext.config` should be opaque to runtime, for example:

```python
@dataclass(frozen=True)
class StageContext:
    config: object
    run_dir: Path
    manifest: Mapping[str, object]
    log_path: Path | None = None
```

Workflow adapters can narrow the type when they consume it.

Alternatively, use a generic type parameter if that materially improves clarity without complicating the API.

The runtime stage module should own only:

- `Stage`,
- `StageContext`,
- `StageResult`,
- generic dependency-output lookup helpers if they are runtime-generic.

COBRA model loading must not live here.

### 4.4 Manifest creation must be decoupled from workflow configuration

Do not move the current `workflow/manifest.py` unchanged.

`runtime.manifest` must not import `workflow.config`.

Instead of:

```python
new_workflow_manifest(config, stages)
```

prefer an API conceptually like:

```python
new_manifest(
    workflow_id=config.workflow,
    run_id=config.run.name,
    config_sha256=config_sha256,
    stages=stages,
)
```

`workflow.runner` or `workflow.config` computes the config hash.

`runtime.manifest` owns:

- manifest schema,
- validation,
- load,
- atomic write,
- timestamps,
- step status representation.

### 4.5 `reference` is an explicit workflow composition

Add `workflow/reference.py`.

It owns the canonical composition:

```text
β1
 ↓
β2
 ↓
β2 gate
 ↓
reference gapfill
```

It contains no scientific implementation.

Its purpose is to preserve the existing `reference` workflow ID and:

```bash
thg-run reference ...
```

behavior.

### 4.6 Registry bootstrap is explicit

`workflow.registry` owns built-in workflow registration.

Remove registration responsibility from `foundation_stages.py`.

Preferred pattern:

```python
REGISTRY = WorkflowRegistry()

def register_builtin_workflows() -> None:
    for definition in (...):
        REGISTRY.register(definition)

register_builtin_workflows()
```

Definitions should come from their owning workflow modules.

For example:

```python
from .beta1.definition import BETA1_WORKFLOW
from .beta2.definition import BETA2_WORKFLOW
from .reference import REFERENCE_WORKFLOW
```

The import of `thg_protocol.workflow.registry` must continue to result in all built-in workflows being available.

---

## 5. Compatibility Strategy

The refactor should preserve behavior before removing implementation modules.

### 5.1 Stable public modules

Keep these as real public modules:

```text
workflow/__init__.py
workflow/runner.py
workflow/cli.py
workflow/config.py
workflow/registry.py
workflow/evidence.py
workflow/proposals.py
workflow/ids.py
```

### 5.2 Temporary compatibility re-exports

Initially retain thin compatibility modules for documented or existing imports:

```text
workflow/artifacts.py
workflow/hashing.py
workflow/manifest.py
workflow/stages.py
workflow/lock.py
workflow/parallel.py
workflow/registered_runner.py
```

Examples:

```python
# workflow/hashing.py
from thg_protocol.runtime.hashing import *
```

and:

```python
# workflow/stages.py
from thg_protocol.runtime.stage import Stage, StageContext, StageResult
```

`workflow/registered_runner.py` should become aliases/wrappers only.

Do not leave execution logic duplicated between compatibility modules and runtime.

### 5.3 Preserve `workflow.__init__` exports

Existing public names exposed through `thg_protocol.workflow` should continue to resolve, especially:

- workflow runner API,
- registry API,
- artifact-reference API,
- evidence records,
- proposals,
- deterministic IDs.

Compatibility can be removed later only after a separate deprecation decision.

---

## 6. Proposed Runtime APIs

The exact signatures may change during implementation, but the boundary should resemble the following.

### 6.1 Stage contract

```python
class Stage(Protocol):
    id: str
    dependencies: tuple[str, ...]
    implementation_version: int

    def enabled(self, config: object) -> bool: ...

    def fingerprint_data(
        self,
        context: StageContext,
    ) -> Mapping[str, object]: ...

    def run(
        self,
        context: StageContext,
        work_dir: Path,
    ) -> StageResult: ...

    def validate(self, result: StageResult) -> None: ...
```

### 6.2 Runtime execution

Conceptually:

```python
def execute(
    *,
    config: object,
    run_dir: Path,
    manifest: dict[str, object],
    stages: tuple[Stage, ...],
    force_step: str | None = None,
) -> Path:
    ...
```

The runtime may accept additional generic execution metadata if required.

It must not accept a workflow ID and then look it up.

### 6.3 Workflow definition resolution

Prefer workflow-side resolution:

```python
@dataclass(frozen=True)
class WorkflowDefinition:
    id: str
    ...

    def resolve(self, config: WorkflowConfig) -> tuple[Stage, ...]:
        ...
```

This replaces hard-coded scientific/fixture selection in the runtime runner.

If keeping `stages_for()` initially reduces migration risk, keep it temporarily but move the decision that determines the mode out of runtime.

---

## 7. Model I/O Boundary

Add:

```text
thg_protocol/io/models.py
```

with shared lazy COBRA imports.

Suggested API:

```python
def load_model(path: str | Path) -> Any:
    ...

def save_model(model: Any, path: str | Path) -> Path:
    ...

def save_json(model: Any, path: str | Path) -> Path:
    ...

def save_sbml(model: Any, path: str | Path) -> Path:
    ...
```

Required behavior:

- JSON loads with COBRA JSON loader.
- non-JSON supported model inputs use SBML loader.
- JSON saves use COBRA JSON writer.
- SBML saves use COBRA SBML writer.
- COBRA imports remain inside functions when practical.
- public domain-level `load_model` wrappers may remain and delegate here.

Migrate duplicated helpers from:

- `workflow/stages.py`,
- β1 adapters,
- β2 adapters,
- foundation/validation adapters,
- other modules discovered during refactor.

---

## 8. Detailed Migration Phases

## Phase 0 — Freeze contracts

### Goal

Capture the behavior that must not change before moving files.

### Tasks

Add or confirm tests for:

- `thg_protocol.workflow.runner.start`
- `thg_protocol.workflow.runner.resume`
- `thg_protocol.workflow.runner.get_status`
- `thg_protocol.workflow.cli.main`
- `thg_protocol.workflow.registry`
- `thg_protocol.workflow` re-exports
- installed `thg-run` entry point
- existing workflow IDs
- existing stage IDs
- existing manifest schema
- existing artifact roles
- force-step descendant invalidation
- resume behavior
- config snapshot matching
- `n_jobs` resume behavior
- interruption/failure state transitions
- stale lock behavior
- CLI exit codes
- CLI verbosity/logging behavior
- reference workflow composition

### Add architectural characterization tests

Add tests that capture the currently supported registered IDs, for example:

```python
EXPECTED_WORKFLOWS = {
    "beta1",
    "beta2",
    "gapfill",
    "reference",
    "validate",
    "compare",
    "cell-specific",
    "pathway",
    "human-database",
    "final-thg",
}
```

Use the actual current registry as the source of truth when writing the test.

### Exit criteria

- baseline full test suite passes,
- docs build passes,
- import-contract tests pass,
- workflow ID/stage ID snapshots are captured.

---

## Phase 1 — Introduce `runtime/` primitives

### Goal

Create the runtime package without changing public behavior.

### Move/refactor

```text
workflow/hashing.py   -> runtime/hashing.py
workflow/parallel.py  -> runtime/concurrency.py
workflow/lock.py      -> runtime/locking.py
workflow/artifacts.py -> runtime/artifacts.py
```

Create compatibility re-exports at the old paths.

### Update generic callers

Change domain callers such as:

```python
thg_protocol.workflow.hashing
thg_protocol.workflow.parallel
```

to:

```python
thg_protocol.runtime.hashing
thg_protocol.runtime.concurrency
```

Do not change proposal/ID imports in this phase unless needed.

### Exit criteria

- runtime modules have no scientific imports,
- old workflow imports still work,
- tests and docs pass.

---

## Phase 2 — Extract runtime stage contract

### Goal

Move the Stage execution contract without creating a runtime → workflow dependency.

### Tasks

Create:

```text
runtime/stage.py
```

Move:

- `Stage`
- `StageContext`
- `StageResult`
- generic dependency artifact lookup helpers

Do not move:

- `_load_cobra_model`

Move COBRA loading later to `io/models.py`, or create the new I/O module now if required to avoid temporary duplication.

Keep:

```text
workflow/stages.py
```

as a compatibility facade.

### Add dependency test

Add a test or static check that:

```text
runtime/stage.py
```

does not import:

```text
thg_protocol.workflow
thg_protocol.curation
thg_protocol.gapfill
thg_protocol.pathway
...
```

### Exit criteria

- runtime stage types are workflow-agnostic,
- existing stage implementations run unchanged through compatibility imports,
- tests pass.

---

## Phase 3 — Extract manifest runtime

### Goal

Make manifest persistence generic.

### Tasks

Create:

```text
runtime/manifest.py
```

Move:

- manifest schema,
- validation,
- atomic writing,
- loading,
- timestamp helpers.

Refactor manifest construction so it accepts resolved metadata instead of `WorkflowConfig`.

Keep:

```text
workflow/manifest.py
```

as a compatibility facade.

### Exit criteria

- `runtime.manifest` imports no workflow config,
- manifest JSON output is byte-compatible where ordering/content is already part of tests, or semantically identical otherwise,
- existing resumable runs remain readable,
- tests pass.

---

## Phase 4 — Split `registered_runner`

### Goal

Separate workflow resolution from execution.

### Runtime side

Create:

```text
runtime/engine.py
```

Move only generic execution mechanics:

- `_descendants`
- `_entry`
- manifest write/update helpers
- invalidation
- artifact validity checks
- attempt calculation
- stage loop
- temporary directory handling
- artifact promotion
- error handling
- interruption handling
- force-step handling.

### Workflow side

Expand:

```text
workflow/runner.py
```

to own:

- `start`
- `resume`
- `get_status`
- config loading
- snapshot validation
- registry lookup
- workflow definition resolution
- manifest/config compatibility checks
- calling `runtime.engine.execute`.

### Important

Preserve:

```python
WorkflowError
start
resume
get_status
```

and existing semantics.

### Logging

Keep runtime stage execution visible through the existing workflow logging surface.

Either:

- runtime explicitly logs to `thg_protocol.workflow`, or
- configure logger propagation so the CLI and run log continue to capture runtime engine messages.

Add tests for verbose CLI output and `logs/run.log`.

### Compatibility

Replace:

```text
workflow/registered_runner.py
```

with thin wrappers/aliases only.

### Exit criteria

- runtime engine does not import registry or workflow definitions,
- workflow runner resolves stages before runtime is called,
- old public imports work,
- tests pass.

---

## Phase 5 — Refactor registry and foundation ownership

### Goal

Make workflow registration explicit and remove cross-workflow ownership from foundation fixtures.

### Tasks

Move fixture-only stages from:

```text
workflow/foundation_stages.py
```

to:

```text
workflow/foundation.py
```

Move validation-specific scientific adapters to:

```text
workflow/validation.py
```

Remove built-in registration from foundation.

Refactor:

```text
workflow/registry.py
```

so it explicitly registers definitions from their owners.

### Add `reference.py`

Create:

```text
workflow/reference.py
```

It should compose existing stage definitions without containing scientific logic.

### Exit criteria

- `foundation.py` contains fixture concerns only,
- importing `workflow.registry` registers the same built-in IDs,
- `reference` remains registered and runnable,
- tests pass.

---

## Phase 6 — Split β1 adapters

### Goal

Replace `workflow/beta1_stages.py` with an explicit β1 workflow package.

### Create

```text
workflow/beta1/
├── __init__.py
├── definition.py
├── input.py
├── evidence.py
├── proposals.py
├── apply.py
├── validation.py
└── export.py
```

### Suggested ownership

#### `definition.py`

Own:

- `DETAILED_BETA1_STAGE_IDS`
- stage ordering
- dependencies
- `WorkflowDefinition`
- fixture/scientific resolution for β1 if still needed.

#### `input.py`

Own:

- input model adapter
- inventory stage if it remains closely tied to ingestion.

#### `evidence.py`

Own:

- metabolite evidence collection
- metabolite identity resolution
- reaction evidence collection
- reaction identity resolution
- gene normalization/GPR evidence wiring where appropriate.

#### `proposals.py`

Own:

- curation proposal generation
- balance proposal generation.

#### `apply.py`

Own:

- curation application
- balance application
- cleanup/deduplication application.

#### `validation.py`

Own:

- β1 validation/release gate adapter wiring.

#### `export.py`

Own:

- final model export
- signatures
- ledgers
- validation bundle assembly.

### Rules

- no scientific algorithm rewrite,
- calls continue to go into `curation.beta1`,
- preserve stage IDs,
- preserve implementation-version semantics unless an actual behavior change requires bumping them,
- preserve artifact roles and filenames unless explicitly covered by compatibility tests.

### Compatibility

Keep:

```text
workflow/beta1_stages.py
```

as a temporary facade exposing names required by tests/docs/importers.

### Exit criteria

- a developer can locate β1 orchestration under `workflow/beta1/`,
- scientific β1 operations remain in `curation/beta1.py`,
- all β1 integration tests pass.

---

## Phase 7 — Split β2 adapters

### Goal

Replace `workflow/beta2_stages.py` with an explicit β2 workflow package.

### Create

```text
workflow/beta2/
├── __init__.py
├── definition.py
├── input.py
├── evidence.py
├── gpr.py
├── localization.py
├── expansion.py
├── validation.py
└── export.py
```

### Suggested ownership

#### `definition.py`

Own:

- `DETAILED_BETA2_STAGE_IDS`
- stage ordering
- dependencies
- β2 workflow definition.

#### `input.py`

Own:

- β1 artifact resolution/input loading.

#### `evidence.py`

Own:

- catalysis evidence
- generic recorded evidence handling
- source metadata and snapshots.

#### `gpr.py`

Own:

- GPR evidence collection
- GPR resolution
- related checkpoints.

#### `localization.py`

Own:

- location evidence
- compartment evidence resolution
- complex/isoenzyme location inference.

#### `expansion.py`

Own:

- expansion-plan generation
- expansion decisions
- model expansion
- consolidation.

#### `validation.py`

Own:

- β2 gate and validation adapters.

#### `export.py`

Own:

- final β2 candidate bundle export.

### Compatibility

Keep:

```text
workflow/beta2_stages.py
```

as a temporary facade.

### Exit criteria

- β2 stage wiring is findable under `workflow/beta2/`,
- β2 scientific behavior remains in `curation/beta2.py`,
- existing β2 replay/offline/resume tests pass.

---

## Phase 8 — Split remaining workflow adapter monoliths

### Goal

Replace generic “phase” and “scientific” adapter files with workflow-owned modules.

### Mapping

```text
workflow/gapfill_stages.py
    -> workflow/gapfill.py

workflow/scientific_stages.py
    -> workflow/cell_specific.py
    -> workflow/pathway.py
    -> workflow/compare.py

workflow/phase4_stages.py
    -> workflow/human_database.py
    -> workflow/final_thg.py
```

Move validation adapters to:

```text
workflow/validation.py
```

### Rules

- preserve IDs,
- preserve artifact roles,
- preserve CLI aliases,
- no domain logic migration unless the code is clearly orchestration-only.

### Exit criteria

- each workflow has one obvious owner,
- no `scientific_stages.py` or `phase4_stages.py` implementation remains,
- tests pass.

---

## Phase 9 — Centralize model I/O

### Goal

Remove duplicated COBRA load/save helpers.

### Tasks

Create:

```text
io/models.py
```

Migrate callers incrementally.

Search for:

```text
_load_cobra_model
load_json_model
read_sbml_model
save_json_model
write_sbml_model
```

and replace duplicated boundary logic where appropriate.

### Compatibility

Do not remove public domain-specific `load_model` functions if they are documented APIs.

They should delegate to `io.models`.

### Exit criteria

- workflow/runtime packages contain no private duplicate COBRA load/save dispatch,
- shared JSON/SBML behavior is in one module,
- COBRA imports remain lazy where possible,
- tests pass.

---

## Phase 10 — Remove obsolete implementation modules

After all callers and docs have migrated, delete old implementation modules or reduce them to compatibility facades.

Candidates:

```text
workflow/registered_runner.py
workflow/foundation_stages.py
workflow/beta1_stages.py
workflow/beta2_stages.py
workflow/gapfill_stages.py
workflow/scientific_stages.py
workflow/phase4_stages.py
```

Keep compatibility facades where an import is still considered public.

Do not remove compatibility merely for structural cleanliness.

---

## Phase 11 — Documentation and generated API references

Update:

- workflow architecture docs,
- generated API inventory,
- workflow API docs,
- CLI documentation,
- module import examples,
- architecture diagrams if present.

Document the separation:

```text
domain = what the scientific operation does
workflow = when it runs and which artifacts it reads/writes
runtime = how resumable execution is performed
```

Document `reference` as composition rather than a scientific domain.

---

## 9. Dependency Enforcement

Add automated architecture checks.

At minimum:

### Runtime isolation

Fail if any file under:

```text
src/thg_protocol/runtime/
```

imports:

```text
thg_protocol.workflow
thg_protocol.curation
thg_protocol.gapfill
thg_protocol.pathway
thg_protocol.cell_specific
```

or any workflow-specific stage module.

A small AST-based unit test is sufficient; no new architecture framework is needed.

### Workflow discovery isolation

Fail if:

```text
runtime.engine
```

imports or calls the workflow registry.

### Domain/runtime cleanup

Track remaining domain imports of:

```text
thg_protocol.workflow.hashing
thg_protocol.workflow.parallel
```

and require migration to runtime paths.

---

## 10. Test Strategy

Run the most relevant tests after each phase before the full suite.

### Contract tests

- imports,
- CLI entry point,
- registry contents,
- `workflow.__init__` exports.

### Runtime unit tests

- dependency invalidation,
- completed artifact reuse,
- corrupted artifact rerun,
- force-step behavior,
- interrupted state recovery,
- failed-attempt directory promotion,
- attempt numbering,
- atomic manifest writes,
- lock behavior.

### Workflow integration tests

- β1 registered workflow,
- β2 registered workflow,
- gapfill registered workflow,
- phase/foundation workflow tests,
- reference workflow,
- phase4 workflows,
- CLI subprocess tests,
- recorded evidence replay.

### Cross-version resume test

Add at least one test that:

1. creates a run using the compatibility-facing workflow API,
2. reads the saved snapshot and manifest,
3. resumes it through the refactored runner,
4. confirms no unnecessary stages rerun.

This guards against changing persisted run semantics during a source-only refactor.

---

## 11. Logging Contract

Preserve current user-visible logging semantics.

The runtime move must not cause engine messages to disappear because the module logger changes from:

```text
thg_protocol.workflow.*
```

to:

```text
thg_protocol.runtime.*
```

Acceptance tests should verify:

- `thg-run -v` shows stage progress,
- `thg-run -vv` shows fingerprints/output detail as before,
- `logs/run.log` receives runtime stage execution messages.

Implementation may use a stable logger name such as:

```python
logging.getLogger("thg_protocol.workflow")
```

from the engine if preserving the existing observable logging contract is preferred.

---

## 12. Current-to-Target Mapping

| Current location | Target |
| --- | --- |
| `workflow/registered_runner.py` | split between `workflow/runner.py` and `runtime/engine.py` |
| `workflow/stages.py` | `runtime/stage.py` plus compatibility facade |
| `workflow/lock.py` | `runtime/locking.py` |
| `workflow/parallel.py` | `runtime/concurrency.py` |
| `workflow/manifest.py` | `runtime/manifest.py`, refactored to remove config dependency |
| `workflow/artifacts.py` | `runtime/artifacts.py` plus compatibility facade |
| `workflow/hashing.py` | `runtime/hashing.py` plus compatibility facade |
| `workflow/beta1_stages.py` | `workflow/beta1/` |
| `workflow/beta2_stages.py` | `workflow/beta2/` |
| `workflow/gapfill_stages.py` | `workflow/gapfill.py` |
| `workflow/scientific_stages.py` | `workflow/cell_specific.py`, `pathway.py`, `compare.py` |
| `workflow/phase4_stages.py` | `workflow/human_database.py`, `final_thg.py` |
| `workflow/foundation_stages.py` | `workflow/foundation.py` plus workflow-owned adapters |
| current inline reference composition | `workflow/reference.py` |
| repeated COBRA helpers | `io/models.py` |

---

## 13. Non-Goals

Do not introduce:

- `pipelines/`,
- top-level `provenance/`,
- speculative repositories,
- services solely for layering,
- factories without an actual construction problem,
- general-purpose utility packages,
- plugin discovery for built-in workflows.

Do not:

- rewrite curation algorithms,
- rename workflow IDs,
- rename stage IDs,
- change artifact roles,
- change run-directory semantics,
- change configuration semantics,
- change `thg-run`,
- change persisted manifest format unless independently justified.

---

## 14. Definition of Done

The refactor is complete when all of the following are true.

### Structure

- β1 wiring is under `workflow/beta1/`.
- β2 wiring is under `workflow/beta2/`.
- `reference` composition is owned by `workflow/reference.py`.
- scientific β1 behavior remains under `curation/beta1.py`.
- scientific β2 behavior remains under `curation/beta2.py`.
- generic execution machinery is under `runtime/`.
- common model I/O is under `io/models.py`.

### Dependency boundaries

- runtime imports no workflow package.
- runtime imports no scientific domain package.
- runtime does not know built-in workflow IDs.
- runtime does not discover built-in workflow modules.
- workflow resolves a concrete stage sequence before execution.

### Compatibility

The following continue to work:

```python
from thg_protocol.workflow.runner import start, resume, get_status
```

and:

```bash
thg-run ...
```

Existing workflow IDs remain unchanged, including `reference`.

Existing persisted runs remain resumable.

### Behavior

- stage IDs are unchanged,
- artifact roles are unchanged,
- manifest semantics are unchanged,
- force-step behavior is unchanged,
- invalidation behavior is unchanged,
- config snapshot semantics are unchanged,
- logging behavior is unchanged.

### Quality gates

After every migration phase:

```text
unit tests pass
relevant integration tests pass
full test suite passes before merge
documentation build passes
lint/format checks pass
```

---

## 15. Recommended PR Breakdown

Keep the migration reviewable by splitting it into small structural PRs.

### PR 1 — Runtime primitives

- add `runtime/`,
- move hashing, concurrency, locking, artifacts,
- add compatibility facades,
- update generic callers.

### PR 2 — Stage and manifest boundaries

- add dependency-clean `runtime.stage`,
- add dependency-clean `runtime.manifest`,
- preserve old imports.

### PR 3 — Runner/engine split

- create `runtime.engine`,
- move execution loop,
- make `workflow.runner` resolve workflows,
- preserve logging and CLI behavior.

### PR 4 — Registry/foundation/reference ownership

- move fixture registration out of foundation,
- add explicit built-in bootstrap,
- add `workflow/reference.py`.

### PR 5 — β1 package split

- create `workflow/beta1/`,
- preserve `beta1_stages.py` compatibility facade.

### PR 6 — β2 package split

- create `workflow/beta2/`,
- preserve `beta2_stages.py` compatibility facade.

### PR 7 — Remaining workflow modules

- gapfill,
- validation,
- cell-specific,
- pathway,
- compare,
- human database,
- final THG.

### PR 8 — Model I/O consolidation

- add `io/models.py`,
- migrate duplicated COBRA load/save paths.

### PR 9 — Docs and compatibility cleanup

- update API docs,
- update generated inventories,
- remove obsolete implementation bodies,
- retain only required public compatibility shims.

This PR sequence deliberately keeps execution behavior and scientific behavior unchanged while changing one ownership boundary at a time.
