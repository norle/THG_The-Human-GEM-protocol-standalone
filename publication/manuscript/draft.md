# A redesigned, reproducible THG model-construction protocol

Internal methods/validation draft. Final-model evaluation is incomplete.
Citations and venue selection are deferred by the publication plan. Quantitative
results enter this draft only after an artifact and regeneration command exist.

## Abstract

We re-implemented the THG reconstruction protocol as an installable Python
package with resumable construction stages, recorded provenance and scientific
gates. The evaluation compares a newly constructed candidate with Human-GEM
2.1.1 with MAR20193 blocked. Construction and evaluation remain in progress;
no final-model improvement or independent reproducibility result is claimed.

## Introduction

Genome-scale metabolic reconstructions connect biochemical knowledge to
constraint-based predictions. Reconstructing a model also depends on choices
about metabolite identity, reaction balance, cellular location and numerical
feasibility. A reproducible implementation must expose these choices and retain
the evidence needed to review them. Here we describe a redesign and
re-implementation of the THG protocol, rather than reproduction of the 2023
publication artifact. Literature citations remain pending.

## Methods and implementation

### Workflow and provenance

The reference workflow curates the input model (beta1), resolves gene and
location evidence and expands compartments (beta2), integrates database evidence
when configured, and performs putative-transport gap filling. Registered stages
write separate attempts and manifests with configuration snapshots, input
references, artifact checksums and service/cache provenance. A forced stage
rerun invalidates downstream results while preserving earlier attempts.

Build configurations are `publication/ws1/reference-a.json` and
`publication/ws1/reference-b.json`. The second run is intended as an independent
replay with frozen service evidence. Replay and output identity have not yet
been established; cached evidence alone does not establish an offline replay.

### Reference intervention and comparison conditions

The benchmark reference is **Human-GEM 2.1.1 with MAR20193 blocked**. The patch
sets both reaction bounds to zero and writes a new model under `runs/`; the
released input remains unchanged. The intervention and its earlier investigation
are documented in `publication/ws0/verifymodel_leaks.md`; regeneration uses
`publication/scripts/patch_human211.py`. Historical task results predate the
numerical diagnostics and require refresh before use as current evidence.

Task settings, input-table hashes and mapping provenance are recorded in
`publication/benchmark_settings.json`. The stored RAVEN tables use the
Human-GEM name mapping. Tasks close existing boundary reactions and introduce
explicit temporary input/output reactions. Forced non-boundary fluxes are
relaxed to include zero before evaluation. Each task runs within a reversible
model context on a solver-specific copy. Unmapped definitions are invalid,
rather than biochemical failures.

### Numerical reliability

The shared task runner records solver status and supported solver tolerances.
For an optimal solve, it obtains unscaled primal values from optlang variables
and constraints before the task context is restored, and measures the maximum
lower- or upper-bound violation separately for variables and constraints.
Violations greater than 1e-7, or unavailable/nonfinite primals, leave the task
unresolved (`error`), with no biological outcome. Residuals for infeasible
solves are null. An expected-infeasible task passes only when the solver reports
infeasibility; an unreliable optimum cannot establish a leak or a pass.

The pinned primary solver is Gurobi, with feasibility, optimality and integrality
tolerances of 1e-7 and two threads. GLPK runs provide corroboration and retain
their own supported tolerances in the reports. They do not replace residual
checks. `publication/scripts/run_tasks.py` writes per-task CSV and detailed JSON,
including model checksum, source commit, working-diff checksum, script checksum,
settings and elapsed time. VerifyModel runs before functional tables; a failed
or unresolved VerifyModel gate prevents their execution in the combined command.

### Identity and chemistry safeguards

Beta1 consolidation requires exact structural identity and matching compartment,
formula and charge. Generic R/X pools are excluded. Differing database identifier
sets in any namespace annotated on both metabolites veto consolidation, even
when the structure annotations agree. An annotation present on only one side is
not a conflict. This safeguard addresses a defect introduced by the redesign;
it is not attributed to the legacy pipeline.

