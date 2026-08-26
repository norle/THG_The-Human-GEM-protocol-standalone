# First-Class Scientific Workflow Coverage Plan

**Proposed repository file:** `docs/protocol/first-class-scientific-workflow-coverage-plan.md`

## Goal

Ensure that functionality which materially determines model content is represented as a first-class THG workflow capability rather than existing only as a Python helper, CLI side operation, or partially wired configuration option.

Use one architectural rule:

```text
If an operation changes the scientific model
or determines which biological content is retained,
it requires:
strict configuration
+ explicit inputs
+ DAG stages
+ provenance
+ resumability
+ validation
+ versioned export
```

## 1. Final-THG repair

Final-THG currently stops at merge and validation. Do not add repair stages or
configuration until a real scientific repair strategy exists; then add the
smallest explicit, bounded workflow around that strategy.

## 2. Cell-specific model workflow

Create a new independent:

```text
workflow: "cell-specific"
```

Cell-specific models must not depend on THGβ1, β2, gapfill, or Final THG.

They may consume:

```text
a THG model
Human-GEM
another GEM
an externally supplied COBRA JSON/SBML model
```

The source is simply a versioned input model.

## 3. Cell-specific DAG

Recommended first version:

```text
load-source-model
→ collect-expression-evidence
→ normalize-gene-identifiers
→ map-expression-to-model
→ evaluate-gpr-activity
→ generate-reduction-plan
→ apply-reduction-decisions
→ apply-reduction
→ configure-context-exchanges
→ validate-cell-specific
→ export-cell-specific
```

## 4. Transcriptomics evidence contract

Do not couple the workflow to one particular laboratory expression format.

The normalized internal evidence should contain:

```text
gene identifier
identifier namespace
sample identifier
expression/activity value
units or transformation
source file checksum
mapping status
warnings
```

The initial workflow can require pre-normalized expression data.

Raw-count normalization can be introduced later as an explicit strategy rather than silently assuming TPM, CPM, log transforms, etc.

Configuration should identify:

```text
expression_file
gene_identifier_namespace
sample or sample aggregation
activity strategy
threshold/policy
gene mapping
unknown-gene policy
preserved reactions
task suite
validation profile
```

## 5. Separate transcriptomics from reduction strategy

Transcriptomics is evidence.

Model reduction is an algorithmic decision.

Keep these separate:

```text
expression evidence
→ normalized gene activity
→ GPR interpretation
→ reaction activity
→ reduction strategy
→ model
```

The first maintained strategies can wrap existing functionality:

```text
gpr-threshold
activity-matrix
```

## 6. Unknown genes and uncertainty

Do not silently interpret a missing expression measurement as biological inactivity.

Introduce an explicit policy such as:

```text
uncertain-retain
inactive
reject
```

Recommended default:

```text
uncertain-retain
```

The workflow must distinguish reactions:

```text
removed because evidence indicates inactivity
retained because evidence supports activity
retained because policy preserves it
retained because evidence is unknown
```

## 7. Proposal-first cell-specific reduction

Do not directly delete reactions as the only record of the decision.

Produce a reduction plan:

```json
{
  "reaction_id": "R1",
  "decision": "remove",
  "evidence": {
    "genes": [],
    "activity": {}
  },
  "reason": "inactive-gpr",
  "uncertainty": []
}
```

Then apply the accepted plan to a model copy.

## 8. Cell-specific validation

A reduced model must run the shared validation system.

Report:

```text
source reaction count
retained reaction count
removed reaction count
fraction retained
unknown genes
uncertain reactions
orphan cleanup
blocked reactions before/after
dead ends before/after
network components before/after
metabolic tasks
objective feasibility
context-specific task suite
exchange configuration
```

## 9. Cell-specific lineage

The output must retain:

```text
source model checksum
expression dataset checksum
mapping version
activity/reduction strategy
thresholds
preserve list
exchange settings
task-suite version
software version
```

## 10. Cell-specific export

Recommended artifacts:

```text
cell-specific-model.json
cell-specific-model.xml
expression-evidence.jsonl
gene-mapping.jsonl
reaction-activity.jsonl
reduction-plan.jsonl
reduction-decisions.jsonl
change-ledger.jsonl
uncertainty.tsv
validation-report.json
validation-report.html
model-diff.json
provenance.json
```

## 11. Pathway implementation

`implement_pathway` also materially mutates a model and should ultimately become first-class.

Create a separate:

```text
workflow: "pathway"
```

with approximately:

```text
load-model
→ load-pathway-definition
→ apply-pathway
→ validate-pathway-model
→ export
```

## 12. Human Database live collection

Bring live Human Database harvesting under workflow provenance.

Recommended separation:

```text
collect-records
→ snapshot-records
→ normalize-records
→ reconstruct
→ validate
→ export
```

Network activity occurs only in collection. Snapshot replay performs no network calls.

## 13. Comparison workflow cleanup

Either `compare` becomes a real registered analysis workflow that loads two models and executes maintained semantic comparison, or it should be removed from the workflow registry and remain a cross-workflow analysis tool.

## 14. Capability registry enforcement

Extend the capability registry with a field such as:

```text
scientific_effect:
  none
  analysis
  evidence
  mutation
  selection
```

For every `mutation` or `selection` capability at `release-supported` or `research-supported` tier, require:

```text
workflow coverage
configuration contract
integration test
provenance output
validation output
```

## 15. Priority

Recommended implementation order:

```text
1. Post-β2 gapfill integration
2. Shared validation/reporting
3. Cell-specific/transcriptomics workflow
4. Final-THG repair framework
5. Pathway workflow
6. Human Database live orchestration
7. Compare workflow cleanup
```

## 16. Completion criterion

The package should have a clear distinction between:

```text
library operation
standalone analysis tool
scientific workflow
```

A researcher should never have to infer from documentation whether a model-changing operation was part of a reproducible THG run.
