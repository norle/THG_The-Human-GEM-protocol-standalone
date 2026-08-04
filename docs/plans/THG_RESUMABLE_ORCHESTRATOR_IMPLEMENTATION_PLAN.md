# THG resumable orchestrator: implementation plan

## Purpose

Implement a small, package-native command named `thg-run` that composes the
currently maintained THG package APIs into a restartable run. The implementation
must be suitable for an agent that works best from explicit, sequential tasks.

The first version is an engineering orchestrator, not a claim that the package
now reproduces the complete published THG artifact. It must preserve the
repository's existing `Partial`, `External`, and `Archived` scientific status
labels.

## One-sentence target

After an interrupted process, this command must continue from the first invalid
or incomplete stage while skipping completed stages whose inputs, configuration,
implementation fingerprint, and output checksums still match:

```bash
thg-run start path/to/run-config.json
thg-run status results/my-run
thg-run resume results/my-run
```

## Constraints for the implementing agent

1. Work only in the existing package, tests, and documentation needed for this
   feature. Do not refactor unrelated code.
2. Do not commit, push, open a pull request, or modify GitHub issues unless the
   user separately authorizes that action.
3. Do not use live biological services in tests.
4. Do not add Airflow, Prefect, Snakemake, a database, or a background daemon.
5. Use JSON for the configuration and manifests. Do not add YAML or a YAML
   dependency.
6. Use existing THG APIs rather than copying their internal logic.
7. Never mutate caller-owned input files.
8. Never label an output `THGbeta1`, `THGbeta2`, `final THG`, or an exact
   published reproduction. Use neutral artifact names such as
   `reference-model` and `candidate-thg`.
9. Keep the default test suite deterministic, offline, and solver-independent.
10. A file merely existing is not proof that a stage completed. A completed
    stage requires a manifest record plus verified output checksums.

## Version 1 scope

The version 1 DAG has five stages:

| Stage ID | Existing API or operation | Depends on | Required |
| --- | --- | --- | --- |
| `reference` | `build_model_batch`, or copy a prebuilt model | none | yes |
| `database` | `reconstruct_model_from_json` | none | yes |
| `merge` | `merge_models_from_paths` | reference, database | yes |
| `validation` | network and consistency APIs | merge | yes |
| `memote` | external `memote run` subprocess | merge | optional |

The `reference` and `database` stages are independent. The runner may execute
them sequentially in version 1; the dependency model must nevertheless describe
them as independent so parallel execution can be added later without changing
the manifest format.

### Supported reference modes

- `prebuilt`: copy a caller-supplied, already prepared JSON or SBML model into
  the run artifacts without changing it.
- `build_model`: invoke
  `thg_protocol.model_build.build_model_batch` with explicit output, error, and
  cache paths.

`build_model` mode is maintained model annotation/build behavior. It must not be
described as the complete published reference-to-THGbeta2 branch.

### Supported database mode

Version 1 accepts a normalized JSON record bundle and calls
`thg_protocol.database.reconstruct_model_from_json`. It does not implement live
KEGG, BioCyc, PubChem, or other pathway harvesting.

### Explicit non-goals

- Complete live Human Database harvesting.
- A complete GPR/location/isoenzyme THGbeta2 orchestrator.
- Historical similarity-aware merge behavior.
- Essential metabolic-task analysis, which remains Archived.
- Automatic scientific acceptance or convergence decisions.
- Exact regeneration of the published final artifact.
- Distributed execution or concurrent stage execution.

## Files to add or change

Add this package:

```text
src/thg_protocol/workflow/
├── __init__.py
├── cli.py
├── config.py
├── hashing.py
├── lock.py
├── manifest.py
├── runner.py
└── stages.py
```

Add tests:

```text
tests/unit/
├── test_workflow_config.py
├── test_workflow_hashing.py
├── test_workflow_manifest.py
├── test_workflow_runner.py
└── test_workflow_cli.py
tests/integration/
└── test_resumable_workflow.py
```

Change:

- `pyproject.toml`: register `thg-run = "thg_protocol.workflow.cli:main"`.
- `docs/protocol/index.md`: link to the resumable composition guide while
  retaining `Status: Partial`.
- `docs/protocol/implementation-status.md`: say a resumable composition exists,
  but unsupported scientific stages and exact reproduction remain Partial.