Beta2 does not copy a mass- or charge-unbalanced parent reaction into a new
compartment. Exclusions retain the reason `unbalanced-parent`. This prevents
propagation of inherited chemistry defects; it does not repair the parent or
establish that excluded reactions are biologically unnecessary. Remaining
charge curation is reported separately from construction-gate outcomes.

### Evaluation and stopping rules

VerifyModel must resolve all expected-infeasible tasks before Essential and Full
results on the candidate can be interpreted. A reliably feasible VerifyModel
task stops model-dependent evaluation and release exports for user investigation.
Stage-wise evaluation locates the first affected stage. Numerically unresolved
results remain unresolved rather than triggering an automatic biochemical fix.

Quality evaluation uses the same `final-standard` profile and MEMOTE settings
for the patched baseline and candidate. Required metrics include balance,
stoichiometric consistency, energy cycles, conservation leaks, dead ends,
blocked reactions under open and defined media, network components, annotation
coverage and MEMOTE section scores. Unavailable metrics retain explicit reasons.

Coverage is assessed by evidence source, balance, connectivity and flux
capability under stated conditions. Counts of added reactions alone are not
interpreted as biological improvement. Functional tasks assess preservation of
baseline function. Independent replay compares model checksums, with semantic
differences investigated if serialization differs.

## Results

### Correctness

The archived Human-GEM 2.1.1 build proposed 11 metabolite consolidations.
All 11 pairs have conflicting shared database identifiers and are vetoed by the
current identifier safeguard (`publication/ws2/correctness.json`; regenerate
with `python publication/scripts/measure_correctness.py`). This is a defect
introduced by the redesign. The corrected deduplication attempt completed with
zero metabolite and reaction merges; its output checksum equals the preceding
balanced-model checksum (`publication/ws1/current/stage_table.csv` and
`run_manifest.json`; regenerate with
`python publication/scripts/stage_table.py runs/thg-ws1-a publication/ws1/current`).
This checkpoint does not establish downstream task performance.

The archived expansion plan proposed 26 copies of 14 unbalanced parents; every
copy matches an `unbalanced-parent` exclusion in the revised archived plan.
Eleven parents have charge-only imbalance. These inherited chemistry defects
remain present in the parent model. The safeguard prevents their propagation;
it does not establish a biochemical repair. Individual reactions and imbalance
vectors are saved in `publication/ws2/correctness.json` using the same
regeneration command above. Corrected end-to-end impact remains pending.

The third selected example, numerical task reliability on an unstable real-model
solve, remains pending. Supplementary fix inventory:
`publication/ws2/fixes.csv`; evidence labels distinguish real-model proposal
measurements, sampled narratives, fixture-only checks and pending work.

### Model evaluation

Final candidate, matched quality results and supported coverage analysis are
pending. Earlier baseline results are retained as historical evidence in
`publication/ws0/`; numerical refresh outputs are separate. Intermediate model
artifacts are not called final.

### Reproducibility

Corrected construction and independent replay are pending. No deterministic
end-to-end build claim is made.

## Discussion

The implementation makes identity, chemistry and numerical assumptions
reviewable. Scientific conclusions depend on the gated candidate and matched
evaluation, which remain incomplete. A numerical optimum outside the reliability
threshold does not establish biochemical feasibility. Excluding unbalanced
parents limits propagation but leaves inherited defects for curation. External
service evidence must be frozen before independent replay can be interpreted.

Legacy attribution, additional reference benchmarks, broad ablations, exhaustive
fix-impact measurements and public release are deferred. Gene essentiality is
dropped by user decision.

## Data and code availability

Local regeneration commands and artifact status are maintained in
`publication/README.md`. Public release, tagging and archiving are pending and
require approval. The current draft does not claim to reproduce the 2023 model.
