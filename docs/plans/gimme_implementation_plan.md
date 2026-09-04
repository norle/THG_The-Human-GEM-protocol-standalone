# Native GIMME Implementation Plan for THG Standalone

## 1. Goal

Implement a **native, solver-agnostic GIMME workflow** inside `THG_The-Human-GEM-protocol-standalone` so that cell-type-specific reconstruction no longer depends on Troppo/Cobamp or a specific Gurobi version.

The implementation should:

- reproduce the scientific intent of the legacy THG cell-type-specific workflow;
- use COBRApy/optlang rather than Troppo;
- work with GLPK by default and optionally Gurobi/CPLEX through COBRApy;
- separate transcript-to-reaction scoring, GIMME optimization, multi-sample consensus, model reduction, and validation;
- preserve the standalone repo's provenance/audit architecture;
- improve several weaknesses in the legacy implementation rather than copying them verbatim.

The target scientific pipeline is:

```text
expression evidence
    ↓
gene ID normalization
    ↓
GPR integration → reaction expression scores
    ↓
native GIMME per sample
    ↓
reaction activity classifications
    ↓
multi-sample consensus
    ↓
reduction plan
    ↓
reduced cell-specific model
    ↓
context exchange configuration
    ↓
biological + structural validation
    ↓
export
```

---

## 2. Non-goals

The first implementation should **not** try to become a generic context-specific reconstruction framework.

Do not initially implement:

- tINIT / ftINIT;
- CORDA;
- FASTCORE;
- mCADRE;
- MBA;
- generic MILP-based reconstruction;
- solver-specific Gurobi code;
- automatic cell-type phenotype inference from literature.

The first goal is one well-tested, transparent implementation of GIMME that reproduces the intended THG workflow.

---

## 3. Design principles

### 3.1 Native COBRApy/optlang implementation

Use the solver already attached to the COBRApy model.

Avoid:

- `troppo`;
- `cobamp`;
- direct `gurobipy` calls;
- explicit solver-version checks;
- manual irreversible-model conversion unless mathematically necessary.

The same code should run under:

```python
model.solver = "glpk"
```

or, when available:

```python
model.solver = "gurobi"
```

without changing GIMME logic.

### 3.2 Do not let GIMME delete reactions

GIMME should produce **evidence and activity classifications**, not mutate the model.

Deletion belongs to the existing proposal/reduction stages.

### 3.3 Separate scientific concepts

Keep distinct configuration parameters for:

1. expression threshold;
2. numerical flux tolerance;
3. multi-sample consensus threshold.

Do not reuse one threshold for all three.

### 3.4 Explicit missing-data semantics

Do not encode missing expression as a magic numeric value such as `-1`.

Represent it explicitly.

### 3.5 Fail loudly on solver/sample failures

A failed GIMME sample must never silently become an all-zero activity vector.

A failed sample should be:

- marked failed;
- excluded only if the configured policy permits exclusion;
- included in the audit report;
- able to fail the workflow when too many samples fail.

---

# 4. Proposed package structure

Refactor the current `cell_specific` package toward:

```text
src/thg_protocol/cell_specific/
    __init__.py
    expression.py
    gpr.py
    gimme.py
    consensus.py
    reduction.py
    exchange.py
    validation.py
```

The exact split can be adjusted to match repo conventions, but responsibilities should remain separate.

## `expression.py`

Responsibilities:

- normalized expression record representation;
- sample grouping;
- gene identifier handling;
- aggregation of duplicate measurements;
- missingness tracking.

## `gpr.py`

Responsibilities:

- parse GPRs;
- map gene expression to reaction expression scores;
- propagate missingness;
- expose deterministic, tested AND/OR semantics.

## `gimme.py`

Responsibilities:

- objective/reference optimization;
- construction of GIMME inconsistency objective;
- objective-retention constraints;
- solving;
- result extraction;
- reaction activity classification;
- solver diagnostics.

## `consensus.py`

Responsibilities:

- combine per-sample GIMME results;
- calculate reaction support fractions;
- distinguish failed samples from inactive reactions;
- generate consensus evidence.

