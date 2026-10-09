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

### Obligatory loop detection and requested removal

Validation detects obligatory infeasible loops by default. The detector filters
blocked reactions, then repeatedly compacts linear pathways and proportional
parallel reactions on a copy. Cycles that cancel completely are reported with
their original reaction IDs. Boundary and objective reactions are protected.
Findings are diagnostic warnings and never change the validated model. This
method does not detect every conditional loop; a clean result is not proof that
the model is loop-free.

Blocked-reaction filtering uses a solver even with `run_solver: false` or the
`structural-fast` profile. Disable this check with
`validation.run_loop_detection: false`, or in direct model mode:

```bash
thg-run validate path/to/model.json --no-run-loop-detection
```

Disabled detection is recorded as not evaluated. Solver errors are recorded
as infrastructure errors rather than a successful check with no findings.
The detection setting is preserved when applying report decisions and
revalidating the resulting model.

Loop removal is a separate, explicit pipeline operation. Set
`gapfill.remove_infeasible_loops: true` in a `reference` or standalone `gapfill`
configuration, or `final_thg.remove_infeasible_loops: true` in `final-thg`.
The default is false. The pipeline detects loops and removes only the reported
original reactions after gapfilling or merging, before validation and configured
metabolic tasks. It retains the input model, records removals in the change
ledger, and exports the resulting candidate only if the existing gate passes.
Detection errors stop requested removal.

Both sections also accept `run_loop_detection` to control their validation
checks. Requested removal always performs detection, even if subsequent
validation detection is disabled. Removal evidence is in `loop_removal` in the
validation report; the gapfill ledger contains both additions and removals, and
`final-thg` exports a separate `loop-removal-ledger.jsonl`.

`release-full` requires evaluable mass and charge balance for non-excluded internal
reactions and a passing energy-generating-cycle check. Missing or invalid chemistry,
detected energy cycles, disabled solver checks, unavailable MEMOTE, or the absence
of an identifiable energy couple prevent release. Other profiles retain energy
cycle results as diagnostic evidence.

