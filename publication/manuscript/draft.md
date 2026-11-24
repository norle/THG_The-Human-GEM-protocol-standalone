# Updating THG for Human-GEM 2.1.1

## Abstract

- Follow-up to the 2023 THG reconstruction protocol, focused on updating its reference-model branch for Human-GEM 2.1.1.
- Core changes include evidence-based compartment expansion, constrained transport gapfill, stage validation and replay from frozen evidence.
- Main benchmark compares updated THG with Human-GEM 2.1.1 with `MAR20193` blocked. Historical comparison uses the published THG model.
- Rebuilt THG retains the patched baseline's passing task outcomes and adds 2,140 compartment copies and 178 putative transports. The blocked-reaction check classified 9 of 2,140 copies and 53 of 178 putative transports as flux-capable under the model exchange bounds. Matched quality checks show more blocked reactions and dead ends. The standalone MEMOTE scores are pending.

## 1. Introduction

- Original THG curated a Human1 reference in β1, expanded compartment-specific isoenzyme reactions in β2, and merged the expanded reconstruction with a separately built Human Database. [Marin de Mas et al. 2023](https://doi.org/10.3390/bioengineering10050576)
- Ask how much subcellular coverage THG can add to Human-GEM 2.1.1 while preserving measured function, and how much of that coverage can carry flux.
- The benchmark covers reference curation, compartment expansion and transport gapfill. The optional Human Database branch was disabled in builds B and C. [Workflow comparison](../ws3/README.md)

## 2. Methods and implementation

- **β1 curation.** Protect objective reactions during cleanup. Require exact structural identity and compatible shared database identifiers for metabolite consolidation. Preserve protons and water in reaction identity. Limit automated β1 balancing to supported proton/water adjustments.
- **β2 expansion.** Record versions of GO, GOA, UniProt, Rhea and Reactome in the frozen configuration. UniProt acquisition uses human-only queries and all result pages. Resolve GO annotations to the most specific configured targets. Retain multi-location genes, carry confidence rules into GPR selection and exclude mass- or charge-unbalanced parent reactions from copying.
- **Gapfill.** Generate putative transports using source-metabolite identity and configured exclusions. Use directional bounds for type A candidates and exclude sink-only target coverage from MILP credit. Solve to zero relative gap, apply the secondary rank-and-ID objective and remove connectors carrying no flux under the verification conditions. [Gapfill method](../../docs/workflows/gapfill-sink-milp.md)
- **Benchmark and controls.** Block both bounds of `MAR20193` in the patched comparison model. Use the pinned RAVEN mapping, closed medium and two native Gurobi threads. Treat any optimal result with bound or constraint violation above `1e-7` as unresolved. Record invalid mappings separately. [Benchmark settings](../benchmark_settings.json)
- **Replay.** Use the frozen acquisition snapshot, record artifact checksums and stage attempts, and compare resumed B with fresh C. B reused its early stages. [Replay protocol and limits](../ws1/replay-b-vs-c/README.md)
- **Optional capabilities.** Document Human Database merge, curator-approved repairs, pathway workflow, HiGHS and downstream GIMME with their own implementation evidence. [Pipeline inventory](../ws2/fixes.csv)

## 3. Results

### 3.1 Compartment resolution

- Earlier standalone multi-location rejection would leave 1,613 of 2,870 genes with assignments on the previously measured evidence. Keeping multi-location genes leaves 2,461 assigned (+848). Legacy attribution awaits source verification. [Earlier policy measurement](../ws2/gene_locations.json)
- Controlled ablation on frozen B evidence (genes assigned / proposed copies): both older rules 1,620 / 623, retain multi-location genes 2,461 / 2,134, current GO resolver 2,461 / 2,140. The current variant reproduces the B expansion plan byte for byte. [Ablation evidence](../ws2/compartment-resolution/summary.json)
- Worked GO examples for Figure 2. Axonemal microtubule maps to cilium and cytoskeleton. Mitochondrial inner membrane resolves to the inner mitochondrial compartment. [Resolution rules](../../docs/protocol/beta2-compartment-resolution.md)
- HPA agreement for the 945 genes comparable across all three ablation variants: 645 overlap in each variant. Mean Jaccard is 0.5027, 0.5027 and 0.5022, respectively. This compares inferred gene targets. [Ablation agreement](../ws2/compartment-resolution/summary.json)
- Preliminary final-model HPA comparison across all mapped compartments (1,494 comparable genes per model): any overlap 975 → 1,118, mean Jaccard 0.365 → 0.394, exact matches 244 → 229. Agreement describes concordance with mapped HPA evidence. [HPA results and limits](../ws2/hpa/README.md)

### 3.2 Safeguards during expansion

- **Identity.** The shared-identifier safeguard vetoed all 11 archived isomer or generic/specific merge proposals. The consolidation defect was introduced during the redesign. [Archived proposals](../ws2/correctness.json)
- **Chemistry.** The parent-balance safeguard excluded 26 proposed copies of 14 unbalanced parents. Eleven of those parents were charge-only cases. [Archived proposals](../ws2/correctness.json)
- **Numerics.** Archived β1 task 21 returned an optimal point with a `3.03e-7` bound violation. The recheck on unpatched Human-GEM 2.1.1 returned 20 infeasible tasks and an unresolved task 21. The new optimal point had a `5.52e-7` maximum bound violation. [Archived β1](../ws2/historical-failure/task_results_archived-beta1.json) [Unpatched recheck](../ws0/unpatched-recheck/task_results_human211-unpatched.csv)
- **Transport selection.** Gapfill version 7 retained 16 of 152 connectors and added 178 reactions total, compared with 314 in version 6. With coverage, costs and budget fixed, exact solving alone retained the same 162 PTRs. The tie-break exchanged 72 PTRs per selection while covering the same 621 targets. The transport energy-cycle filter was enabled and recorded as skipped because no energy metabolite was identified. [Gapfill comparison](../ws1/gapfill-change/README.md) [Selection ablation](../ws1/gapfill-change/selection_ablation.json) [Run-scope caveat](../../docs/plans/publication-plan.md#gapfill-selection-approved-2026-11-18)

### 3.3 Updated model and benchmark

- **Historical comparator.** The repository THG-2023 SBML file matches supplement S2 byte for byte. Under the current COBRApy loader it contains 20,677 reactions, 14,058 metabolites, 3,394 genes and 9 compartments. The file has 13,840 reaction-linked species, matching the paper’s metabolite count. The paper reported 3,392 genes, two fewer than the 3,394 gene products declared in the file. [Historical evidence](../ws3/README.md)
- **Updated model.** Rebuilt B contains 15,066 reactions, 12,927 metabolites, 2,870 genes and 13 compartments. Patched Human-GEM 2.1.1 contains 12,748 reactions, 8,374 metabolites, 2,870 genes and 9 compartments. The added compartments are cell membrane, cilium, cytoskeleton and vesicle. [Rebuilt B statistics](../ws3/model_stats_rebuilt-b.csv) [Patched baseline statistics](../ws0/model_stats_patched.csv)
- **Coverage and topology.** All 2,140 compartment copies and 178 putative transports are assessable and mass- and charge-balanced. Structural dead-end metabolites increase from 623 to 3,651 against the patched baseline. Under the saved exchange bounds, 9 copies, all 16 retained connectors and 37 of 162 other transports were flux-capable. Gapfill unblocked 47 previously blocked reactions, including five β2 copies. The total blocked count increased from 3,393 before gapfill to 3,471 after adding the transports. [Flux classification](../ws4/coverage-rebuilt-b/flux_coverage.json) [Coverage results](../ws4/coverage-rebuilt-b/coverage.json)
- **Functional tasks.** On both rebuilt B and the patched baseline, VerifyModel 21/21, Essential 57/57 and Full 255 passes with two invalid mappings. Both invalid tasks use 10,13,16-docosatriynoic acid and have no matching model metabolite. [Rebuilt B VerifyModel](../ws1/rebuild-b/gates/task_results_b-rebuilt-final-verify.csv) [Rebuilt B Essential and Full](../ws1/rebuild-b/gates/task_results_b-rebuilt-final.csv) [Patched baseline](../ws0/pinned-refresh/task_results_human211-patched.csv)
- **Consistency and quality.** Rebuilt B's SBML and JSON have identical reaction stoichiometry. Both fail the raw MEMOTE stoichiometric-consistency LP. The unfiltered result differs from curated validation. JSON preserves 64 pseudo-subsystem exclusions missing from the SBML metadata. Native curated checks therefore pass on JSON and fail on SBML. With the same 66 exclusions, including two biomass reactions, both formats pass the curated check. [Raw check](../ws4/consistency/rebuilt-b-raw.json) [Shared-exclusion check](../ws4/consistency/rebuilt-b-exclusions.json)

- **Matched quality.** Both SBML models pass curated stoichiometric consistency with 66 exclusions. Blocked reactions rise from 1,257 to 3,471, dead-end metabolites from 623 to 3,651 and obligatory loops from 2 to 8. Counts of mass- and charge-imbalanced reactions are unchanged under the matched checks. [Quality table](../ws4/matched-refresh/quality_table.csv)
- **Closed-boundary and energy checks.** The metabolite leakage check reports 25 producible metabolites in the baseline and zero in rebuilt B. The energy-cycle check ran on 10 recognised baseline metabolites and was unevaluable in B. Candidate copies share MetaNetX cross-references with existing cytosolic metabolites, so the routine cannot uniquely identify its targets. [Quality evidence](../ws4/matched-refresh/README.md)

### 3.4 Reproducibility

- Resumed B and fresh C produced byte-identical final JSON, SBML and gapfill plans. Seven stage output differences were in fingerprints or run provenance. [Replay evidence](../ws1/replay-b-vs-c/README.md)
- Current-code coverage produced identical records for all 141 components with one and eight workers. The one-worker rerun took 2,093 seconds and the saved eight-worker B run took 722 seconds. Report timings as observations from separate runs. [Serial comparison](../ws1/gapfill-change/serial/comparison.json) [B coverage](../ws1/gapfill-change/README.md)
- Both builds ran on the same machine using the same frozen snapshot. The result verifies computational replay under those conditions.

## 4. Discussion

- The update extends subcellular coverage relative to its patched input while retaining the observed task outcomes. Interpret connectivity and flux capability alongside the increase in coverage.
- Changes in input GEM, Human Database integration, evidence and workflow scope all contribute to the differences between the two THG releases.
- Report numerical uncertainty and model-format metadata explicitly. The task-21 recheck cannot establish a biochemical leak at the agreed residual threshold.
- Attribute causal effects of reconstruction choices only where the comparison holds other inputs fixed.

## Figures and tables

- Figure 1. Current workflow, benchmark scope, stage gates and provenance. [Workflow figure](../figures/figure1_workflow.svg)
- Figure 2. Compartment-rule ablation. Report HPA agreement and worked GO examples alongside the figure. [Figure 2](../figures/figure2_compartment_ablation.svg)
- Figure 3. VerifyModel outcomes at β1, β2 and final, with numerical residuals for unresolved task-21 solves. [Figure 3](../figures/figure3_expansion_safeguards.svg)
- Figure 4. Flux-capable and blocked additions by class. Pair with the matched task and quality table. [Figure 4](../figures/figure4_flux_coverage.svg)
- Table 1. Structural comparison and matched task outcomes, with the historical benchmark fields left blank. [Source CSV](table1.csv)

## Data and code availability

- Record regeneration commands, hashes, solver settings and evidence scope with each result. [Evidence index](../README.md) [Claim audit](evidence-audit.md)
- Archive the release artifacts after the release decision.