## `reduction.py`

Responsibilities:

- convert consensus evidence into retain/remove proposals;
- apply approved decisions;
- remove orphan genes/metabolites;
- record reduction ledger.

The current reduction code can be moved here incrementally rather than rewritten all at once.

## `validation.py`

Responsibilities specific to cell-specific models:

- required metabolic tasks;
- objective retention;
- regressions relative to source model;
- failed-sample checks;
- context-specific biological checks.

Generic GEM validation should remain in the existing top-level validation module.

---

# 5. Data model

Introduce small immutable result objects.

## 5.1 Reaction expression evidence

```python
from dataclasses import dataclass
from typing import Literal

@dataclass(frozen=True)
class ReactionExpressionEvidence:
    reaction_id: str
    score: float | None
    status: Literal[
        "measured",
        "partial",
        "unknown",
        "no-gpr",
    ]
    genes_used: tuple[str, ...]
    missing_genes: tuple[str, ...]
```

This object should distinguish:

- known zero expression;
- unknown expression;
- no GPR;
- partially observed GPR.

Those must not collapse into the same numeric value.

## 5.2 GIMME objective requirement

```python
@dataclass(frozen=True)
class GimmeObjectiveRequirement:
    id: str
    coefficients: dict[str, float]
    minimum_fraction_of_optimum: float
```

This permits:

- a single biomass reaction;
- ATP maintenance;
- a true weighted multi-reaction linear objective.

## 5.3 Per-sample GIMME result

```python
@dataclass(frozen=True)
class GimmeResult:
    sample_id: str
    status: str

    inconsistency_score: float | None

    reaction_fluxes: dict[str, float]
    flux_active: dict[str, bool]
    expression_supported: dict[str, bool]
    reaction_active: dict[str, bool]

    penalties: dict[str, float]

    objective_maxima: dict[str, float]
    objective_requirements: dict[str, float]
    objective_achieved: dict[str, float]

    solver_name: str
    warnings: tuple[str, ...]
```

The exact serialization may be JSON/JSONL rather than direct dataclass output, but all of this evidence should remain available.

---

# 6. GPR expression integration

This should be implemented before the GIMME solver because bad reaction scores make a correct GIMME implementation scientifically wrong.

## 6.1 Default numeric semantics

For measured genes:

```text
AND → minimum
OR  → maximum
```

Examples:

```text
G1 AND G2
G1 = 10
G2 = 4
reaction score = 4
```

```text
G1 OR G2
G1 = 10
G2 = 4
reaction score = 10
```

Do **not** reproduce the legacy behavior in which an AND containing a zero can return the maximum expression value.

## 6.2 Missing genes

Missingness should propagate separately from numeric scoring.

Recommended default policy:

```text
fully measured GPR      → measured score
partially measured GPR  → partial
no measured genes       → unknown
no GPR                  → no-gpr
```

For a partial rule, calculate a score only when the Boolean structure permits a defensible result.

Examples:

```text
G1 AND G2
G1 = 0
G2 = unknown
```

This reaction is effectively constrained by a known inactive subunit and may be classified as low/inactive rather than simply "unknown".

```text
G1 OR G2
G1 = high
G2 = unknown
```

The known active isoenzyme is sufficient to support the reaction.

This is best implemented using a small expression-tree evaluator rather than regex replacement plus `eval`.

## 6.3 Parser

Prefer using the GPR representation already available from COBRApy if it exposes an appropriate AST.

If a separate parser is needed:

- keep it very small;
- support `and`, `or`, and parentheses;
- avoid arbitrary Python `eval`;
- add exhaustive unit tests.

---

# 7. Native GIMME mathematical formulation

## 7.1 Inputs

For each reaction \(i\):

- reaction expression score \(e_i\);
- expression threshold \(e_\mathrm{cut}\);
- model flux variables;
- one or more required metabolic objectives.

Define the penalty:

\[
p_i =
\begin{cases}
e_\mathrm{cut} - e_i & \text{if expression is known and } e_i < e_\mathrm{cut} \\
0 & \text{otherwise}
\end{cases}
\]

Unknown/no-GPR reactions should be unpenalized by default.

Make the unknown policy configurable later if needed.

## 7.2 Objective

Minimize expression inconsistency:

\[
\min \sum_i p_i |v_i|
\]

subject to:

\[
Sv = 0
\]

reaction bounds and required objective constraints.

## 7.3 Absolute flux using COBRApy variables

COBRApy already represents net reaction flux from forward and reverse variables.

Use:

```python
absolute_flux_expression = (
    reaction.forward_variable
    + reaction.reverse_variable
)
```

Then:

```python
gimme_objective = sum(
    penalty[reaction.id] *
    (
        reaction.forward_variable
        + reaction.reverse_variable
    )
    for reaction in model.reactions
)
```

Minimize that expression.

This avoids manually splitting reversible reactions.

Before finalizing this implementation, add a small numerical test confirming that the COBRApy forward/reverse representation behaves as expected for reversible reactions under each supported solver.

---

# 8. Required metabolic objectives

## 8.1 Compute reference maxima separately

For each configured objective requirement:

1. copy or use a reversible model context;
2. set the objective expression;
3. maximize it;
4. require an optimal solver status;
5. require a meaningful positive maximum where appropriate;
6. record the maximum.

Then calculate:

\[
f_\mathrm{required}
=
\alpha f_\mathrm{max}
\]

where \(\alpha\) is `minimum_fraction_of_optimum`.

## 8.2 Add a linear constraint

For each required function:

\[
c^T v \ge f_\mathrm{required}
\]

Do not implement this by mutating a reaction lower bound unless the objective truly consists of exactly one reaction with coefficient +1.

Using a solver constraint makes multi-reaction objectives mathematically correct.

## 8.3 Initial THG defaults

Do not hard-code these into the solver itself, but provide a documented example matching the legacy biological intent:

- biomass: `MAR13082`;
- ATPase/ATP maintenance: `MAR03964`.

The exact required fractions should be made explicit in config and reviewed scientifically.

The legacy implementation's combination of:

- forcing 20% lower bounds before GIMME;
- then supplying 0.1 biomass / 0.9 ATPase as separate Troppo objective dictionaries;
- `obj_frac = 1.0`;

should **not** be reproduced blindly.

---

# 9. Reaction activity classification

Do not equate:

```text
one optimal flux vector == reaction membership
```

After solving, track at least:

```text
expression_supported
flux_active
gimme_active
```

Recommended initial classification:

```python
expression_supported = (
    evidence.score is not None
    and evidence.score >= expression_threshold
)

flux_active = abs(flux) > flux_activity_tolerance

gimme_active = (
    expression_supported
    or evidence.status in {"unknown", "no-gpr"}
    or flux_active
)
```

This is deliberately conservative and resembles the intended GIMME activity logic better than using only `flux != 0`.

### Optional stronger future classification

A later enhancement could use FVA under the optimal/near-optimal GIMME inconsistency score to determine whether a low-expression reaction is *required or possible* rather than relying on one optimum.

Do not make this part of v1.

---

# 10. Multi-sample GIMME

The legacy THG pipeline runs GIMME independently across many transcriptomic samples.

Preserve that approach.

For every successful sample \(s\), produce:

```text
reaction × sample → active/inactive
```

Then define consensus support for reaction \(i\):

\[
support_i =
\frac{
  \#\{successful\ samples\ where\ reaction\ i\ is\ active\}
}{
  \#successful\ samples
}
\]

## 10.1 Do not count solver failures as zero activity

A failed sample is not an inactive sample.

Store:

```text
sample status:
- passed
- solver-failed
- invalid-input
- objective-infeasible
```

Then enforce a workflow-level policy such as:

```yaml
minimum_successful_sample_fraction: 0.95
```

If the successful sample fraction falls below the requirement, the workflow fails.

## 10.2 Consensus reduction policy

For compatibility with the conservative legacy behavior, default to:

```text
remove only reactions with support == 0
```

Represent this as:

```yaml
consensus_presence_threshold: 0.0
```

with removal when:

```text
support <= threshold
```

This makes the current `activity-matrix` logic reusable downstream.

---

# 11. Workflow integration

Replace the current scientific interpretation of the cell-specific workflow with explicit reconstruction stages.

Recommended stage sequence:

```text
load-source-model
collect-expression-evidence
normalize-gene-identifiers
map-expression-to-model
compute-reaction-expression
run-gimme
aggregate-gimme-activity
generate-reduction-plan
apply-reduction-decisions
apply-reduction
configure-context-exchanges
validate-cell-specific
export-cell-specific
```

## 11.1 Keep existing `gpr-threshold`

Do not delete it.

Keep it as a lightweight baseline strategy:

```yaml
reduction_strategy: gpr-threshold
```

but document that it is **not** equivalent to GIMME.

## 11.2 Keep `activity-matrix`

Keep this strategy for externally generated reconstruction/activity matrices:

```yaml
reduction_strategy: activity-matrix
```

But rename/document the semantics clearly:

> The matrix is reaction activity or reconstruction output; it is not interpreted as raw transcript abundance.

Prefer eventually requiring labeled reaction IDs rather than row-order-only matrices.

## 11.3 Add native strategy

```yaml
reduction_strategy: gimme
```

This becomes the recommended strategy for reproducing the legacy THG cell-type-specific workflow.

---

# 12. Proposed configuration

Example:

```yaml
workflow: cell-specific

cell_specific:
  input_model: inputs/model.xml
  expression_file: inputs/expression.gct
  gene_identifier_namespace: Ensembl

  reduction_strategy: gimme

  sample_aggregation: none

  gpr:
    and_rule: min
    or_rule: max
    unknown_policy: unpenalized

  gimme:
    expression_threshold: 1.0
    flux_activity_tolerance: 1.0e-7

    objectives:
      - id: biomass
        coefficients:
          MAR13082: 1.0
        minimum_fraction_of_optimum: 0.2

      - id: atp_maintenance
        coefficients:
          MAR03964: 1.0
        minimum_fraction_of_optimum: 0.2

    minimum_successful_sample_fraction: 0.95

  consensus:
    presence_threshold: 0.0

  preserved_reactions: []

  validation_profile: cell-specific-standard
  task_suite: human-essential
```

Do not commit the example numerical expression threshold as a scientifically approved default until the expression units and transformation are explicitly defined.

---

# 13. Config validation

Update the workflow config validator to validate:

- `reduction_strategy` includes `gimme`;
- expression threshold is finite;
- flux tolerance is positive;
- objective list is non-empty;
- objective coefficients are finite;
- objective fractions are within `(0, 1]`;
- objective reaction IDs exist in the model;
- successful-sample fraction is within `[0, 1]`;
- consensus threshold is within `[0, 1]`;
- incompatible settings are rejected.

Do not silently use legacy magic defaults.

---

# 14. Validation profile

Create a dedicated:

```text
cell-specific-standard
```

profile.

A cell-specific model should not pass merely because the SBML structure is valid.

## Required release conditions

At minimum:

1. generic reference integrity passes;
2. IDs/GPRs are valid;
3. solver is functional;
4. required GIMME objectives remain feasible;
5. essential metabolic task suite passes;
6. configured cell-specific tasks pass;
7. successful sample fraction meets the configured minimum;
8. no required exchange configuration references invalid/internal reactions;
9. no solver/infrastructure error is silently treated as pass.

## Status semantics

Use:

```text
passed
failed
indeterminate
```

An infrastructure error in a release-blocking check should produce `indeterminate` or `failed`, never implicit pass.

---

# 15. Test strategy

Testing is the most important part of this implementation.

## 15.1 GPR unit tests

Cover at least:

```text
A
A AND B
A OR B
(A AND B) OR C
A AND (B OR C)
```

with:

- high/high;
- high/low;
- low/low;
- known zero;
- unknown gene;
- partially observed complex;
- partially observed isoenzymes;
- no GPR.

