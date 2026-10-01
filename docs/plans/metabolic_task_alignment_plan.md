# Metabolic task alignment plan

## Goal

Make metabolic task execution in
`/home/reinism/THG_The-Human-GEM-protocol-standalone` (THG) follow RAVEN task
semantics: tasks are defined on metabolites, which the task opens through
temporary source and sink reactions. Support two input formats that load into
one task model and one evaluator:

- **JSON task suites** (native): metabolites and reactions are referenced by
  model ID, so a task means the same thing on every run.
- **RAVEN task tables** (legacy, `.txt`/`.xlsx`): read as-is, with metabolites
  matched by name and compartment, as RAVEN does.

Then align `/home/reinism/pipeline` (`loopless_flux_sampler`) with the same
contract. Paths below are relative to the repository named in each section.
Keep model-specific task collections and ID mappings in their respective
repositories.

## Progress (updated 2026-10-01)

| Section | State |
| --- | --- |
| 1. Contract in THG | Done (metabolite-based; both-sides rule revised, see section 1) |
| 2. Evaluator and tests in THG | Done |
| 3. RAVEN importer in THG | Done (`.txt`/`.tsv`/`.csv`; no `.xlsx`, openpyxl is not a THG dependency) |
| 4. Convert task inputs | Partly: THG tables verified on Human-GEM; mapping files and pipeline tables open |
| 5. Align pipeline | Code and tests ported; cross-repo comparison on real models open |

### State of the code

Not committed, on THG `refactoring-cleanup` and pipeline `shrink_loops`:

- THG: `src/thg_protocol/tasks.py` (contract and evaluator),
  `src/thg_protocol/raven_tasks.py` (importer, direct/convert, mapping files),
  `tests/unit/test_metabolic_tasks.py`, `tests/unit/test_raven_tasks.py`, and
  docs in `docs/workflows/validation.md` and `docs/api/`. Workflow
  `task_suite` settings (`final_thg`, `cell_specific`, `gapfill`) accept a
  RAVEN table, with an optional `task_mapping` setting.
- Pipeline: `src/loopless_flux_sampler/utils/task.py` and `raven_tasks.py`
  are copies of the THG modules; `utils/evaluation.py` is removed;
  `tests/test_tasks/` holds the same tests; `examples/research/test_tasks.py`
  uses the new API.

### Section 4 findings

- On Human-GEM 2022-06-21 (GLPK, closed medium, direct runs): Essential
  57/57 passed, VerifyModel 21/21 passed (all expected failures), Full
  257/257 passed. This confirms the closed medium on a Human-GEM model.
  CellfieConsensus: 169 passed, 17 failed, and 9 invalid. The invalid tasks
  come from 16 references with no Human-GEM match (`NA[c]`, `NA[r]`,
  `FADH2[e]`, `NADPH[e]`, `propanoyl-CoA[e]`), which need a curation
  decision. No comparison with MATLAB RAVEN runs has been made yet.
- The Essential suite converted to JSON on Human-GEM passes 57/57 on
  THG-beta2 with no mapping file.
- THG-beta2 renamed many metabolites (`glutamine` became `L-glutamine`), so
  name matching leaves 37 of 57 Essential tasks unresolved, but it keeps the
  Human-GEM `MAM…` IDs. Converting each table once against Human-GEM gives
  ID-based JSON suites that need no mapping file on THG models.
- Pipeline tables: `metabolicTasks_EC.csv` (ID repeated on every row of a
  task, 190 contiguous tasks) is authoritative. `metabolicTasks_EC1.csv` is a
  lossy conversion of it: task 68 is merged into 67, the rows of 182/183 are
  misgrouped, and IDs 17 and 182 appear twice. Neither EC table nor
  `generic_metab_tasks.tsv` has RAVEN's leading comment column, so RAVEN
  would skip every row. All three use BiGG-style IDs (`gln_L[c]`) as names,
  which need a mapping file per target model.

### Reference: RAVEN semantics

Source: `core/parseTaskList.m` and `core/checkTasks.m` from RAVEN commit
`800362e71b9d04ae2e2a16960b9d19aff346d37e`, the commit cited by the
pipeline's `task.py`.

- Rows whose first cell is non-empty (normally `#`) are skipped. The first
  remaining row is the header. A row with an `ID` starts a task; following rows
  with an empty `ID` add constraints to it.
- `IN`/`OUT`: `;`-separated `name[comp]` metabolites sharing the row's bounds.
  Defaults are `IN LB 0`, `IN UB 1000`, `OUT LB 0`, `OUT UB 1000`.
- IN/OUT relax the steady-state balance of the listed metabolite
  (`model.b`): an input may be net consumed within `[IN LB, IN UB]`, an output
  net produced within `[OUT LB, OUT UB]`. All other metabolites stay balanced.
  Existing exchange reactions are not used.
- `ALLMETS` (every metabolite) and `ALLMETSIN[comp]` (one compartment) use only
  the upper bound: they allow flux, never require it. Specific metabolite
  constraints are applied after them and take precedence.
