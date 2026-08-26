# THG Model Validation and Quality Report Plan

**Proposed repository file:** `docs/protocol/thg-validation-quality-report-plan.md`

## Goal

Create a unified THG validation system that produces both machine-readable validation evidence and a human-readable model-quality report similar in usability to a MEMOTE snapshot report.

The report should answer, at a glance:

```text
What is in this model?
Is it structurally valid?
How chemically consistent is it?
How connected is the network?
How much of it is blocked?
Where are its dead ends?
Does it perform its required metabolic tasks?
What changed relative to the previous model stage?
Can this model pass its configured release gate?
```

The canonical validation result must be THG-owned and independent of MEMOTE.

MEMOTE remains an optional external validation panel.

## 1. One canonical validation schema

Define a versioned report contract, for example:

```text
thg.validation.report/v1
```

All workflows use the same schema:

```text
β1
β2
post-gapfill
Human Database
Final THG
cell-specific models
standalone validation
```

The HTML report must be rendered from the canonical JSON artifact.

The renderer must not independently recompute validation results.

## 2. Standard report artifacts

Every full validation run should produce:

```text
validation-report.json
validation-report.html
validation-summary.md
```

Large detail sets may additionally be exported as:

```text
blocked-reactions.tsv
dead-end-metabolites.tsv
network-components.tsv
unbalanced-reactions.tsv
metabolic-tasks.tsv
```

The JSON remains authoritative.

## 3. Report header

The top of the report should show:

```text
model ID
model checksum
workflow/run
upstream artifact
software version
validation profile
timestamp
solver/interface
task-suite version
MEMOTE version, when run
overall gate status
```

Then show basic counts:

```text
reactions
metabolites
genes
compartments
exchange reactions
demand reactions
sink reactions
other boundary reactions
```

## 4. Structural integrity section

Report:

```text
duplicate metabolite IDs
duplicate reaction IDs
duplicate gene IDs
dangling references
invalid GPR rules
reactions without GPRs
orphan metabolites
orphan genes
```

Each metric should provide count, fraction where meaningful, status, affected IDs and severity.

## 5. Chemical consistency section

Report reaction classifications rather than only pass/fail:

```text
mass balanced
mass unbalanced
not evaluable because formula is missing
excluded boundary
excluded biomass/pseudo
```

Similarly for charge:

```text
charge balanced
charge unbalanced
not evaluable because charge is missing
excluded
```

Do not count “not evaluable” as equivalent to “balanced”.

Also report:

```text
metabolites missing formulas
metabolites missing charges
stoichiometric-consistency result
unconserved metabolites, where available
```

## 6. Dead-end and production/consumption section

Distinguish different meanings of “dead end”.

### Structural dead ends

Topology-only assessment of metabolites that only occur on one stoichiometric side of the modeled network.

### Flux/functional dead ends

Where solver-backed analysis supports it, identify metabolites that cannot be functionally produced and/or consumed under declared validation conditions.

Report separately:

```text
structural dead ends
not produced
not consumed
functional dead ends
```

Do not collapse these definitions into one number.

## 7. Blocked reactions

Define a canonical **universally blocked** metric.

Run blocked-reaction analysis with model exchanges opened according to an explicit validation-medium policy so that results represent network blocking rather than an accidentally restrictive current medium.

Report:

```text
blocked reaction count
blocked reaction fraction
unblocked reaction count
blocked reaction IDs
blocked reaction classes/compartments
```

Optionally also report:

```text
blocked under configured physiological medium
```

as a separate metric.

Never mix the two.

## 8. Network connectivity

Integrate network component analysis into standard validation.

Report at least:

```text
number of connected components
nodes in largest component
reactions in largest component
metabolites in largest component
fraction of network in largest component
component size distribution
number of singleton/tiny components
IDs contained in each disconnected component
compartments represented in each component
```

Do not reduce network connectivity to only a fully-connected yes/no result.

## 9. Multiple connectivity views

Support explicitly named network views.

At minimum:

```text
raw structural network
internal network with boundary/pseudo reactions excluded
functional network with universally blocked reactions removed
```

A future currency-metabolite-filtered view may be added, but only with an explicit, versioned exclusion policy.

Never silently remove highly connected metabolites.

## 10. Functional/solver section

When the selected profile enables solver analysis, report:

```text
solver status
objective feasibility
objective value
universally blocked reactions
flux consistency
stoichiometric consistency
energy-generating cycles
unbounded reactions
minimal inconsistent-set diagnostics where supported
```

Infrastructure errors must be visually different from biological/model failures.

Use distinct states such as:

```text
FAILED
ERROR
NOT RUN
NOT EVALUABLE
WARNING
PASSED
```

## 11. Metabolic tasks

Make versioned metabolic task suites a core section of the report.

Show:

```text
task-suite ID
task-suite version
number of tasks
passed
failed
not evaluable
infrastructure errors
```

For every task show:

```text
task ID
group
expected result
observed result
solver status
objective/flux value
temporary reactions used
medium/bounds modifications
diagnostics
```

An empty task suite must be shown as:

```text
NOT REQUESTED
```

not as a biological pass.

## 12. Before/after comparison

Whenever validation follows a model-changing stage, generate a delta panel.

Examples:

```text
β1 → β2
β2 → gapfilled reference
reference branches → Final THG
generic GEM → cell-specific GEM
```

Show deltas for:

```text
reactions
metabolites
genes
blocked reactions
blocked fraction
dead ends
network component count
largest-component fraction
unbalanced reactions
metabolic tasks
objective feasibility
```

Example:

```text
Blocked reactions      2,431 → 1,780   (-651)
Dead-end metabolites     812 →   493   (-319)
Network components        43 →    12    (-31)
Tasks passed            31/40 → 38/40
Added reactions             0 →    57
```

## 13. Release gates versus diagnostics

Do not make every reported metric release-blocking.

Every check has a severity:

```text
blocking
warning
informational
```

Profiles determine the policy.

Recommended profiles:

```text
structural-fast
beta1-standard
beta2-standard
post-gapfill
cell-specific
final-standard
release-full
diagnostic-full
```

## 14. No single THG quality score initially

Do not introduce an overall numeric score in the first implementation.

Use a dashboard of explicit metrics plus a gate status:

```text
RELEASE GATE: PASSED
```

or:

```text
RELEASE GATE: FAILED
2 blocking findings
```

A composite score can be considered later if there is a clear scientific use case and documented weighting.

## 15. MEMOTE integration

MEMOTE remains optional and complementary.

When enabled, show an external-tool panel containing:

```text
MEMOTE version
MEMOTE execution status
MEMOTE score
link/path to MEMOTE HTML
link/path to MEMOTE JSON
```

Do not reinterpret a MEMOTE score as the THG release gate.

Preserve original MEMOTE HTML/JSON artifacts.

## 16. Human-readable HTML

The HTML report should have a compact landing dashboard with sections for:

```text
Overview
Structural integrity
Chemistry
Dead ends
Blocked reactions
Network connectivity
Solver/functionality
Metabolic tasks
Changes from upstream
MEMOTE
Provenance
```

For network components, useful displays include:

```text
component size distribution
largest-component percentage
top disconnected components
reaction/metabolite counts per component
```

Avoid requiring a live web server.

## 17. Validation DAG

Expand the registered validation workflow into explicit stages:

```text
validate-load
→ validate-structural
→ validate-chemical
→ validate-topology
→ validate-network
→ validate-solver
→ validate-tasks
→ validate-memote
→ assemble-validation-report
→ render-validation-report
```

Stages may be skipped according to profile, but skipped states must remain visible in the final report.

## 18. Shared use by scientific workflows

Scientific workflows should call the same validation/report stages or shared implementation.

Do not maintain one validation interpretation in β2, another in gapfill and another in Final THG.

The same metric name must mean the same calculation everywhere.

Workflow-specific checks can be added under a dedicated section:

```text
workflow invariants
```

without redefining common metrics.

## 19. Testing

Add unit/integration coverage for:

- deterministic report JSON;
- HTML generated only from report JSON;
- structural counts;
- missing-formula versus unbalanced distinction;
- universally blocked reactions under opened exchanges;
- medium-specific blocking reported separately;
- dead-end definition separation;
- network component counts;
- largest-component fractions;
- internal versus functional connectivity views;
- task pass/fail/not-requested semantics;
- infrastructure errors distinct from test failures;
- before/after metric deltas;
- profile severity/release-gate behavior;
- MEMOTE absent, successful and failed states;
- very large result lists rendered without changing the canonical JSON.

## 20. Completion criterion

A researcher opening one HTML file should be able to understand the model’s technical and functional state without manually running separate scripts.

The same run must also provide structured JSON sufficient for CI and downstream comparison.

The final model-quality interface becomes:

```text
Model
  ↓
THG validation
  ├─ canonical JSON evidence
  ├─ detailed machine-readable lists
  ├─ human-readable HTML report
  ├─ optional MEMOTE report
  └─ explicit release-gate decision
```

The report should make problems discoverable rather than hiding them behind one score.
