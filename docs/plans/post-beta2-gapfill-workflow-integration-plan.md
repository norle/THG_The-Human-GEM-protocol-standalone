# Post-β2 Gapfill Workflow Integration Plan

**Proposed repository file:** `docs/protocol/post-beta2-gapfill-workflow-integration-plan.md`

## Goal

Make gapfilling a first-class, reproducible stage of the canonical THG reference-model pipeline immediately after β2, while preserving β2 itself as an ungapfilled model artifact.

The intended scientific sequence is:

```text
β1
→ β2
→ preserved ungapfilled β2 artifact
→ gapfill
→ validated gapfilled reference artifact
→ downstream THG work
```

The important distinction is:

```text
β2 artifact != gapfilled model
```

Gapfilling follows β2 in the pipeline but never silently changes what “β2” means.

## 1. Architectural decision

Keep the existing standalone `beta2` workflow capable of terminating at the ungapfilled β2 artifact.

Add a canonical composite workflow named `reference`. It contains the existing
β1 and β2 scientific stages, then continues into the shared gapfill stages.
The standalone `gapfill` workflow uses the same gapfill stages after loading an
explicit external model.

Conceptually:

```text
β1 stages
→ β2 stages
→ validate-beta2
→ export-beta2
→ gate-beta2
──────────────── β2 artifact boundary ────────────────
→ load-gapfill-source
→ characterize-gapfill-baseline
→ generate-gapfill-plan
→ apply-gapfill
→ validate-gapfill
→ gate-gapfill
→ export-gapfilled-reference
```

The standalone `workflow: "gapfill"` DAG is:

```text
load-gapfill-source
→ characterize-gapfill-baseline
→ generate-gapfill-plan
→ apply-gapfill
→ validate-gapfill
→ gate-gapfill
→ export-gapfilled-reference
```

`reference` resolves `load-gapfill-source` from the completed `gate-beta2`
and `export-beta2` artifacts. `gapfill` resolves it from
`gapfill.input_model`. No post-β2 stage may accept an arbitrary model path when
running as part of `reference`.

`export-beta2` must continue to produce exactly the ungapfilled β2 model.

`apply-gapfill` must load a copy of that artifact and produce a new model.

This gives two independently identifiable model states:

```text
thg-beta2
thg-reference-gapfilled
```

A failure during gapfilling must never invalidate or overwrite the successfully produced β2 artifact.

The public gapfilled reference is created only after `gate-gapfill` passes.
Failed and partial attempts remain inspectable as candidate artifacts and
reports, but are never exported under the released reference filenames.

## 2. Make gapfill a first-class workflow capability

Add a strict `gapfill` workflow/configuration section to `workflow/config.py`.
Add `reference` as a registered workflow whose allowed sections are `beta1`,
`beta2`, and `gapfill`.

Register a reusable gapfill stage factory. Its stages must work after either
the in-run β2 handoff (`reference`) or the external model loader (`gapfill`).
The implementation must not invoke `thg-gapfill` as a subprocess.

Those stages should support both:

1. use inside the canonical post-β2 pipeline; and
2. a standalone first-class `workflow: "gapfill"` run against another COBRA model.

The canonical `reference` workflow must use the same gapfill implementation as
the standalone workflow. The existing `beta2` workflow remains independent and
continues to stop at its ungapfilled export.

## 3. Configuration contract

Gapfilling must be fully represented in the run configuration and snapshot.

Standalone example:

```json
{
  "workflow": "gapfill",
  "run": {"name": "example-gapfill", "output_dir": "../runs/example-gapfill"},
  "gapfill": {
    "input_model": "../inputs/models/model.json",
    "external_input": true,
    "method": "greedy",
    "max_additions": 500,
    "allowed_connections": [
      ["c", "e"],
      ["c", "m"]
    ],
    "candidate_types": ["A", "B", "C"],
    "validation_profile": "post-gapfill"
  }
}
```

For MILP:

```json
{
  "workflow": "gapfill",
  "run": {"name": "example-gapfill-milp", "output_dir": "../runs/example-gapfill-milp"},
  "gapfill": {
    "input_model": "../inputs/models/model.json",
    "external_input": true,
    "method": "milp",
    "universal_model": "../inputs/models/universal.xml",
    "objective": "biomass",
    "minimum_flux": 0.05,
    "max_additions": 100,
    "penalties": {},
    "validation_profile": "post-gapfill"
  }
}
```

The canonical `reference` configuration uses the same `gapfill` object but
omits `input_model` and `external_input`; its source is the in-run β2 handoff.
For standalone `gapfill`, `input_model` and `external_input: true` are
required; `external_input: false` is invalid because the standalone workflow
has no implicit β2 source.

The initial workflow method enum is exactly:

```text
greedy
deadends
milp
```

`deterministic` remains a lower-level Python strategy and is not a workflow
configuration value.

`method` and `validation_profile` are required. `max_additions` is a positive
integer. Transport methods require `allowed_connections` and
`candidate_types`; `milp` requires `universal_model`, `objective`,
`minimum_flux`, and `penalties`. Unknown or method-incompatible keys are
configuration errors.

`apply-all` is the only implemented application policy and is the implicit
default. There is no decision file and no human approval step in the initial
repository workflow. A future reviewed policy is explicitly deferred.

`task_suite` is optional. When supplied, it must point to an existing task
suite and its checksum must be included in the validation fingerprint. When it
is omitted, task results are reported as `not-requested`.

Method-specific configuration must be validated strictly. All external
candidate universes, universal models, task suites, and other scientific inputs
must be checksummed into the stage fingerprint.

## 4. Explicit β2 handoff

`gate-beta2` must consume the existing `export-beta2` model artifact, verify
its manifest record and checksum, run the β2 release-gate checks, and write a
machine-readable `beta2-gate.json` result.

The first post-β2 stage must consume that same checksum-verified β2 artifact
only when the gate result is passed.

It should never accept an arbitrary path internally when invoked as part of the reference pipeline.

The handoff should record:

```text
upstream workflow
upstream run
upstream stage
artifact role
artifact checksum
β2 validation result
β2 release/gate result
software version
```

If the β2 gate fails, the `reference` run must report an error, preserve the
β2 candidate and gate report, and stop before gapfill. It must not create a
gapfilled reference artifact.

An independently invoked `workflow: gapfill` may accept an external model, but
`external_input: true`, the source path, source checksum, and software version
must be recorded. It must never describe that model as a β2 artifact.

## 5. Characterize the ungapfilled baseline

Before generating additions, write a reproducible baseline report.

At minimum record:

```text
reaction count
metabolite count
gene count
blocked reactions
dead-end metabolites
network components
largest-component fraction
objective feasibility
configured metabolic-task results
```

This baseline becomes the reference for evaluating what the gapfill actually changed.

It should be produced by the shared THG validation/reporting implementation,
using the `post-gapfill` profile and the same validation conditions later used
for the after-report. If no task suite is configured, record
`not-requested`, not a passing task result. The report must also retain the
source model checksum and the validation profile/version.

Do not add a second gapfill-specific definition of blocked reactions, dead
ends, or network components.

## 6. Separate planning from mutation

Introduce a proposal-first boundary.

Recommended APIs:

```text
generate_gapfill_plan(...)
validate_gapfill_plan(...)
apply_gapfill_plan(...)
```

`generate_gapfill_plan` may internally execute the configured method, but it
must not mutate the source model. Its persistent output should describe the
proposed additions and the exact source model on which they were generated.

Each selected addition should record at least:

```json
{
  "schema_version": 1,
  "proposal_id": "...",
  "reaction_id": "...",
  "method": "greedy",
  "source": "...",
  "metabolites": {},
  "bounds": {"lower": -1000.0, "upper": 1000.0},
  "candidate_type": "A",
  "reason": "...",
  "cost": null,
  "coverage_or_improvement": {},
  "solver_evidence": {}
}
```