- `EQU`: equation added as a temporary reaction. Defaults: `EQU LB -1000` for
  `<=>`, `0` otherwise; `EQU UB 1000`. RAVEN allows the equation to create new
  metabolites.
- `CHANGED RXN`: `;`-separated reaction IDs with `CHANGED LB`/`CHANGED UB`.
- A metabolite that is both input and output: its lower balance bound becomes
  `OUT LB` if positive, otherwise `-IN UB`; its upper bound becomes `OUT UB`.
  Nonzero `IN LB` and `OUT LB` on the same metabolite is an error.
- Metabolites are matched by `name[comp]` against model names and compartment
  IDs, case-insensitively. Unmatched names fail the task.
- `SHOULD FAIL` is true for any non-empty cell (so a literal `0` counts as
  true). `PRINT FLUX` only prints fluxes.
- Evaluation is feasibility only: the task succeeds when the LP has a solution.

## 1. Revise the contract in THG

The task suite JSON keeps `schema_version: 2`, since the reaction-based
version 2 was never committed or released.

Task fields:

- `id`, `version`, optional `description`, `expected` (default `true`),
  `group`, `identity`, `solver`, `medium`, `metadata`: as before.
- `inputs`: metabolite ID → `[lower, upper]`, the allowed net consumption.
- `outputs`: metabolite ID → `[lower, upper]`, the allowed net production.
- `temporary_reactions`: as before (explicit bounds, existing metabolite IDs).
- `bounds`: reaction ID → `[lower, upper]` for model or temporary reactions
  (RAVEN `CHANGED RXN`).
- `objective`: optional, JSON only (see below).
- `uptake` and `secretion` are removed. Opening a model exchange reaction is
  still possible through `bounds`.

Semantics:

- Inputs and outputs are evaluated as temporary reactions: a source
  `-> m` named `TASK_IN_<m>` with the input bounds, and a sink `m ->` named
  `TASK_OUT_<m>` with the output bounds. A name that clashes with a model
  reaction makes the task invalid.
- A metabolite listed in both may be consumed or produced. A nonzero lower
  bound on one side is a requirement and closes the other side's reaction,
  so net production is `[OUT LB, OUT UB]` when `OUT LB > 0`,
  `[-IN UB, -IN LB]` when `IN LB > 0`, and `[-IN UB, OUT UB]` otherwise.
  Nonzero lower bounds on both sides make the task invalid, as in RAVEN.
  (Revised during implementation: the earlier formula
  `[OUT LB - IN UB, OUT UB - IN LB]` lets a source and sink cycle, which
  makes `OUT LB` vacuous and disagrees with RAVEN's `checkTasks.m`, for
  example on CellfieConsensus task 169, NADP+/NADPH[m].)
- Repeated constraints on one metabolite or reaction are intersected
  (greatest lower bound, least upper bound); an empty intersection is an
  invalid definition, even for an expected-failure task.
- `medium: "closed"` (default) sets every model boundary reaction to `[0, 0]`,
  so only the task's inputs and outputs connect the model to the outside. This
  matches RAVEN, where boundary metabolites stay balanced. Verify this on a
  Human-GEM-derived model in section 4. `medium: "model"` keeps the input
  model's boundary bounds.
- Order: close boundaries, add input/output and temporary reactions, apply
  intersected bounds, set the objective.
- Feasibility tasks (no `objective`) replace the inherited objective with a
  constant zero objective and succeed when the problem is feasible.
- Objective tasks are a JSON-only extension; RAVEN tables never produce them.
  `objective` is `{"reaction", "direction": "max"|"min", "threshold"}` with a
  finite threshold. The objective is set explicitly; the model's own objective
  is never used. The task succeeds when the solve is optimal and the value is
  at least (`max`) or at most (`min`) the threshold, within
  `OBJECTIVE_TOLERANCE = 1e-6`. The report includes the achieved value.
- `expected: false` passes only on a biological failure (infeasible, or
  optimal but short of the threshold). Invalid definitions and solver errors
  never pass.

## 2. Revise the evaluator and tests in THG

Update `src/thg_protocol/tasks.py`, its docs, and
`tests/unit/test_metabolic_tasks.py` to the section 1 contract. Keep the
existing GLPK cases (closed medium, zero-objective feasibility with an
unbounded input objective, objective thresholds with an opposing input
direction, expected failures, solver errors, contradictory bounds, invalid IDs,
metadata round trips, model restoration) and add:

- An input and an output on internal metabolites with no exchange reaction.
- A metabolite that is both input and output, including the invalid case with
  both lower bounds nonzero.
- Repeated input constraints that intersect, with nonempty and empty results.
- A clash between a `TASK_IN_`/`TASK_OUT_` name and a model reaction.

## 3. Add the RAVEN importer in THG

Add a RAVEN table importer (new module next to `tasks.py`) that produces a
`TaskSuite`. Both ways of using it end in the same `TaskSuite`, so they give
identical results:

- Direct: run a RAVEN table against a model without a conversion step.
  Workflows that accept a task suite path accept a RAVEN table as well, and
  import it against the model being evaluated.
- Convert: write the resolved suite with `save_task_suite` for review and
  reuse.

Parsing follows `parseTaskList.m`: comment rows, the header row, continuation
rows, `;`-separated lists, the RAVEN column names (extra columns are kept as
metadata), and RAVEN's default bounds, written explicitly into the JSON. `.txt`
input is required; `.xlsx` only if openpyxl is already a dependency.

Name resolution:

- Match `name[comp]` against model metabolite names and compartment IDs,
  case-insensitively, as RAVEN does.
- An optional mapping file supplies metabolite overrides (for renamed or
  ambiguous names), compartment label mappings, and reaction ID mappings for
  `CHANGED RXN`.
- `ALLMETSIN[comp]` and `ALLMETS` are expanded to explicit inputs or outputs
  `[0, UB]` for every matching model metabolite. Explicit constraints on the
  same metabolite in that task take precedence, as in RAVEN.
- EQU strings are parsed into temporary reactions `TEMPORARY_<n>` with numeric
  coefficients and `<=>`/`=>` direction. A metabolite that does not exist in
  the model makes the task invalid; this differs from RAVEN, which would add it.
- Unresolved or ambiguous names make that task invalid. The importer reports
  each problem with file, row, column, the original text, and any candidate
  matches. Nothing is guessed or dropped. When running directly, these tasks
  appear in the report as `invalid`. Conversion refuses to write the suite
  while problems remain, unless an explicit option writes only the resolved
  tasks and lists the omitted ones.

Departures from RAVEN, listed in the importer docs and reported per task when
they apply:

- `SHOULD FAIL` is true for `1`/`true`, false for empty, `0`, or `false`
  (case-insensitive); other values are rejected. RAVEN treats any non-empty
  cell, including `0`, as true.
- Repeated constraints on one metabolite are intersected instead of being an
  error.
- An `IN LB` on a metabolite that is also an output is kept as a requirement;
  RAVEN drops it.
- EQU cannot introduce new metabolites.

Every imported task stores its original rows in `metadata.source_rows`
(`file`, `row`, ordered `[column, value]` pairs, missing cells as `null`),
including descriptions, comments, references, and `PRINT FLUX`.

Tests: the Essential fixture
(`tests/fixtures/memote/data/metabolicTasks_Essential.txt`) on a small
synthetic model, each departure above, mapping overrides, ambiguous and
unresolved names, `ALLMETSIN`, EQU parsing, and identical reports for direct
runs and saved-then-loaded JSON.

## 4. Convert the task inputs

- Tables to convert: the THG fixtures (`metabolicTasks_Essential.txt`,
  `metabolicTasks_Full.txt`, `metabolicTasks_VerifyModel.txt`,
  `metabolicTasks_CellfieConsensus.txt` in `tests/fixtures/memote/data/`) and
  the pipeline's `data/metabolicTasks_Full_thg.txt`,
  `data/metabolicTasks_EC.csv`, `data/metabolicTasks_EC1.csv`, and
  `data/generic_metab_tasks.tsv`.
- Check each table's columns and conventions against RAVEN before importing.
  The EC tables repeat the ID on every row of a task (EC) or use RAVEN-style
  continuation rows (EC1); `generic_metab_tasks.tsv` has extra and repeated
  columns. Reconcile these, and decide which of EC/EC1 is authoritative,
  rather than assuming every row or every distinct ID is a complete task.
- Write mapping files for the target models and fix every reported unresolved
  or ambiguous name before replacing any workflow input.
- Keep the original tables as migration references. Validate representative
  converted tasks by comparing direct and converted runs, and where possible
  against published RAVEN results for the same model.

## 5. Align the pipeline repository

In `/home/reinism/pipeline`, port the THG evaluator and RAVEN importer and the
same behavioral tests. Replace the name-based exchange lookup in
`src/loopless_flux_sampler/utils/evaluation.py` (which maps IN/OUT to existing
exchange reactions and uses ±1e-4 defaults that are not RAVEN's) and the
TSV-centric `MetabolicTask` in `src/loopless_flux_sampler/utils/task.py`.
Update the research runner `examples/research/test_tasks.py`; keep existing
entry points only where useful for compatibility.

Preserve reaction ordering. Parallel execution must distribute complete tasks;
use serial execution until that is verified. Avoid new dependencies or a
separate shared package at this stage.

## Completion criteria

- THG and the pipeline accept the same JSON contract and the same RAVEN
  tables, and give matching outcomes on identical small models and tasks,
  including metabolites used as both input and output, overlapping bounds, and
  nondefault input objectives.
- A RAVEN table run directly and its converted JSON give identical reports.
- Converted inputs have no silently omitted requirements, and metadata
  survives JSON load/save round trips in both repositories.
- The GLPK task checks pass in both repositories, plus the relevant existing
  checks in each. Full loopless sampling remains a separate, Gurobi-dependent
  workflow.