- Add `docs/workflows/resumable-run.md` with commands, configuration, artifact
  layout, resume rules, and limitations.

Do not change the status to fully Supported for the complete published protocol.

## Configuration contract

Use a strict JSON object. Reject unknown keys so typographical errors do not
silently change a scientific run.

Example:

```json
{
  "format_version": 1,
  "run": {
    "name": "example-thg-run",
    "output_dir": "results/example-thg-run"
  },
  "reference": {
    "mode": "prebuilt",
    "input_model": "inputs/reference.json"
  },
  "database": {
    "records": "inputs/normalized-records.json"
  },
  "merge": {
    "remove_isolated_metabolites": false
  },
  "validation": {
    "run_memote": false
  }
}
```

For `reference.mode == "build_model"`, allow optional `cache_dir` only if there
is a clear need to reuse a caller-owned cache. Prefer a run-owned cache by
default. Do not place credentials or tokens in the copied configuration or
manifest.

### Path rules

1. Resolve relative input paths against the directory containing the original
   configuration file during `start`.
2. Store resolved absolute input paths in the run's immutable configuration
   snapshot.
3. Resolve a relative `run.output_dir` against the current working directory at
   `start` time and store its absolute value.
4. On `resume`, read only `<run-dir>/config.snapshot.json`; do not depend on the
   original configuration file still existing.
5. Validate that required inputs exist and are regular files before creating a
   run.
6. Refuse to start if the output directory already contains a manifest. Tell
   the user to use `resume`.

### `config.py`

Use standard-library dataclasses and explicit parsing functions. Do not add a
validation framework.

Suggested public surface:

```python
@dataclass(frozen=True)
class RunConfig: ...

class ConfigError(ValueError): ...

def load_start_config(path: str | Path) -> RunConfig: ...
def load_snapshot(run_dir: str | Path) -> RunConfig: ...
def write_snapshot(config: RunConfig, run_dir: Path) -> Path: ...
def config_to_dict(config: RunConfig) -> dict[str, object]: ...
```

Validate `format_version == 1`, the two reference modes, required strings,
booleans, allowed model suffixes (`.json`, `.xml`, `.sbml`), and unknown keys.

## Run directory and artifact layout

Use this layout:

```text
results/example-thg-run/
├── config.snapshot.json
├── manifest.json
├── run.lock
├── logs/
│   ├── reference-attempt-0001.log
│   └── ...
├── artifacts/
│   ├── reference/attempt-0001/
│   │   ├── reference-model.json
│   │   ├── errors.tsv
│   │   └── cache/
│   ├── database/attempt-0001/human-database.json
│   ├── merge/attempt-0001/
│   │   ├── candidate-thg.json
│   │   └── merge-report.json
│   ├── validation/attempt-0001/
│   │   ├── components.json
│   │   └── consistency.json
│   └── memote/attempt-0001/memote.html
├── failed/
│   └── <stage>/attempt-NNNN/
└── .tmp/
```

Each attempt gets a new directory. Never overwrite a previously successful
attempt. The manifest points to the currently selected successful attempt.

The `run.lock` exists only while a command is actively mutating the run. The
lock's temporary presence in the tree above is illustrative.

## Manifest contract

`manifest.json` is the source of run state. Write it atomically after every
state transition.

Minimum shape:

```json
{
  "format_version": 1,
  "run_id": "example-thg-run",
  "created_at": "ISO-8601 UTC",
  "updated_at": "ISO-8601 UTC",
  "config_sha256": "...",
  "package_version": "0.1.0",
  "overall_status": "running",
  "steps": {
    "reference": {
      "status": "completed",
      "attempt": 1,
      "fingerprint": "...",
      "started_at": "...",
      "finished_at": "...",
      "outputs": [
        {
          "role": "model",
          "path": "artifacts/reference/attempt-0001/reference-model.json",
          "sha256": "...",
          "size": 123
        }
      ],
      "error": null
    }
  }
}
```

Allowed step statuses:

```text
pending, running, completed, failed, interrupted, skipped
```

Allowed overall statuses:

```text
pending, running, completed, failed, interrupted
```

Do not store secrets, environment dumps, full service responses, or exception
tracebacks containing configuration secrets in the manifest. Full diagnostic
tracebacks may go to the stage log after basic secret-safe formatting.