Stoichiometric consistency is diagnostic in every profile, including
`release-full`: failure produces a warning rather than blocking release.
The check runs MEMOTE's consistency functions (Gevorgyan et al. 2008) with the
model's solver. Profiles that run solver checks also name the unconserved
metabolites (ID, name, compartment) with MEMOTE's MILP; `structural-fast` runs
only the consistency LP and reports `unconserved` as `null` when it fails.
Boundary, biomass (`SBO:0000629`), "Artificial reactions" and "Pool
reactions" reactions are excluded, as are reaction IDs listed in
`validation.conservation_exclusions`; the details list each exclusion with its
rule. Without the optional `memote` extra the check is reported as not
evaluated. When it fails, the validation report names the responsible
reactions and lists [suggested fixes](#suggested-fixes).

`validation.reference_model` (optional) names the model the checked one derives
from, for example Human-GEM for a β1 model. Its conservation exclusions carry
over, and formulas and charges are compared against it (below).

Four chemistry checks flag common causes of mass creation and wrong
identities. All are diagnostic in every profile:

- `fractional-coefficients` lists internal reactions with non-integer
  coefficients, such as fitted `1.2 O2 -> 1.5 product`. Reactions the
  conservation check excludes (biomass, artificial and pool reactions, the
  reference model's exclusions, `validation.conservation_exclusions`) are
  skipped, since pseudo-reactions are fractional by design.
- `formula-disagreement` lists metabolites whose formula or charge differs
  from the same metabolite in another compartment (IDs equal after removing
  the compartment suffix, as `MAM00668c`/`MAM00668m` or `C03024_c`) and, with
  a reference model, from the same ID there. Formulas are compared as element
  counts, so `CH1O2` equals `CHO2`. A formula that is wrong in the reference
  as well is not caught here.
- `annotation-conflict` finds mislabelled metabolites. Within the model, it
  lists names shared by metabolites that are different compounds: their
  formulas differ beyond hydrogen or their KEGG IDs are disjoint (ChEBI is
  not compared, as it gives an acid and its conjugate base different IDs).
  With a reference model, it also lists metabolites renamed from the
  reference to the name of another, conflicting compound there. Both catch a
  merge that mapped a compound onto the wrong metabolite: the legacy merge
  behind THG β1 renamed Human-GEM's `MAM00668` (2-naphthol) to
  icosapentaenoic acid, which `MAM01784` already is, and about 30 others.
- `unusual-protons` lists internal reactions with more than 10 H+ (formula
  `H`, charge +1), a common sign of a reaction balanced against a wrong
  formula (`EPA-CoA + H2O -> 2 EPA + CoA + 14 H+`). With a reference model,
  reactions with the same proton coefficients there are not listed, so
  inherited transport chains (63 in Human-GEM) do not drown new cases.

Solver profiles also close every boundary reaction and run two
non-blocking flux tests. Internal reactions are bounded to `[0, 1]` or
`[-1, 1]` by reversibility (MEMOTE's `close_boundaries_sensibly`), so fixed
bounds cannot make them infeasible. Both depend on the optional `memote`
dependency.

- `metabolite-leaks` lists metabolites the network can make or destroy
  with nothing coming in or going out, split by compartment. Unlike
  `stoichiometric-consistency` it respects reaction directions, so it reports
  only leaks that flux can actually reach. Each LP maximises the summed drain
  of the metabolites not yet found, so a leak-free model needs one LP per
  direction.
- `energy-generating-cycles` follows MEMOTE (Fritzemeier et al. 2017): for
  each cytosolic energy couple (ATP, GTP, NADH, NADPH, FADH2, acetyl-CoA, ...)
  it adds a dissipation reaction such as ATP + H2O → ADP + Pi + H+ and
  maximises it. Any flux is a cycle; the check lists the reactions of a
  least-flux (pFBA) cycle rather than every reaction carrying flux. MEMOTE's
  metabolite lookup finds both water and hydroxide in Human-GEM (MetaNetX
  merges protonation states), so ties go to the candidate sharing the most
  cross-references with MEMOTE's shortlist. Couples the model lacks are listed
  as not found.

The closed-medium FVA formerly reported under the `energy-generating-cycles`
ID found internal loops rather than energy-generating cycles and was removed;
reports that still hold it hide it.

Blocked reactions (`flux-consistency`) are diagnostic in every profile. A
genome-scale reconstruction always has reactions that carry no flux under its
default bounds, so they are reported as a warning and never block release.
The report counts them per compartment against the compartment's size; a
reaction spanning compartments (a transport) is grouped under all of them, as
`c+m`. Dead-end and never-produced/never-consumed metabolites are split the
same way. The former `blocked-reaction-singletons` check repeated the blocked
reactions one per set and was removed.

`mass-balance` and `charge-balance` list pool, biomass and artificial
reactions (the conservation exclusions, plus reactions whose ID or name says
pool, pseudo, lumped or artificial, or that make or use a pool
metabolite) separately as unbalanced by design; only
ordinary reactions fail the check. Mass balance tests each reaction against
its formulas; `stoichiometric-consistency` tests the whole network without
formulas, so it also catches metabolites without a formula and loops of
reactions that together create matter.

## Suggested fixes

The validation report written by the `validate` workflow and by gap-filling
lists suggested fixes under the failed checks that a rule can fix. The JSON
report holds them as `validation.proposals` (the conservation workflow's
proposal records plus `checks`, the checks that produced each one):

| Check | Fixes |
| --- | --- |
| `stoichiometric-consistency` | The [conservation workflow](conservation.md)'s localization and proposal rules; the check also lists the blamed reactions, split by chemical flag |
| `formula-disagreement` | Set the formula or charge to the reference model's value, or to the value most compartments have |
| `fractional-coefficients` | Minimal coefficient edits that balance elements and charge; already balanced fractional stoichiometries are retained |
| `mass-balance`, `charge-balance`, `unusual-protons` | Solve existing coefficients first, then allow bounded combinations of missing small molecules/cofactor partners in one reaction compartment; formulas, charges and original reaction sides stay fixed |
| `charge-balance` | Only when no stoichiometry fix is found: change one metabolite's charge by one if that balances the reaction and unbalances none of its other reactions (low confidence, separate metabolite suggestion) |

The reference model supplies context, not restored reaction coefficients.
The [conservation proposal rules](conservation.md#proposal-rules) describe
the search bounds and ranking. Equally ranked solutions appear as alternatives
in the HTML, with element and charge balance before and after each change.
Formula/charge disagreements and inferred formulas remain separate,
low-confidence metabolite suggestions requiring independent chemical review.

In the HTML report, accept one fix per reaction (or per metabolite formula and
charge), or reject it; fixes left alone are not applied. Choices are kept in
the browser per model;
**Export decisions.jsonl** in the bar at the bottom writes them out, and
**Import decisions** loads a file back. Then apply them:

```bash
thg-run apply-decisions runs/validation/.../validation-report.json decisions.jsonl \
    --model path/to/model.xml -o path/to/model-fixed.xml
```

The command refuses a model whose SHA-256 differs from the report's, and an
invalid decision (an unknown proposal, two fixes for one target, a malformed
replacement, stoichiometry repairs that no longer balance elements and charge
or preserve reaction sides, or charge repairs that conflict when applied together) stops it
before anything is written. It writes the fixed model,
`model-fixed.ledger.jsonl`, and `model-fixed.validation-report.json`/`.html`
from re-validating with the same profile, reference model and exclusions, and
prints the checks whose status changed. Repeat with the new report until the
checks pass.

Reaction and metabolite IDs in the report open a panel with the equation,
formula, charge and connected reactions, and the filter boxes also match
names and subsystems.

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
