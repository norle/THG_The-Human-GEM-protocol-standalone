# Validation

Validation has three related interfaces.

Validation inside β1, β2, Human Database reconstruction, gapfill, or
cell-specific reduction is stage-level validation. It checks that stage and
records evidence but does not confer THG reference-model status. The final
validation gate evaluates the post-gapfill **THG candidate** under its
configured release profile. A passing candidate is **validated**; no registered
workflow currently promotes and exports it as the released **THG reference
model**.

## Registered validation workflow

For a quick one-off check, pass a model directly. This uses the
`structural-fast` profile and prints a compact result; use `--json` for the
full report or override the profile and solver behavior:

```bash
thg-run validate path/to/model.json
thg-run validate path/to/model.json --profile final-standard --run-solver --json
```

The direct form does not create a resumable run or run MEMOTE. Use the
configuration form below when those artifacts are required.

Save the configuration as `configs/validation.json` and run
`thg-run validate configs/validation.json` with a model and a reusable profile.
It can write structural, chemical, topology, and optional solver-backed checks, plus
an optional MEMOTE stage. A failed external tool is recorded distinctly from
model-test failures.

```json
{"workflow": "validate",
 "run": {"name": "validation", "output_dir": "../runs/validation"},
 "validation": {"input_model": "../inputs/models/model.json", "profile": "final-standard",
                 "run_memote": false}}
```

The registered workflow writes one canonical `validation-report.json`, a
self-contained `validation-report.html` viewer, and `validation-summary.md`.
The HTML is rendered from the JSON and does not rerun or reinterpret checks.

Stoichiometric consistency is diagnostic in every profile, including
`release-full`: failure produces a warning rather than blocking release.
The check seeks positive conserved metabolite weights over internal reactions,
excluding boundary reactions. Pool metabolites and lumped reactions may need
manual interpretation; warnings remain visible for review.

## Metabolic task API

`thg_protocol.tasks` is a versioned, non-mutating API. Task suites may copy a
model, add temporary reactions, execute configured solver checks, and classify
results. `thg-run validate` does not execute an arbitrary task suite unless its
configuration explicitly enables the supported task stage. `final-thg` task
results are likewise reported separately where configured.

Task suites are JSON objects (`schema_version` 2) with an `id`, `version`, and
a list of `tasks`. Unknown fields, duplicate task IDs, duplicate JSON keys,
nonfinite or reversed bounds, and malformed values are rejected at load time
instead of being dropped. Tasks follow RAVEN semantics: they are defined on
metabolites, which the task opens through temporary source and sink reactions.
Each task follows this contract:

- `inputs` and `outputs` map model metabolite IDs to `[lower, upper]` bounds
  on the allowed net consumption and net production. Each is evaluated as a
  temporary reaction: a source `-> m` named `TASK_IN_<m>` and a sink `m ->`
  named `TASK_OUT_<m>`. Existing exchange reactions are not used, and a
  generated name that clashes with a model reaction makes the task invalid.
- A metabolite listed as both input and output may be consumed or produced.
  A nonzero lower bound on one side is a requirement and closes the other
  side, so the requirement cannot be met by cycling through the source and
  sink. Nonzero lower bounds on both sides are an invalid definition.
- `temporary_reactions` add reactions over existing model metabolite IDs
  (`id`, `stoichiometry`, `lower_bound`, `upper_bound`, optional `name` and
  `gene_reaction_rule`). Bounds have no default; importers write their source
  format's defaults explicitly.
- `bounds` maps model or temporary reaction IDs (RAVEN `CHANGED RXN`) to
  signed `[lower, upper]` flux bounds. Repeated constraints on one reaction,
  including a temporary reaction's own bounds, are intersected; an empty
  intersection is an invalid definition, even for an expected-failure task.
- `medium` is `"closed"` by default: every model boundary reaction is set to
  `[0, 0]`, so only the task's inputs and outputs connect the model to the
  outside, as in RAVEN, where boundary metabolites stay balanced. Use
  `"model"` to retain the input model's boundary bounds. A model exchange can
  still be opened through `bounds`.
- Evaluation order: close boundaries, add source/sink and temporary
  reactions, apply the intersected bounds, set the objective.