### Atomic manifest writes

Implement this exact pattern in `manifest.py`:

1. Serialize deterministic, indented JSON with a trailing newline.
2. Write to `manifest.json.tmp` in the same directory.
3. Flush and `os.fsync()` the temporary file.
4. Call `os.replace(temp_path, manifest_path)`.

Suggested surface:

```python
class ManifestError(RuntimeError): ...

def new_manifest(config: RunConfig) -> dict[str, object]: ...
def load_manifest(run_dir: str | Path) -> dict[str, object]: ...
def write_manifest_atomic(run_dir: Path, manifest: Mapping[str, object]) -> None: ...
def validate_manifest(manifest: Mapping[str, object]) -> None: ...
```

Reject unknown manifest versions and malformed step entries with a clear error;
do not try to repair them silently.

## Hashing and fingerprints

### `hashing.py`

Implement:

```python
def sha256_file(path: str | Path, chunk_size: int = 1024 * 1024) -> str: ...
def sha256_json(value: object) -> str: ...
def artifact_record(role: str, path: Path, run_dir: Path) -> dict[str, object]: ...
def verify_artifact(record: Mapping[str, object], run_dir: Path) -> bool: ...
```

`sha256_json` must serialize with sorted keys and compact separators. Stream
file hashing; do not load model files into memory solely to hash them.

Each stage fingerprint must hash a canonical object containing:

- the stage ID;
- the stage-specific configuration;
- hashes of caller-owned input files used by that stage;
- output hashes of dependency stages;
- package version; and
- a constant stage implementation version, initially `1` per stage.

Do not use timestamps, output paths, temporary paths, or attempt numbers in a
fingerprint.

If the package cannot determine its installed version, record a stable value
such as `unknown`; do not crash solely because package metadata is unavailable.

## Locking

### `lock.py`

Implement a small cross-platform exclusive lock using
`os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)`. Write PID, hostname, and
start time as JSON. Remove the lock in `finally`.

Suggested surface:

```python
class RunLockedError(RuntimeError): ...

@contextmanager
def acquire_run_lock(run_dir: Path) -> Iterator[None]: ...
```

If a lock already exists, fail safely and display its metadata. Add:

```bash
thg-run unlock RUN_DIR
```

The `unlock` command may delete a lock only when:

- the recorded hostname is the current hostname and the PID is demonstrably no
  longer alive; or
- the user passes `--force`.

Never remove a lock automatically merely because it is old.

## Stage interface

### `stages.py`

Define a small stage protocol and context. Keep orchestration logic out of the
scientific API modules.

Suggested shape:

```python
@dataclass(frozen=True)
class StageContext:
    config: RunConfig
    run_dir: Path
    manifest: Mapping[str, object]

@dataclass(frozen=True)
class StageResult:
    outputs: tuple[tuple[str, Path], ...]
    summary: Mapping[str, object]

class Stage(Protocol):
    id: str
    dependencies: tuple[str, ...]
    implementation_version: int

    def enabled(self, config: RunConfig) -> bool: ...
    def fingerprint_data(self, context: StageContext) -> Mapping[str, object]: ...
    def run(self, context: StageContext, work_dir: Path) -> StageResult: ...
    def validate(self, result: StageResult) -> None: ...
```

Return paths inside `work_dir`. The runner, not the stage, promotes the entire
work directory into its final attempt directory.

### Reference stage

For `prebuilt` mode:

1. Copy the input model to `work_dir/reference-model<original-suffix>` using
   `shutil.copy2`.
2. Load the copied model with COBRA to prove it is readable.

For `build_model` mode:

1. Call `build_model_batch(input_path, output_path, output_errors=...,
   cache_dir=...)`.
2. Put all output, errors, and cache files inside `work_dir`.
3. Serialize the report to `build-report.json` using its public fields. Do not
   serialize arbitrary Python objects with pickle.
4. Load the output model to validate it.

Preserve the input's JSON versus SBML form when practical. Add one private
`_load_cobra_model(path)` helper shared by stages.

### Database stage

1. Call `reconstruct_model_from_json(records_path,
   output_path=work_dir / "human-database.json")`.