Explicitly include regression tests proving:

```text
A=0, B=100
A AND B != 100
```

## 15.2 Tiny-model GIMME tests

Create a minimal synthetic COBRA model with:

- one required objective;
- two alternative pathways;
- one high-expression pathway;
- one low-expression pathway.

Test that GIMME prefers the expression-consistent path.

Then create a case in which the low-expression path is required to retain the metabolic objective and verify that GIMME keeps flux through it despite the penalty.

## 15.3 Reversible reaction test

Construct a reversible reaction used in the negative direction.

Verify that:

- the inconsistency objective uses absolute flux;
- forward/reverse solver variables produce the correct penalty;
- the result is solver-independent within tolerance.

## 15.4 Multi-objective requirement test

Use two independent required functions.

Verify both minimum constraints are met.

Also test a true weighted linear objective to prove that the implementation handles multi-reaction objective expressions correctly.

## 15.5 Unknown-expression test

Verify that unknown reactions are unpenalized under the default policy.

Verify known zero and unknown are not treated identically.

## 15.6 Failed sample test

Simulate one sample that cannot satisfy the configured objective requirement.

Verify:

- sample is marked failed;
- its activity column is not treated as zeros;
- it is excluded from the consensus denominator only according to policy;
- workflow fails if successful-sample fraction is below the configured minimum.

## 15.7 Consensus tests

Given known Boolean activity matrices, verify:

```text
support == 0
support == 0.25
support == 1.0
```

and correct retain/remove decisions around threshold boundaries.

## 15.8 Solver portability

CI:

- GLPK required.

Optional marked tests:

- Gurobi when available.

Compare:

- optimal inconsistency score;
- objective feasibility;
- reaction activity classifications.

Do not require identical raw flux vectors because degenerate LPs can have multiple valid optima.

---

# 16. Legacy regression comparison

Before removing Troppo from the scientific path, create a small frozen compatibility fixture.

## 16.1 Reference fixture

Use:

- a small model;
- fixed reaction-expression scores;
- fixed objective;
- fixed threshold.

Run the old Troppo implementation once and store:

- expression scores;
- objective maximum;
- objective requirement;
- optimal inconsistency score;
- Troppo-reported active reactions;
- raw flux vector for diagnostics.

The fixture should be stored as plain JSON/CSV test data.

Troppo should **not** remain a test dependency after the reference is frozen.

## 16.2 Comparison criteria

Native implementation should match or explain differences in:

1. objective feasibility;
2. optimal inconsistency value;
3. high-expression reaction retention;
4. required low-expression reaction usage;
5. active-reaction classification.

Do not require byte-for-byte equivalence with the old THG `flux != 0` post-processing because that behavior should intentionally be improved.

---

# 17. Provenance artifacts

For every cell-specific run, save:

```text
expression-evidence.jsonl
gene-mapping.jsonl
reaction-expression/<sample>.jsonl
gimme-results/<sample>.json
gimme-activity-matrix.csv
gimme-sample-status.jsonl
consensus-reaction-activity.jsonl
reduction-plan.jsonl
reduction-decisions.jsonl
reduction-ledger.jsonl
cell-specific-validation.json
```

The activity matrix should include reaction IDs, not just implicit row order.

A suitable tabular format would be:

```csv
reaction_id,sample_1,sample_2,sample_3
MAR00001,1,1,0
MAR00002,0,0,0
...
```

Also record:

- source model signature/checksum;
- expression source checksum;
- solver name;
- solver version if available;
- configuration snapshot;
- THG package version/commit;
- numerical tolerances.

---

# 18. Activity-matrix hardening

The current matrix reducer should be made ID-safe.

Instead of accepting only:

```text
N rows == N model reactions
```

require or strongly prefer:

```text
reaction_id + activity columns
```

Validate that:

```text
set(matrix reaction IDs)
==
set(model reaction IDs)
```

and reorder explicitly to model order.

If legacy unlabeled MAT/CSV files remain supported, require:

- an explicit `legacy_row_order: true`;
- model signature/checksum;
- a warning in the report.

---

# 19. Exchange handling

Cell-specific exchange configuration should verify that the target reaction is actually:

- a boundary reaction;
- exchange;
- demand;
- or sink,

unless an explicit override is set.

Do not allow a typo in an exchange configuration to silently modify an internal metabolic reaction.

Suggested config:

```yaml
allow_internal_bound_override: false
```

---

# 20. Documentation

Add:

```text
docs/tools/gimme.md
docs/workflows/cell-specific.md
```

## `gimme.md` should include

- mathematical formulation;
- expression penalty definition;
- missing expression semantics;
- objective-retention constraints;
- solver independence;
- reaction activity classification;
- differences from Troppo;
- differences from the old THG implementation.

## Cell-specific workflow docs should clearly distinguish

```text
gimme
gpr-threshold
activity-matrix
```

and explain when each should be used.

---

# 21. Implementation sequence

The work should be split into reviewable steps.

## Phase 1 — GPR scoring foundation

Implement:

```text
cell_specific/gpr.py
```

with:

- reaction evidence dataclass;
- GPR AST evaluation;
- min/max rules;
- missingness propagation;
- comprehensive unit tests.

**Acceptance criteria**

- no `eval`;
- zero and unknown are distinguishable;
- legacy anomalous AND behavior is not reproduced;
- all GPR tests pass.

---

## Phase 2 — Core native GIMME solver

Implement:

```text
cell_specific/gimme.py
```

with:

- penalty calculation;
- objective-max calculation;
- objective-retention constraints;
- optlang inconsistency objective;
- solver status handling;
- result object;
- no model mutation outside a model context/copy.

**Acceptance criteria**

- synthetic pathway tests pass under GLPK;
- reversible-flux test passes;
- objective requirement is enforced;
- unknown reactions are unpenalized by default;
- no Troppo/Cobamp/Gurobi-specific imports.

---

## Phase 3 — Reaction activity classification

Add:

```text
expression_supported
flux_active
gimme_active
```

to results.

**Acceptance criteria**

- highly expressed reactions are not lost merely because one optimum gives zero flux;
- reactions required for objective feasibility become active even when expression is below threshold;
- classification is deterministic for the fixture.

---

## Phase 4 — Multi-sample orchestration

Implement per-sample execution and consensus.

Do this serially first.

Only add process-level parallelism after correctness and deterministic error handling are established.

**Acceptance criteria**

- each sample has explicit status;
- failed samples never become zero-activity samples;
- consensus denominator is correct;
- sample success threshold is enforced.

---

## Phase 5 — Workflow integration

Add:

```yaml
reduction_strategy: gimme
```

to cell-specific workflow config.

Introduce stages:

```text
compute-reaction-expression
run-gimme
aggregate-gimme-activity
```

Wire consensus output into the existing reduction-plan machinery.

**Acceptance criteria**

- complete end-to-end run from expression file to reduced model;
- all intermediate artifacts are persisted;
- `gpr-threshold` and `activity-matrix` continue to work.

---

## Phase 6 — Biological validation gate

Add:

```text
cell-specific-standard
```

and make task failure affect overall workflow status.

**Acceptance criteria**

- essential task failure => cell-specific validation failure;
- infrastructure error cannot become pass;
- zero-but-optimal objective is rejected where a positive function is required;
- validation reports before/after model metrics.

---

## Phase 7 — Legacy compatibility fixture

Generate and freeze a small Troppo reference case.

Add regression tests.

**Acceptance criteria**

- native solver reproduces the reference GIMME optimum within tolerance;
- documented differences from old THG activity interpretation are intentional;
- Troppo is not needed at runtime or in normal CI.

---

## Phase 8 — Activity matrix + exchange hardening

Implement:

- labeled activity matrices;
- model-signature checks;
- boundary validation for exchange settings.

**Acceptance criteria**

- row-order mismatch cannot silently produce a wrong model;
- internal reactions cannot be modified as exchanges without explicit override.

---