- A task without `objective` is a feasibility task: the inherited objective is
  replaced by a constant zero objective and the task succeeds when its
  constraints are feasible. An objective task (a JSON-only extension) declares
  `{"reaction", "direction": "max" | "min", "threshold"}` and succeeds when
  the solve is optimal and the value is at least (`max`) or at most (`min`)
  the threshold within an absolute tolerance of `1e-6`.
- `expected: false` marks a task that should fail. Only a biological failure
  (infeasible, or optimal but short of the threshold) satisfies it.
- `description` is optional text. `metadata` is an optional object preserved
  through load/save. Imported rows use ordered `source_rows` entries with
  `file`, `row`, and `columns` as `[name, value]` pairs, with missing cells as
  `null`.

Task reports keep `status` (`passed`, `failed`, `invalid`, `error`),
`expected_outcome`, `actual_outcome`, `solver_status`, `objective_value`, and
`diagnostics` separate. Unknown reaction or metabolite IDs are `invalid` and
unexpected solver statuses or exceptions are `error`; neither ever passes.
Tasks run serially, in order, on a copy of the input model, and each task's
changes are reverted before the next.

### RAVEN task tables

`thg_protocol.raven_tasks` reads RAVEN task tables (tab-delimited `.txt`,
`.tsv`, or `.csv`; export Excel workbooks' `TASKS` sheet first) as RAVEN's
`parseTaskList.m` does, and matches `name[comp]` metabolites
case-insensitively against model metabolite names and compartment IDs, as
`checkTasks.m` does. RAVEN's defaults (`IN`/`OUT` `[0, 1000]`, `EQU LB`
`-1000` for `<=>` and `0` for `=>`, `EQU UB 1000`) are written explicitly;
`CHANGED LB`/`CHANGED UB` have no default. `ALLMETS` and `ALLMETSIN[comp]`
expand to `[0, UB]` for every matching model metabolite without an explicit
constraint on the same side. `EQU` rows become `TEMPORARY_<n>` reactions.

A table can be used two ways, with identical results:

- Directly: every workflow `task_suite` setting accepts a RAVEN table, which
  is imported against the model being evaluated. An optional `task_mapping`
  setting names a JSON mapping file.
- Converted: `convert_raven_tasks` writes the resolved suite as JSON for
  review and reuse.

The mapping file has optional `metabolites` (`"name[comp]"` text → model
metabolite ID), `compartments` (table label → model compartment ID), and
`reactions` (table reaction ID → model reaction ID, for `CHANGED RXN`)
objects. Unresolved or ambiguous names, malformed values, and contradictory
constraints make the task invalid; each problem names the file, row, column,
original text, and candidate matches. Run directly, such tasks are reported as
`invalid`. Conversion refuses to write while problems remain, unless
`resolved_only=True` writes the resolved tasks and lists the omitted ones in
the suite's `metadata.omitted_tasks`.

Departures from RAVEN, recorded per task in `metadata.import_notes`:

- `SHOULD FAIL` is true for `1`/`true` and false for empty, `0`, or `false`
  (case-insensitive); other values are rejected. RAVEN treats any non-empty
  cell, including `0`, as true.
- Repeated constraints on one metabolite or reaction are intersected; RAVEN
  raises an error for metabolites and lets the last reaction bound win.
- An `IN LB` on a metabolite that is also an output is kept as a requirement;
  RAVEN drops it.
- `EQU` cannot introduce metabolites that are not in the model.
- A task ID used by several tasks is made unique as `<ID>-row<row>`.

## MEMOTE integration

`thg_protocol.memote.run_memote` is a maintained subprocess wrapper. Install
the optional `memote` extra, record the command and version, and retain the
JSON result, HTML report, and run metadata. A MEMOTE score does not replace
package structural checks, determine the THG release gate, or prove
publication-artifact reproduction.

See the [I/O and configuration reference](../reference/io-and-config.md) and
[generated API reference](../api/workflows.md).

Canonical APIs: [`validate_model`][thg_protocol.validation.validate_model],
[`run_task_suite`][thg_protocol.tasks.run_task_suite],
[`import_raven_tasks`][thg_protocol.raven_tasks.import_raven_tasks], and
[`run_memote`][thg_protocol.memote.run_memote].
