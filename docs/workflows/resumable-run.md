# Resumable engineering runs

!!! warning "Scientific scope"
    `thg-run` composes maintained package APIs into restartable engineering
    checkpoints. It does not implement live biological harvesting, complete
    THGbeta2 construction, essential metabolic-task analysis, or exact
    reproduction of the published final artifact.

The command keeps an immutable configuration snapshot, an atomically written
manifest, checksum-verified outputs, and a separate directory for every stage
attempt. It is offline by default and does not require a solver or MEMOTE.

## Commands

```bash
thg-run start path/to/run-config.json
thg-run status results/my-run
thg-run resume results/my-run
thg-run unlock results/my-run --force
```

`status` also accepts `--json`. Use `resume --force-step validation` to rerun
validation and its optional descendants without deleting earlier artifacts.

## Minimal configuration

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

Relative input paths are resolved against the configuration file. The output
directory is resolved against the working directory when `start` is called;
the normalized absolute values are saved in `config.snapshot.json`, so resume
does not require the original configuration file.

## Artifacts

```text
run/
├── config.snapshot.json
├── manifest.json
├── logs/
├── artifacts/<stage>/attempt-0001/
├── failed/<stage>/attempt-NNNN/
└── .tmp/
```

The version 1 stages are `reference` and `database`, followed by `merge`,
`validation`, and optional external `memote`. The independent first two
branches are executed sequentially today, but their dependency relationship is
recorded explicitly.

`reference` in `prebuilt` mode copies and reads a JSON or SBML model. In
`build_model` mode it calls `build_model_batch` with run-owned output, cache,
and error paths. The reference stage writes a checksummed cache manifest;
configured external caches are inventoried but remain caller-owned. `database` accepts normalized JSON records and calls
`reconstruct_model_from_json`; it does not harvest online services.

## Resume and recovery

On resume, a completed stage is reused only when its implementation/configuration
fingerprint and every recorded output checksum still match. A changed reference
input reruns `reference`, `merge`, `validation`, and enabled MEMOTE, while the
independent database stage remains reusable. A changed records bundle reruns
the other branch and those same descendants. A deleted report reruns only its
stage and descendants. Previous successful attempt directories are retained.
The manifest records the latest attempt for each stage; retained directories
preserve files but are not a structured complete attempt history.

If a process stopped while a stage was `running`, resume records it as
`interrupted` and creates a new attempt. Failed and interrupted temporary work
is retained under `failed/` when possible. A lock is removed automatically only
when its owning command exits; `unlock` requires a demonstrably dead local PID
unless `--force` is supplied. Do not use `--force` while another process may be
writing the run. A SIGTERM that prevents cleanup can leave a stale lock; after
confirming the recorded process is gone, use `thg-run unlock`.

Checksum-invalid or structurally invalid manifests are rejected rather than
repaired. The manifest is not an authentication mechanism: a well-formed manual
edit is detected only when its configuration or artifact checks no longer
match. Inspect the log and use `resume`; use `--force-step` when a deliberate
rerun is needed. Caller-owned input files are read-only from the workflow's
perspective.

`start` refuses an existing nonempty output directory unless it already has a
manifest (which must be resumed). This prevents unrelated files from becoming
part of a new run.

## MEMOTE

Set `validation.run_memote` to `true` only when the separately installed
`memote` executable is available. The command runs it as an external
list-form subprocess and stores the HTML report and stage log. MEMOTE remains
an External operation in the protocol status matrix.

## Limitations

This is a checkpointed composition of current APIs, not a scientific acceptance
or convergence engine. Live KEGG/BioCyc/PubChem harvesting, a complete GPR,
location, and isoenzyme THGbeta2 branch, historical similarity-aware merging,
essential metabolic-task analysis, and exact published-artifact regeneration
remain outside version 1. Outputs should be named and interpreted as neutral
artifacts such as `reference-model` and `candidate-thg`.

## API reference

The maintained entry points are [`start`][thg_protocol.workflow.runner.start],
[`resume`][thg_protocol.workflow.runner.resume], and
[`get_status`][thg_protocol.workflow.runner.get_status]. Their implementation
and manifest/checksum contracts are rendered in the [workflow API reference](../api/workflows.md).