## Phase 9 — Documentation and migration

Update docs and provide migration guidance from legacy THG.

Document mapping:

```text
legacy expressionRxns
    → reaction-expression scores

legacy gimme_parallel.py
    → native run_gimme

legacy allsolutions_gimme_parallel.csv
    → gimme activity/results artifacts

legacy model_reduce.py
    → consensus + reduction stages
```

---

# 22. Suggested first PR

Keep the first PR intentionally narrow.

## Files

```text
src/thg_protocol/cell_specific/gpr.py
src/thg_protocol/cell_specific/gimme.py
tests/unit/test_cell_specific_gpr.py
tests/unit/test_cell_specific_gimme.py
```

Do **not** wire it into the full workflow yet.

The first PR should prove that the scientific core is correct and solver-independent.

### Required tests in PR 1

- GPR AND/OR;
- unknown propagation;
- expression penalty calculation;
- two-pathway GIMME;
- required low-expression pathway;
- reversible reaction;
- GLPK run;
- model not mutated.

Once this core is stable, workflow integration becomes much lower risk.

---

# 23. Suggested second PR

Integrate multi-sample GIMME and consensus.

Files likely affected:

```text
src/thg_protocol/cell_specific/consensus.py
src/thg_protocol/workflow/_scientific.py
src/thg_protocol/workflow/config.py
tests/unit/test_cell_specific_consensus.py
tests/integration/...
```

Add output artifacts and config validation.

---

# 24. Suggested third PR

Implement the cell-specific biological validation gate.

Likely affected:

```text
src/thg_protocol/validation.py
src/thg_protocol/tasks.py
src/thg_protocol/workflow/_scientific.py
docs/workflows/cell-specific.md
```

The overall cell-specific status must depend on required task results.

---

# 25. Scientific decisions that should be documented explicitly

Before declaring the implementation stable, record decisions for:

1. Which expression transformation is expected?
   - raw counts?
   - TPM?
   - log2(TPM+1)?
   - externally normalized values?

2. How is `expression_threshold` selected?

3. How are replicates/samples interpreted?
   - separate GIMME models then consensus;
   - aggregate expression before GIMME;
   - both supported?

4. What fraction of optimal biomass is required?

5. What ATP maintenance constraint is biologically intended?

6. Are unknown/no-GPR reactions always unpenalized?

7. Which Human-GEM metabolic tasks are mandatory for every human cell?

8. Which additional tasks are specific to the modeled cell type?

These are scientific protocol choices, not merely software defaults.

---

# 26. Definition of done

The native GIMME implementation is ready when:

- [ ] Troppo and Cobamp are not runtime dependencies.
- [ ] No code directly depends on `gurobipy`.
- [ ] GLPK can execute the complete GIMME test suite.
- [ ] Gurobi can be used through COBRApy without changing GIMME code.
- [ ] GPR expression mapping is explicit and tested.
- [ ] Missing expression is distinct from zero expression.
- [ ] GIMME objective-retention constraints are mathematically explicit.
- [ ] Per-sample failures are visible and cannot become false inactivity.
- [ ] Reaction activity is not inferred solely from one raw flux vector.
- [ ] Multi-sample consensus is ID-safe.
- [ ] Reduction remains proposal/ledger based.
- [ ] Essential metabolic tasks affect the final validation status.
- [ ] Infrastructure errors cannot silently pass validation.
- [ ] A frozen legacy/Troppo regression fixture exists.
- [ ] Cell-specific workflow documentation explains all three strategies.
- [ ] End-to-end provenance artifacts are produced for a GIMME run.

---

# 27. Recommended scope decision

For THG standalone, the recommended final strategy set is:

```text
gimme
    Primary legacy-compatible cell-specific reconstruction strategy.

gpr-threshold
    Lightweight deterministic baseline / diagnostic strategy.

activity-matrix
    Import path for precomputed reaction-activity results from an
    external reconstruction workflow.
```

The native `gimme` strategy should become the documented route for reproducing the scientific intent of the legacy THG cell-type-specific pipeline.