The plan header must include the source model checksum, method, normalized
parameters, implementation version, and the number of proposals. Proposal IDs
must be deterministic and unique. `validate_gapfill_plan` must reject duplicate
IDs, missing metabolites, existing reaction-ID collisions, unsupported bounds,
and any proposal that does not match the source checksum.

For generated transport reactions, record the source metabolites, source compartments, connection rule and candidate-generation algorithm.

For universal-model reactions, preserve the original reaction identifiers and source-model checksum.

## 7. Application policy

The initial repository workflow applies all valid proposals automatically. The
plan is an audit record, not a human approval queue.

`apply-gapfill` must therefore:

```text
load source model
validate gapfill plan
apply every valid proposal
write change ledger
```

There is no `reviewed` mode or decision file in this implementation. That
policy is deliberately deferred until an actual review workflow is needed.
Do not add a placeholder decision stage or silently support a second policy.

The final change ledger must make it possible to prove:

```text
gapfilled model
=
β2 model
+ exactly the planned gapfill additions
```

No additional mutation should occur implicitly. The plan and ledger must both
be copied into the export so the result can be audited without the original
working directory.

## 8. Apply gapfill on a private model copy

`apply-gapfill` must:

- load the source artifact identified by `load-gapfill-source`;
- copy it;
- verify that the plan was generated from that exact artifact;
- apply every planned addition once;
- annotate every added reaction with gapfill provenance;
- reject reaction-ID collisions and duplicate applications;
- reject additions that require new metabolites, genes, or compartments in the initial implementation;
- preserve every existing source object, bound, objective, and annotation unchanged;
- write a complete mutation ledger.

The source artifact remains untouched. In the `reference` workflow, this also
means the preserved β2 artifact remains untouched.

The supported mutation is therefore limited to adding new reactions whose
metabolites already exist in the source model. New model objects or changes to existing
objects require a separate, explicit extension to this plan.

Solver methods may use a temporary objective or temporary bounds on their
private working copy, but those temporary settings must be restored before the
gapfilled model is written.

After application, compare semantic model signatures rather than serialized
file bytes. The diff must contain only the planned reaction additions and the
provenance annotations on those additions. It must contain no removed or
changed β2 reactions, metabolites, genes, compartments, or objective entries.

## 9. Validate after gapfill

Run the common validation system after mutation.

The report must show **before → after** changes, especially:

```text
blocked reactions
dead-end metabolites
network components
largest connected component
metabolic-task performance
objective feasibility
reaction/metabolite counts
mass balance
charge balance
energy-generating cycles
```

It is not sufficient for a method simply to report that it added reactions.

Every check must have an explicit status such as `passed`, `warning`,
`failed`, `error`, `not-requested`, or `not-evaluable`. Infrastructure errors
are errors, not successful validations. The report must identify the source
and resulting model checksums, validation profile, solver conditions, task
suite, and metric deltas.

At minimum, emit warnings for non-blocking validation findings, a partial
algorithm result, a worsening blocked/dead-end metric, or a task suite that
was not requested when the profile expected one.

## 10. Gapfill acceptance gate

`gate-gapfill` must always write `gapfill-gate.json`. It is the only stage that
decides whether the result may be exported as the gapfilled reference.

The gate should require:

- gapfill execution completed without infrastructure failure;
- every added reaction is represented in the gapfill plan and change ledger;
- no undeclared model mutation occurred;
- validation completed;
- configured release-blocking checks pass;
- configured metabolic tasks pass when a task suite is required;
- solver metadata is present for solver-backed methods;
- all external candidate sources have checksums/provenance.

The result status must distinguish:

```text
passed  — export is allowed
warning — non-blocking diagnostic findings exist; export is allowed
blocked — a partial result or failed release-blocking check; export is not allowed
error   — configuration, input, algorithm, mutation, or infrastructure failure
```

A `partial` gapfill result is preserved as an inspectable candidate and emits a
warning plus a blocked gate. It must not be promoted. Errors also prevent
export, but their report must remain available in the failed attempt directory
and in the run log.