2. Validate that the returned model can be loaded from the written JSON.
3. Record model ID, metabolite count, reaction count, and gene count in the
   stage summary.

### Merge stage

1. Resolve the successful reference model and database model from dependency
   output records in the manifest. Do not guess paths.
2. Call `merge_models_from_paths(...,
   work_dir / "candidate-thg.json",
   remove_isolated_metabolites=config.merge.remove_isolated_metabolites)`.
3. Write `merge-report.json` containing the public `MergeReport` fields.
4. Load the candidate model and verify the reaction and metabolite counts are
   nonzero unless a deliberately tiny test fixture documents otherwise. Prefer
   a general readability validation over hard-coded scientific thresholds.

### Validation stage

Load the merge output and invoke maintained APIs:

- `find_network_components`;
- `write_component_report`;
- `unbalanced_reactions`;
- `unbalanced_reactions_by_charge`;
- `orphan_metabolites`;
- `dead_end_metabolites`.

Write `consistency.json` with sorted lists and simple counts. Do not run solver-
backed functions such as blocked reactions or flux variability in version 1.
The stage reports results; it must not silently change the model or fail only
because biological issues were found.

### MEMOTE stage

If `validation.run_memote` is false, mark this stage `skipped`.

If enabled:

1. Resolve the merge model from the manifest.
2. Use `shutil.which("memote")`; fail with an actionable message if missing.
3. Run a list-form subprocess, never `shell=True`:

   ```python
   ["memote", "run", "--filename", str(output_html), str(model_path)]
   ```

4. Redirect stdout and stderr to the attempt log.
5. Require return code zero and a nonempty HTML output.
6. Record the command name and MEMOTE version, but not the whole environment.

Keep MEMOTE documented as External.

## Runner behavior

### `runner.py`

Suggested public surface:

```python
class WorkflowError(RuntimeError): ...
class StageFailedError(WorkflowError): ...

def start(config_path: str | Path) -> Path: ...
def resume(run_dir: str | Path, *, force_step: str | None = None) -> Path: ...
def get_status(run_dir: str | Path) -> Mapping[str, object]: ...
```

Use a hard-coded tuple of version 1 stage objects in topological order. At
module initialization or in a test, verify that every dependency exists and
precedes its consumer.

### Start algorithm

1. Load and validate the external configuration.
2. Create the output directory only after input validation succeeds.
3. Acquire the run lock.
4. Write the normalized immutable configuration snapshot.
5. Create and atomically write a new manifest.
6. Call the same internal execution function used by `resume`.
7. Return the run directory.

### Resume algorithm

1. Require `config.snapshot.json` and `manifest.json`.
2. Acquire the run lock.
3. Load and validate both files and verify `config_sha256`.
4. Convert any manifest step left as `running` by a crashed process to
   `interrupted`, then write the manifest atomically.
5. Visit stages in topological order.
6. Mark disabled optional stages `skipped`.
7. Compute the current fingerprint.
8. If a stage is `completed`, the fingerprint matches, and every recorded
   artifact checksum verifies, skip it.
9. Otherwise invalidate that stage and all descendants in memory. Do not
   delete old successful attempt directories.
10. Create `.tmp/<stage>-attempt-NNNN`.
11. Mark the step `running`, set timestamps and attempt number, and atomically
    write the manifest before calling the stage.
12. Run and validate the stage.
13. Move the whole temporary directory with `os.replace` to
    `artifacts/<stage>/attempt-NNNN`.
14. Create artifact records using their promoted paths and hashes.
15. Mark the step `completed` and atomically write the manifest.
16. On an ordinary exception, move the temporary directory to
    `failed/<stage>/attempt-NNNN` when possible, record a concise error, mark
    the run failed, atomically write the manifest, and re-raise as
    `StageFailedError`.
17. On `KeyboardInterrupt` or a handled SIGTERM, record `interrupted` and exit
    nonzero. A later `resume` reruns that stage.
18. When every required stage is completed and every enabled optional stage is
    completed, mark the run completed.

### Downstream invalidation

If a stage's fingerprint or artifacts are invalid, set that stage and every
transitive descendant to `pending`. Preserve their old attempt histories and
artifacts. The independent sibling branch must not be invalidated.

Examples:

- Changed reference input reruns `reference`, `merge`, `validation`, and
  enabled `memote`, but not `database`.
