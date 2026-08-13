# Reproducible and resumable runs

Each run has a directory containing its manifest, configuration snapshot,
stage attempts, artifacts, checksums, and provenance. Stage fingerprints allow
valid work to be reused; `thg-run resume RUN_DIR --force-step STAGE` invalidates
that stage and descendants while preserving previous attempts.

Starting a config whose output directory already contains the matching
registered run resumes it automatically. Only `n_jobs` may differ; other
configuration changes require a new output directory.

```bash
thg-run status runs/beta1 --json
thg-run resume runs/beta1 --verbose
```

Verbose mode reports each stage as it starts, completes, is skipped, or reuses
a checksum-verified artifact. Use `-vv` when diagnosing a run to include stage
fingerprints, summaries, and output paths.

Verbose workflow messages are also preserved in `RUN_DIR/logs/run.log`.

Record artifact roles, input references, configuration snapshots, stage
fingerprints, package versions, and service/cache provenance. Deterministic
outputs are guaranteed only where the workflow and injected evidence make that
possible. Interrupted stages can be resumed after their lock is cleared using
the documented `unlock` command and an explicit stale-lock decision.

The exact contracts are generated under the [workflow API reference](../api/workflows.md).

Canonical APIs: [`start`][thg_protocol.workflow.runner.start],
[`resume`][thg_protocol.workflow.runner.resume], and
[`get_status`][thg_protocol.workflow.runner.get_status].
