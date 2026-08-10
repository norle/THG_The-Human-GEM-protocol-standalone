# Validation

Validation has three related interfaces.

## Registered validation workflow

Save the configuration as `configs/validation.json` and run
`thg-run validate configs/validation.json` with a model and a reusable profile.
It can write structural, chemical, topology, and optional solver-backed checks, plus
an optional MEMOTE stage. A failed external tool is recorded distinctly from
model-test failures.

```json
{"format_version": 2, "workflow": "validate",
 "run": {"name": "validation", "output_dir": "../runs/validation"},
 "validation": {"input_model": "../inputs/models/model.json", "profile": "final-standard",
                 "run_memote": false}}
```

## Metabolic task API

`thg_protocol.tasks` is a versioned, non-mutating API. Task suites may copy a
model, add temporary reactions, execute configured solver checks, and classify
results. `thg-run validate` does not execute an arbitrary task suite unless its
configuration explicitly enables the supported task stage. Final-THG task
results are likewise reported separately where configured.

## MEMOTE integration

`thg_protocol.memote.run_memote` is a maintained subprocess wrapper. Install
the optional `memote` extra, record the command and version, and retain the
JSON result, HTML report, and run metadata. A MEMOTE score does not replace
package structural checks or prove publication-artifact reproduction.

See the [I/O and configuration reference](../reference/io-and-config.md) and
[generated API reference](../api/workflows.md).

Canonical APIs: [`validate_model`][thg_protocol.validation.validate_model],
[`run_task_suite`][thg_protocol.tasks.run_task_suite], and
[`run_memote`][thg_protocol.memote.run_memote].