- Changed normalized records reruns `database`, `merge`, `validation`, and
  enabled `memote`, but not `reference`.
- Deleted `components.json` reruns only `validation`.
- A previous process stopped while `merge` was `running`; resume changes it to
  `interrupted`, then reruns `merge` and its descendants.

### `--force-step`

`thg-run resume RUN_DIR --force-step validation` must mark that step and its
descendants pending even if fingerprints and artifacts are valid. Reject an
unknown step ID. Do not delete prior attempts.

## CLI behavior

### `cli.py`

Use `argparse`. Implement:

```text
thg-run start CONFIG.json
thg-run resume RUN_DIR [--force-step STAGE]
thg-run status RUN_DIR [--json]
thg-run unlock RUN_DIR [--force]
```

Exit codes:

| Code | Meaning |
| --- | --- |
| `0` | Success, including a completed `status` command |
| `2` | Configuration or CLI usage error |
| `3` | Run is locked |
| `4` | Stage failed |
| `130` | Interrupted by user |

Human-readable status should print one line per stage with status and attempt.
`--json` should print the validated manifest without modifying it.

Do not print tracebacks for expected configuration, locking, or stage errors.
Unexpected programmer errors may retain a traceback during development, but
tests should assert stable user-facing error messages for expected failures.

## Test plan

Implement tests in this order. Use `tmp_path`, small COBRA models, the existing
normalized-record fixtures where suitable, and monkeypatching for controlled
failures.

### 1. Configuration tests

- Valid prebuilt configuration resolves paths correctly.
- Valid build-model configuration is accepted.
- Missing input, wrong version, unknown key, invalid mode, invalid suffix, and
  non-boolean options are rejected.
- The snapshot is self-contained and reloads without the original config.
- Secrets or arbitrary extra keys cannot be copied into the snapshot.

### 2. Hashing tests

- File hash matches a known SHA-256 value.
- JSON hashing is independent of mapping key order.
- Artifact verification detects content changes, deletion, wrong size, and
  paths escaping the run directory.
- Symlinks that resolve outside the run directory are rejected for produced
  artifacts.

### 3. Manifest tests

- New manifest has all stage entries and valid initial states.
- Atomic writer leaves valid JSON after repeated writes.
- Bad versions and malformed states are rejected.
- A simulated failure before `os.replace` does not corrupt the previous
  manifest.

### 4. Runner unit tests with fake stages

- Fresh execution completes stages in topological order.
- Resume skips valid completed stages.
- A fake stage fails once; resume reruns it but not valid ancestors.
- A `running` step from a simulated crash becomes interrupted and is rerun.
- A changed source input invalidates only its branch and descendants.
- A changed or missing output invalidates its stage and descendants.
- `--force-step` reruns the selected stage and descendants.
- Attempt numbers increase and old successful artifacts remain.
- An optional disabled stage is skipped.
- A concurrent lock prevents mutation.

Prefer injecting the stage tuple into one internal runner function for these
tests. Do not monkeypatch module globals in every test.

### 5. Stage tests

- Prebuilt reference copies and validates JSON and SBML without changing input.
- Build-model reference passes explicit run-owned output/cache/error paths and
  accepts static service clients in a direct stage-level test if injection is
  exposed.
- Database reconstruction produces readable JSON.
- Merge produces a readable candidate and JSON report.
- Validation writes deterministic JSON and does not mutate the candidate.
- Disabled MEMOTE is skipped.
- Enabled MEMOTE reports a missing executable cleanly.
- A fake MEMOTE executable verifies list-form arguments and output validation.

### 6. CLI tests

- `--help` works without optional dependencies.
- Start, status, resume, force-step, and unlock parse correctly.
- Expected failures return the documented exit codes.
- `status --json` emits parseable JSON and performs no write.

### 7. End-to-end offline integration test

1. Create a tiny prebuilt reference model and normalized database record bundle.
2. Run `start` through merge and validation with MEMOTE disabled.
3. Record all attempt numbers.
4. Run `resume` and assert no attempt number changes.
5. Corrupt or delete `validation/consistency.json`.
6. Run `resume` and assert only validation receives a new attempt.
7. Simulate a stopped merge by editing the test manifest through a test helper
   to status `running`, then resume and assert merge and validation rerun.