`export-gapfilled-reference` must refuse to write the released reference files
unless `gapfill-gate.json` has status `passed` or `warning` with no blocking
findings.

## 11. Export artifacts

`export-gapfilled-reference` should include at minimum:

```text
thg-reference-gapfilled.json
thg-reference-gapfilled.xml
gapfill-plan.jsonl
gapfill-change-ledger.jsonl
gapfill-report.json
gapfill-gate.json
validation-report.json
validation-report.html
validation-summary.md
model-diff.json
model-signature.json
provenance.json
summary.json
```

The export must retain a direct reference to the exact β2 artifact from which it was derived.
That reference must include the upstream run, stage, role, checksum, β2 gate
result, and source model checksum used to generate the plan.

## 12. Downstream pipeline contract

The canonical downstream THG pipeline should consume the **gapfilled reference artifact**, not silently select between β2 and gapfilled files.

The intended reference branch becomes:

```text
β1
→ β2
→ gapfill
→ gapfilled reference branch
```

For the canonical route, Final THG must receive the exported gapfilled
reference artifact through an explicit `reference_upstream` (or an equivalent
named artifact role). Direct `beta2_model` input remains available for
independent β2 work, but must not be used by the canonical reference route.

## 13. CLI behavior

Keep `thg-gapfill` as a useful direct tool, but document it as a lower-level entry point.

Scientific pipeline usage should be through `thg-run`, rather than requiring the user to manually run `thg-gapfill` and then decide which model downstream stages should consume.

`thg-run gapfill` and `thg-run reference` must print the final report path and
status. Errors use a failing exit status; warnings print clearly and still
leave the report and candidate artifacts available.

## 14. Resumability

Every gapfill stage must participate in normal fingerprints and invalidation.

Changing:

```text
method
max_additions
candidate types
allowed connections
universal model
objective
penalties
validation profile
task suite
```

must invalidate the appropriate gapfill stages and descendants without rerunning β2.

Forcing post-gapfill validation must not rerun the gapfill algorithm.

Forcing plan generation must regenerate the plan and invalidate
apply/validation/gate/export.

The fingerprint boundaries are:

```text
β2 artifact checksum
  → load source, baseline, plan, apply, validation, gate, export

gapfill method and algorithm parameters
  → plan, apply, validation, gate, export

validation profile and task suite
  → validation, gate, export
```

The plan must also update the runner's resume policy for `reference`: changing
gapfill settings must update the snapshot and invalidate from the first
affected gapfill stage while retaining valid β1/β2 artifacts. The β2 source
identity remains immutable for that run. If this policy is not implemented,
the alternative is a separate `gapfill` run against an explicit completed β2
artifact; silently rerunning β2 is not acceptable.

## 15. Testing

Add integration tests covering:

- β2 artifact is unchanged after post-β2 stages;
- canonical pipeline continues automatically from β2 into gapfill;
- failed β2 gate prevents gapfill;
- the standalone workflow requires and records an external input checksum;
- `apply-all` is the default and requires no decision file;
- reviewed/decision-file behavior is not exposed yet;
- gapfill configuration participates in fingerprints;
- rerunning validation does not rerun gapfill;
- changing algorithm parameters reruns only the affected gapfill stages;
- every added reaction exists in the plan and ledger;
- no unplanned mutation is present in the output diff;
- solver metadata is recorded for MILP;
- external universal-model checksum changes invalidate the plan;
- before/after validation metrics are preserved;
- failed/partial gapfills do not silently become released models;
- warnings and errors are written to machine-readable reports and surfaced by the CLI;
- Final THG consumes the canonical gapfilled reference artifact.

## 16. Completion criterion

The canonical model lineage must be unambiguous:

```text
β2
  checksum A
  ungapfilled
      │
      ▼
gapfill plan
      │
      ▼
gapfilled reference
  checksum B
  exact additions documented
```

The canonical run applies all valid gapfill proposals automatically, emits
clear warnings or errors when something is wrong, and exports a gapfilled
reference only after the release gate passes. No human must leave the workflow
system to choose the next model, and no human approval step is required in the
initial implementation.