The integration test must not access the network or require a solver.

## Security and integrity checks

- Reject artifact paths outside the run directory after `Path.resolve()`.
- Do not follow produced symlinks outside the run directory.
- Use list-form subprocess arguments and never `shell=True`.
- Do not serialize environment variables.
- Do not accept executable commands from the JSON configuration in version 1.
- Do not use pickle for configuration, state, reports, or provenance.
- Keep caller-owned inputs read-only from the workflow's perspective.
- Ensure stage attempt and artifact paths are derived from known stage IDs, not
  arbitrary configuration strings.

## Documentation requirements

`docs/workflows/resumable-run.md` must contain:

1. The exact four CLI forms.
2. A complete minimal JSON configuration.
3. The run directory layout.
4. Resume and invalidation behavior with examples.
5. How to use a prebuilt reference model versus `build_model` mode.
6. How to enable separately installed MEMOTE.
7. A prominent limitations block explaining that the command composes current
   maintained APIs but does not implement missing live harvesting, complete
   THGbeta2 construction, essential tasks, or exact published reproduction.
8. Recovery guidance for failed, interrupted, locked, and checksum-invalid
   runs.

Update the implementation-status matrix carefully:

- Iterative/resumable composition may move from "no maintained convergence
  orchestrator" to wording such as "a checkpointed engineering composition is
  available; scientific convergence decisions remain manual."
- Complete published protocol and final-artifact reproduction remain Partial.
- MEMOTE remains External.
- Essential metabolic-task analysis remains Archived.

## Validation commands

Run from the repository root:

```bash
python -m pytest tests/unit/test_workflow_config.py
python -m pytest tests/unit/test_workflow_hashing.py
python -m pytest tests/unit/test_workflow_manifest.py
python -m pytest tests/unit/test_workflow_runner.py
python -m pytest tests/unit/test_workflow_cli.py
python -m pytest tests/integration/test_resumable_workflow.py
python -m pytest
ruff check src tests
python -m build
```

Then install the built wheel in a clean environment and verify:

```bash
thg-run --help
thg-run start --help
thg-run resume --help
thg-run status --help
```

Do not claim completion if the feature-specific tests pass but the existing
offline suite regresses.

## Recommended implementation sequence

Use one focused change set per numbered item and run the named tests before
continuing:

1. Add `workflow/config.py` and its tests.
2. Add `workflow/hashing.py` and its tests.
3. Add `workflow/manifest.py` and its tests.
4. Add `workflow/lock.py` and locking tests.
5. Add the stage protocol plus reference and database stages.
6. Add merge and validation stages.
7. Add the optional MEMOTE stage.
8. Add `workflow/runner.py` with fake-stage tests.
9. Add `workflow/cli.py` and the `pyproject.toml` entry point.
10. Add the offline end-to-end integration test.
11. Add and update documentation without changing scientific status beyond
    what the implementation demonstrates.
12. Run the full validation commands and inspect the final diff for unrelated
    changes.

## Definition of done

The work is complete only when all of the following are true:

- `thg-run start`, `status`, `resume`, and `unlock` exist and have help text.
- An interrupted or formerly `running` stage can be resumed safely.
- Valid completed stages are skipped based on both fingerprints and artifact
  checksums.
- Changed inputs invalidate only the affected branch and its descendants.
- Previously successful attempt artifacts are not overwritten or deleted.
- Manifest updates are atomic.
- Concurrent mutation is blocked by a run lock.
- MEMOTE is optional and external.
- No test requires network, credentials, a solver, or MEMOTE.
- The full existing offline test suite and Ruff pass.
- Documentation explains both the feature and its scientific limitations.
- The implementation does not claim exact reproduction of the published THG
  artifact.

## Short handoff prompt for a coding agent

Use this prompt together with this file:

> Implement the plan in `THG_RESUMABLE_ORCHESTRATOR_IMPLEMENTATION_PLAN.md`
> sequentially. Begin with configuration and hashing only. After each numbered
> implementation step, run its targeted tests and fix failures before moving
> on. Reuse existing `thg_protocol` APIs, keep all tests offline, preserve input
> files and previous attempt artifacts, and do not change the published
> protocol status to fully Supported. Do not commit, push, or open a PR.
