# Publication plan for the THG protocol update

The manuscript is a follow-up to Marin de Mas et al.'s
[2023 THG publication](https://doi.org/10.3390/bioengineering10050576). It
reports how the original reconstruction workflow has evolved and evaluates the
model produced by the updated workflow. Section 1 defines the paper's scope.

Read first: `docs/about/legacy-comparison.md`,
`docs/contributing/refactoring-changes-2026-10.md`,
`docs/plans/metabolic_task_decisions.md`,
`docs/plans/metabolic_task_leaks_plan.md`,
`docs/protocol/implementation-status.md`.

## Progress (build checkpoint 2026-11-20)

**Current checkpoint (2026-11-23).** See the
[progress handoff](../../publication/HANDOFF-2026-11-23.md) for completed
analyses, measured results, evidence links and remaining work. The bullet
draft, Figures 1–4, Table 1 and matched curated validation are saved. Paired
standalone MEMOTE scores remain open.

This section replaces the 2026-11-09 status. The shutdown handoff
[`publication/HANDOFF-2026-11-09.md`](../../publication/HANDOFF-2026-11-09.md)
and the speedup handoff
[`gapfill-speedup-handoff-2026-11-10.md`](gapfill-speedup-handoff-2026-11-10.md)
are history; where they disagree with this section, this section wins.

**Update (2026-11-20): Gurobi works again** (license renewed; Gurobi 12.0.1
solves in `thg_standalone`). The gapfill change and HiGHS option are committed
(`b731a2b`, configs `1805783`). On Gurobi: 157 gapfill tests pass; the full
offline suite is 2,561 passed with the 2 mkdocs tests passing in the base env;
ruff is clean on `src` and `tests`. B was rebuilt and C built on `1805783`:
both finished 52/52, the final models are byte-identical, and the gapfill
plans are identical (`publication/ws1/replay-b-vs-c/`). Rebuilt B gates
(`publication/ws1/rebuild-b/gates/`): VerifyModel 21/21, Essential 57/57, Full
255 passed / 257 (2 invalid). Gapfill change measurements:
`publication/ws1/gapfill-change/` (plan adds 178 reactions instead of 314; 16
of 152 connectors kept). HPA comparison started:
`publication/ws2/hpa/`. The paper presents the full localisation layer and
includes the HPA comparison.

**Historical stop on 2026-11-20.** The remaining steps at that point were:
step 7 (SBML vs JSON stoichiometric consistency: run
`publication/scripts/check_sbml_json_consistency.py MODEL.json MODEL.xml OUT.json`
on the rebuilt B final model; the first run was stopped before it finished, no
result saved), step 9 (task-21 / `MAR20193` re-check), step 10 (ablation
ladder), step 11 (MEMOTE, `ws4` redo on the rebuilt B), step 13 (figures,
Results). Still open from the gapfill evidence list: effect of each change
alone, whether the tie-break was needed, and the serial benchmark rerun.
Uncommitted: all new `publication/` files and this plan edit.

Practical notes for the next agent:

- Run builds with `publication/ws1/run_build.py CONFIG` from `publication/ws1/`
  (pins Gurobi native settings). Its entry point must stay under
  `if __name__ == "__main__"`: coverage workers re-import the script, and an
  unguarded version re-runs the build in each worker and hangs the stage.
- After killing a build, delete a stale `runs/<name>/run.lock` once you have
  confirmed its PID is gone, before resuming.
- Never `pkill -f` a pattern that also appears in your own command line; it
  kills the shell running the command.
- `runs/` and the downloaded HPA and GO files are local only (not in git).
  Rebuilt B is `runs/thg-ws1-b` (final model
  `artifacts/export-reference/attempt-0002/thg-reference.{json,xml}`); C is
  `runs/thg-ws1-c`. B's earlier v6 gapfill artifacts are archived in
  `publication/ws1/gapfill-change/old-b-v6/`.
- Long stages on a 15,000-reaction model (`characterize-gapfill-baseline`
  ~20 min, `validate-gapfill` ~50 min, `summarize-reference` ~30 min) print
  nothing while running; check CPU, not the log.
- The goal hook was cleared by the user on 2026-11-20.

| WS | Current state |
|---|---|
| WS0 | Matched patched-baseline tasks and curated validation complete. Unpatched task 21 is numerically unresolved. Standalone baseline MEMOTE had started at the checkpoint. |
| WS1 | Build and replay complete. B resumed and C rebuilt from frozen inputs. Final exports and plans match. Selection ablation and serial coverage comparison are saved. |
| WS2 | Archived safeguards, compartment ablation, HPA comparison and fix inventory saved. Current-rule ablation reproduces B's plan. |
| WS3 | S2 model identity, workflow mapping, historical structural counts and S4 task-table checks saved. Full historical attribution is deferred. |
| WS4 | Matched curated validation, format diagnosis and coverage saved. Candidate energy-cycle check is unevaluable. Paired standalone MEMOTE remains pending. |
| WS5 | Task outcomes match for all 335 entries, including two invalid Full mappings on both models. |
| WS6 | Dropped by user decision. |
| WS7 | Bullet draft, Figures 1–4, Table 1 and an evidence audit are saved. Add paired MEMOTE results if available. Public release remains deferred. |

**Historical coverage timing.** The coverage speedup was benchmarked on
run A's model: 536 s with eight workers against about 2.5 h serial, with
identical coverage, targets and `sink_only` sets for components 1–4
(`docs/workflows/gapfill-sink-milp.md`, "Timing of the coverage step"). The
benchmark files were in a session scratchpad and are not saved under
`publication/`; rerun it to keep the evidence.

**WS1 findings from `thg-ws1-a` (resolved 2026-11-09):**

1. **β1 dedup merged isomers.** All 11 metabolite merges on 2.1.1 joined
   different isomers or a generic and a specific form (12-HETE vs 12(S)-HETE,
   9-cis/13-cis retinoyl glucuronide, 8(S)/8(R) hydroxy acids,
   `MAM04041m` trans-5,8- vs `MAM01576m` (5Z,8Z)-tetradecadienoyl-CoA, ...).
   Human-GEM copies one isomer's InChI/MetaNetX/PubChem onto the other; only
   BiGG, VMH, LIPID MAPS, HMDB or ChEBI differ. **Fix (user rule "must match all
   database IDs"):** `consolidate_model` still needs an exact structure, and
   now also vetoes a merge when any namespace annotated on both sides differs
   (a namespace on one side only is not a conflict). On 2.1.1 this leaves 0
   metabolite and 0 reaction merges; VerifyModel on the new dedup output is
   21/21 with Gurobi and GLPK.
2. **"β2 passes 21/21" was a numerical artefact, not a real fix.** β2
   attempt 1 fails task 21, attempt 2 passes, and attempt 2 contains every β1
   reaction unchanged (same stoichiometry and bounds; removing all 2,140 β2
   additions still passes). The β1 "leak" is numerically marginal: Gurobi
   reports optimal with an unscaled bound violation of 3.0e-7 (feasibility
   tolerance 1e-7) on the VLDL/chylomicron exports, through `MAR00012` (48
   coefficients of 0.0001, itself unbalanced: C +16.2, charge −1). GLPK calls
   the same β1 LP infeasible, and Gurobi's verdict flips with how the LP is
   built. So the task-21 result on β1, dedup and β2 depended on solver
   numerics. Follow-up implemented: optimal task solves now report bound and constraint
   violations and flag > 1e-7 as numerically unreliable. Archived beta1 task 21
   reproduces a 3.0276e-7 bound violation and returns unresolved; see
   `publication/ws2/historical-failure/`.
3. **β2 copied unbalanced parents.** **Fix:** `generate_expansion_plan` no
   longer copies a reaction whose parent is mass- or charge-unbalanced
   (`reason: "unbalanced-parent"`); this removed 26 copies of 14 parents in
   attempt 2. User preference: balance the parents instead where possible.
   11 of the 14 are charge-only imbalances (±1/±2, elements balanced:
   `MAR02032`, `MAR03992`, `MAR04549`, `MAR06634`, `MAR06729`, `MAR07025`–
   `MAR07028`, `MAR07741`, `MAR08615`), which proton-water balancing cannot
   fix; they probably need a metabolite charge correction in β1. The other 3
   (`MAR00031`, `MAR07160`, `MAR07625`) are R/X pool reactions and stay
   unbalanced and uncopied.

Charge curation of the 11 inherited parents remains desirable, but is not a
draft prerequisite while unbalanced parents are excluded.

## Build and draft checklist

GLPK corroboration was dropped by user decision (2026-11-10): Gurobi with
residual diagnostics is the only task gate. No target dates are set. Respect
the WS5 stop condition throughout.

The historical workflow comparison in WS3 can start from the 2023 paper and
the current run manifest while validation proceeds. Measure the structural
comparison for Table 1 using the pinned THG-2023 artifact and rebuilt B.

1. **Renew the Gurobi license.** Done on November 20. Paper LP runs use it.
   HiGHS is not a substitute for the paper runs (too slow at this model size,
   and the benchmark settings pin Gurobi).
2. **Finish and commit the gapfill change and the HiGHS option.** The commits
   and test results are recorded above. The serial coverage benchmark is saved
   under `publication/ws1/gapfill-change/serial/`.
3. **Rebuild B and build C on that commit.** Done. Commit and working-tree
   records are in `publication/ws1/rebuild-b/` and `publication/ws1/build-c/`.
   The latter used `publication/ws1/reference-c-frozen.json`. For paper reruns,
   pin Gurobi so a missing license fails the run before it switches solver.
4. **Gate the rebuilt B.** The final VerifyModel, Essential and Full results
   are saved. Use the recorded stage checks in Figure 3.
5. **Measure the gapfill change** for Methods. Connector removal, selection
   under versions 6 and 7, and B/C plan identity are recorded. The
   fixed-coverage ablation isolates the exact gap and the tie-break.
6. **Compare B and C.** Checksums and semantic comparison are saved. Use
   these and the stage data in Results 3.4.
7. **Explain the SBML/JSON stoichiometric-consistency discrepancy.** Complete.
   Applying the same 66 exclusions gives a passing curated check on both
   exports. Raw checks without curated exclusions fail on both.
8. **Two-tier export: decided (2026-11-20)** — present the full localisation
   layer; classify and report flux-capable vs blocked additions only (section 6,
   item 9).
9. **Re-check unpatched 2.1.1 task 21.** Complete. The solver returned an
   optimal point with a bound violation above the reliability threshold.
   The task remains unresolved.
10. **Compartment-resolution ablation ladder** (Results 3.1). Complete.
11. **MEMOTE and `final-standard` validation** on the patched baseline and the
    rebuilt B, sequentially; check `free -m` first. The structural and
    construction-bound flux-capability analyses for rebuilt B are saved.
    The matched final-standard table is saved. Paired standalone MEMOTE scores
    remain open.
12. **HPA comparison.** Final-model and ablation results are saved with their
    separate denominators and outcome definitions.
13. **Figures 2–4, Table 1, Results, Discussion, evidence audit.** Draft figures,
    the structural and task table and the requested bullet-point manuscript
    are saved. Incorporate matched quality results and finish the audit.

## Gapfill selection (approved 2026-11-18)

Describe the transport safeguards that precede the version-7 changes
(`db45570`). Candidate pairing uses source-metabolite identity and excludes
configured energy and redox cofactors and protons. Type A transports run
from product-only to substrate-only dead ends. Ambiguous pairs remain
reversible. Coverage and application use the same transport bounds. The
selection supports compartment-pair costs and a MEMOTE energy-cycle filter.
Rebuilt B used the default costs. Its plan enabled the filter but records
`skipped` because no energy metabolite could be identified. Report that
outcome separately from final-model validation. See
`runs/thg-ws1-b/artifacts/generate-gapfill-plan/attempt-0002/gapfill-report.json`
and the [gapfill method notes](../workflows/gapfill-sink-milp.md).

The user approved the changes to the sink-MILP selection in
`generate-gapfill-plan` (stage version 6 → 7). They change the model, so the
paper must describe them in Methods (section 2) and the numbers below must be
measured on the rebuilt B. The reference description is
`docs/workflows/gapfill-sink-milp.md`, stage 4 and "Verification".

What changed:

1. **Exact MILP.** Gurobi's default relative gap (1e-4) can exceed
   `tradeoff_lambda` (0.01 per PTR) when hundreds of targets are in the
   objective, so a near-optimal solution can keep PTRs the true optimum would
   not. The MILP is now solved with `MIPGap = 0`.
2. **Deterministic tie-break.** Different selections often cover the same
   targets at the same cost (two transports that unblock the same reactions),
   and the solver's choice between them is arbitrary. A second solve fixes
   coverage and cost at the optimum and minimises the summed preference
   position of the chosen PTRs: type A before B before C, then reaction ID.
   The same inputs therefore give the same plan. An exact tie in that sum is
   possible in principle and is not detected.
3. **Inactive connectors are dropped.** Connectors (the minimum-spanning-tree
   PTRs that join network components) are still added before coverage and
   selection. After selection, the model without temporary sinks is checked;
   a connector that carries no flux is removed, and the check repeats until
   every remaining connector carries flux. Removed connectors are listed in
   `verification["inactive_connectors"]` with status `connector-inactive`.
   The plan status stays `solved`. On run A's model, 1 of 152 connectors
   carried flux without sinks, so most connectors are expected to go.
   Removing the connector stage altogether, or choosing connectors by flux, is
   deferred to the method discussion.

The coverage speedup (cached solver variables, a sum-LP pre-check, one test
per cross-component candidate, a process pool set by `coverage_workers`) does
not change results and belongs in Methods only as runtime.

Methods should also name the solver and say that the protocol supports HiGHS
as an open-source alternative (`gapfill.solver`), with the measured per-LP
cost on the β2 model, and that all reported runs used Gurobi.

Evidence to save under `publication/ws1/gapfill-change/`, each with its
command:

- connectors proposed, kept and dropped on the rebuilt B;
- PTRs selected under version 6 (old B) and version 7 (rebuilt B), and how
  many reactions differ, separating the effect of the dropped connectors from
  the exact gap and tie-break where possible;
- whether the tie-break was needed: number of alternative optima the second
  solve chose between, or at least whether its selection differs from the
  first solve's;
- B vs C gapfill plans identical (determinism);
- coverage-step runtime and equality with the serial code (rerun of the
  benchmark).


## Compartment resolution and validation

**Compartment resolution is a Results section.** It is the step that produces
the localised reactions THG adds. Show two rule changes, selected because they
change the final model:

1. *Genes with several compartments are kept* (`0188ac5`). Previously a gene
   with more than one location contributed none. Measured: 848 of 2,870 genes
   rescued (`publication/ws2/gene_locations.json`).
2. *One GO term can map to several compartments* (`4e88dea`). Previously the
   resolver picked the compartment the fewest GO steps away (93 terms narrowed,
   8 ties dropped; narrative counts, no saved measurement). Now every
   configured compartment reached through the GO hierarchy is kept, except one
   that contains another reached one. Examples: axonemal microtubule → cilium
   and cytoskeleton; mitochondrial inner membrane → `i` only.

The UniProt query fix (R1) and the "Cytoplasm" alias (R8) are **not** shown in
Results; they stay in the supplementary fix inventory.

Required analysis: an ablation ladder on the frozen evidence snapshot
(`publication/ws1/frozen/`), β2 planning stages only. Start from the old rules
and switch on one change at a time. At each step record genes localised and
reaction copies generated per compartment. Save results and the regeneration
command under `publication/ws2/compartment-resolution/`.

Wording constraint: the existing measurement for change 1 is an ablation of an
earlier *standalone* rule; legacy attribution is not established. Before the
text says "the 2023 protocol did X", confirm each old behaviour in the legacy
checkout (`../THG_The-Human-GEM-protocol`). Otherwise write "an earlier rule".

**Revised Results structure:** 3.1 compartment resolution, 3.2 safe
expansion, 3.3 THG vs Human-GEM 2.1.1, 3.4 reproducibility. The full table and
figure list are in section 2.

Defects found in Human-GEM 2.1.1, to consolidate for 3.3: the task-21 route
through `MAR20193` on the unpatched release (re-check with residual
diagnostics before claiming it), isomer pairs sharing copied structure
annotations (WS1 finding 1), and the 11 charge-only unbalanced reactions (WS1
finding 3).

The paper presents the full localisation layer and reports flux-capable and
blocked additions. Include Human Protein Atlas agreement in the ablation
ladder (section 6, items 9 and 10).

Remaining work is listed in the build and draft checklist above.

## Draft scope and rules (agreed November 9, 2026)

The first deliverable is a methods-led internal draft of the THG update with
traceable results. The November 9 schedule below is historical. Follow
the build and draft checklist for the current sequence.

| Day | Priority | Deliverable |
|---|---|---|
| Nov 9 | Numerical diagnostics; freeze settings; restart corrected WS1; begin Methods | Reliable task verdicts, pinned inputs/config/code/solver settings, build status, Methods text |
| Nov 10 | Finish build and stage/final gates; validate patched baseline and THG | Candidate model, stage table, comparable quality results, or documented blocker |
| Nov 11 | Independent replay; three correctness examples; coverage analysis | Reproducibility comparison, source tables and three figures |
| Nov 12 | Assemble manuscript and audit claims against evidence | Complete internal draft with evidence links and explicit unresolved results |

**Numerical prerequisite:** record maximum bound and constraint violations for
every optimal task solve, with solver status and tolerances. Flag violations
above 1e-7 as numerically unreliable, not as a pass or a confirmed leak.
Record infeasible and unresolved statuses separately; do not substitute zero
residuals for an unavailable solution. Cross-solver agreement corroborates the
result but does not replace these checks. Refresh affected baseline results
under the same harness/settings used for THG.

**Day-2 decision point:** if the final candidate is still blocked or fails its
gates, continue a methods/validation draft using verified baseline and
correctness results. Label final-model evaluation incomplete. Preserve the
WS5 leak investigation stop condition; do not call an intermediate model final.
Writing Methods and independent WS2 results can continue during that stop.

Required for the model-results draft: one gated candidate, the THG-2023 lineage
comparison, the patched baseline, matched quality and task measurements,
supported coverage analysis, independent replay, and three measured
correctness examples. Candidate examples are
consolidation safeguards, numerical task reliability, and exclusion of
unbalanced parents. Distinguish inherited defects from redesign-introduced
bugs, and numerical artifacts from biochemical leaks. Every count needs a
saved result and regeneration command; existing narrative counts are leads.

The baseline already passes all valid Essential/Full tasks. Use those tasks
to test preservation of function, not improved pass rates. Assess added
coverage through evidence source, balance, connectivity and flux capability
under stated conditions; reaction counts alone do not establish biological
improvement. Report Full as 255 pass / 257 total, with 2 invalid, until rerun.

Defer the full WS3 attribution experiment, additional benchmarks, broad
ablations, exhaustive full-model audit-fix measurements and public release.
WS6 remains dropped. Keep all other fixes in a supplement labelled by evidence
strength. Run memory-heavy validation jobs sequentially. Record missing or
unfinished metrics honestly; do not silently relax scientific gates to meet
the date. Venue selection and release publication do not block an internal draft.

Results so far: `publication/ws0/` (task results, `verifymodel_leaks.md`), `publication/ws1/` (stage VerifyModel, dedup bisect, run configs), `publication/benchmark_settings.json`.
Machine memory was exhausted on 2026-11-04; check `free -m` before MEMOTE runs (2026-11-09: ~11 GB available).

Environment: conda env `thg_standalone` (has Gurobi). Use memote and
optlang/Gurobi for model-scale LPs. mkdocs and ruff live only in the base env.

---

## 1. Framing of the paper

**Working title** — Updating THG for Human-GEM 2.1.1.

Open with the scientific aim of the
[2023 THG protocol](https://doi.org/10.3390/bioengineering10050576). It used
β1 to curate the reference reconstruction and β2 to expand it with
compartment-specific isoenzyme reactions, then merged the expanded reference
with a separately reconstructed Human Database. The update revisits the
reference-model branch on Human-GEM 2.1.1 and evaluates revised localisation,
transport gap filling, stage-wise validation and replay from frozen evidence.
The B/C benchmark ran with Human Database reconstruction and integration
disabled. State this scope difference when describing the build and
interpreting model sizes. See `publication/ws1/build-c/build.log`.

**THG-2023 answers what changed since the original publication.** Map the
original stages to the stages actually run, then compare the published model
and rebuilt B descriptively. Changes in reference model, data sources,
database integration and methods all contribute to differences between the
artifacts. Attribute effects to individual rules only with controlled evidence.

**Patched Human-GEM 2.1.1 answers what the update adds to its input.** Use
matched quality and task checks against Human-GEM 2.1.1 with `MAR20193`
blocked. Ask how much supported compartment coverage THG adds, how much is
flux-capable, and which functions and quality metrics it preserves. Describe
the intervention and the unpatched reference in Methods.

Use independent replay to support reproducibility of the current build from
frozen inputs. Exact reproduction of the original artifact remains unverified.

Candidate venues: *Bioinformatics* (Application Note) or *PLOS Comput Biol*
(Software) for a methods-led paper. *NAR Genomics & Bioinformatics* or
*Metabolic Engineering* are realistic if the functional results (WS5) are
strong.

## 2. Proposed manuscript structure

Updated 2026-11-23 for the follow-up to the 2023 publication.

| Section | Content | Evidence from |
|---|---|---|
| Abstract | Identify the 2023 protocol, summarise the update and report verified findings from the matched benchmark and replay | WS1, WS2, WS3, WS4, WS5 |
| 1. Introduction | Explain what the 2023 paper introduced, why update it for Human-GEM 2.1.1, and why localisation evidence, conservation and reproducibility matter | 2023 paper, WS3 |
| 2. Methods / Implementation | Map the original workflow to the current build. Cover the pipeline changes listed below and identify which methods were used in B/C | WS0, WS1, WS2, WS3, WS7 |
| 3.1 Results: compartment resolution | Two rule changes (multi-compartment genes; one GO term to several compartments), ablation ladder, worked GO examples | WS2 (`compartment-resolution/`) |
| 3.2 Results: safe expansion | Stage gates, leak mechanisms with origin of defects stated, 0 of 21 VerifyModel tasks feasible at every stage | WS1, WS2 |
| 3.3 Results: the updated THG model | Lead with the structural comparison to THG-2023. Then report coverage, quality, task preservation and verified baseline defects against patched Human-GEM 2.1.1 | WS3, WS4, WS5 |
| 3.4 Results: reproducibility | Independent replay and stage sizes/runtime | WS1 |
| 4. Discussion | What the update preserves and changes, connectivity of additions, and limitations from differences in reference, database integration, evidence and methods | all active WS |
| Data and code availability | Local artifacts and regeneration commands; public release pending | WS7 |
| Supplementary | Full fix inventory with evidence strength, per-task results, manifests and validation detail | active WS |

### Pipeline changes to document

| Area | Changes to account for | Where to report |
|---|---|---|
| β1 curation | Protect objective reactions in duplicate removal, require compatible identifiers and exact chemistry, and retain protons and water in reaction identity. Distinguish automatic proton/water balancing in β1 from the separate MILP balance-suggestion tools | Methods, safeguard examples in Results 3.2, fix inventory |
| β2 evidence and expansion | Versioned location and reaction evidence (GOA, UniProt, Rhea and Reactome in B/C), human-only paginated UniProt queries, exact Cytoplasm alias, multi-location genes, multi-target GO mapping, confidence rules for structured GPRs, source identity and bounds in duplicate checks, rejection of empty evidence and exclusion of unbalanced parent reactions | Methods, measured localisation and chemistry findings in Results 3.1–3.2, fix inventory |
| Transport gapfill | Resumable sink-MILP, source-identity pairing, directional bounds and exclusions, sink-only controls, energy-cycle filter, exact MILP, tie-break, inactive connector removal, coverage acceleration, and the HiGHS option | Methods, measured plan changes and replay, fix inventory |
| Validation and curation | Release profiles and stage gates, direction-aware consistency checks, mass and charge balance, closed-boundary leakage and energy-cycle checks, obligatory-loop detection, RAVEN task semantics and numerical residuals, and reviewable repair proposals with approved fixes and ledgers | Methods and Results 3.2–3.3 for benchmark checks, supplement for optional repair workflows |
| Execution and provenance | Installable CLI, resumable stages with dependency-based invalidation, stable β1-to-β2 fingerprints, frozen evidence and release-aware caching, manifests, checksums, and export and replay checks | Methods, Results 3.4, engineering evidence |
| Optional and downstream workflows | Normalized Human Database reconstruction, annotation- and chemistry-aware integration, pathway additions, and native GIMME with versioned expression evidence. Identify their scope in the workflow mapping and cite implementation evidence for capabilities outside B/C | WS3 workflow mapping and supplement |

Use the [refactoring change report](../contributing/refactoring-changes-2026-10.md),
the [function audit](../../reviews/2026-11-03-function-audit/README.md), the
[capability registry](../protocol/implementation-status.md) and subsequent
pipeline commits to reconcile the supplement with the build commit. For each
substantive change record its source, whether B/C exercised it, and whether its
evidence is a model measurement, a fixture check or an implementation record.
Confirm legacy attribution before calling a change a correction to the 2023
protocol. Carry forward optional capabilities and fixes with their evidence
limits. Reserve quantitative claims for measurements with saved artifacts.

### Planned figures and tables for the first draft

| ID | Content | Produced by |
|---|---|---|
| Fig 1 | Current protocol stages, gates and provenance, with a caption relating them to the 2023 workflow and identifying the unused Human Database branch | WS1, WS3 |
| Fig 2 | Compartment resolution: GO-hierarchy mapping examples and ablation ladder (genes localised, reaction copies per compartment) | WS2 |
| Fig 3 | Safe expansion: VerifyModel per stage and the measured rationale for the identity, chemistry and numerical safeguards | WS1, WS2 |
| Fig 4 | Human-GEM 2.1.1 vs. THG: quality, supported coverage, task preservation | WS4, WS5 |
| Table 1 | Structural statistics for THG-2023, current THG and patched Human-GEM 2.1.1. Label the historical row and identify which quality and task metrics were run under matched conditions. Include invalid and unresolved counts for those runs | WS0, WS3, WS4, WS5 |
| Table S* | Original-to-current workflow mapping, fix inventory, per-task results, stage and replay evidence, and validation details | active WS |

Legacy-overlap figures and essentiality panels are not draft deliverables.

## 3. Models in scope

Pin every model actually used by path and SHA-256 in `publication/models.json`
(WS1). For the first draft, use THG-2023 for lineage and patched 2.1.1 for
matched benchmarking against current THG. Retain unpatched 2.1.1 and Human1
control provenance where used.

| Label | File | Role |
|---|---|---|
| Human1 (2022-06-21) | `models/Human-GEM_2022-06-21.xml` | Legacy reference and input of the 2023 pipeline |
| Human Database (2023-02-25) | `models/Human Database.xml` | Legacy Human Database used to build THG-2023 |
| Human2 (benchmark) | `runs/human211-patched/Human_211_patched.xml` | Current reference: Human-GEM 2.1.1 (`inputs/models/Human_211.xml`, SHA-256 `dc0efd80…5ddf`) with reaction `MAR20193` blocked (bounds 0,0). Made by `publication/scripts/patch_human211.py`; SHA-256 `04cb9de9…3f38`. Decided 2026-11-05. Name it "Human-GEM 2.1.1 with MAR20193 blocked" in the paper |
| Human2 unpatched | `inputs/models/Human_211.xml` | 2.1.1 as released. Earlier task-21 failure needs rechecking with residual diagnostics |
| Human2.0 (extra) | `inputs/models/Human2.xml` | Believed 2.0 (user, unverified). 21 of 21 VerifyModel. Optional comparison row |
| THG-2023 (legacy final) | `models/THG-2023-02-25.xml` | Historical comparator for the update. Check against the publication supplement in WS3 |
| THG-β1 / β2 (legacy) | `models/THG-beta1.xml`, `models/THG-beta2.xml` | Legacy intermediates |
| THG current (β2, gapfilled, final) | `runs/thg-ws1-b/artifacts/export-reference/attempt-0002/thg-reference.{json,xml}` | Rebuilt B, the model being presented |

Provenance of the legacy inputs (checked 2026-11-04): `Human-GEM_2022-06-21.xml`,
`Human Database.xml` and `THG-2023-02-25.xml` in `models/` are byte-identical to
the copies committed in the legacy repository in February–March 2023 (commits
`fad16c2`, `3ee4f60`, `5ff6f1d`, `bbcae83` in `../THG_The-Human-GEM-protocol`),
so they are the files the 2023 pipeline used. Record this in
`publication/models.json`.

Out of scope: Human-GEM 1.19 and the 2025 legacy intermediates built on it
(`THG-beta-batch_251106*`, endo models). They are not part of the published
lineage and are not compared.

**Comparison context.** The original THG integrated the 2023 Human Database
with a Human1-derived model. The benchmarked update starts from patched
Human-GEM 2.1.1 and leaves Human Database integration disabled. A direct
comparison measures the combined differences in inputs, workflow scope and
methods. Record these when interpreting the historical comparison in WS3.

### Known issue: β1 metabolite consolidation (fixed 2026-11-04)

Check this first if a THG model fails VerifyModel again.

- **Symptom.** The gapfilled candidate in `runs/thg-reference` (2026-09-11)
  had VerifyModel tasks 10, 11, 17 and 21 feasible (NADH from O2 in cytosol and
  mitochondria, > 40 ATP per glucose, ATP from Pi and O2). Human2 itself passes
  21 of 21.
- **Cause.** `consolidate_model` (`src/thg_protocol/curation/beta1.py`, stage
  `deduplicate-and-clean`) merged metabolites that shared compartment,
  formula, charge and the first of ChEBI/KEGG/PubChem. Human-GEM's
  tissue-specific lipid pools share generic ChEBI classes (for example
  `CHEBI:35366` for "fatty acid pool", "fatty acid-LD-PC pool" and "fatty
  acid-LD-PE pool"), so 61 pools were merged. Each pool has its own
  composition reaction with slightly different coefficients. After the
  merge, flux enters the pool through one composition and leaves through
  another, which makes fatty acids from nothing; beta-oxidation turns them into
  NADH and ATP. The other 16 merges joined stereoisomers and positional
  isomers ((2S)/(2R)-pristanic acid, (3S)/(3R)-phytanic acid, 26-/27-tetrols).
  Every leak route used only Human2 reactions; gapfill added none of them.
- **Fix.** Generic (R/X-group) metabolites are never merged. Only exact
  structure (InChIKey, InChI, SMILES) establishes identity; ChEBI, KEGG,
  PubChem and MetaNetX alone do not (identical MetaNetX sets still joined
  isomers on Human2). A differing MetaNetX set vetoes a structural match. On
  Human2 the stage now merges 0 metabolites and VerifyModel stays 21 of 21.
- **Regression test.** `tests/integration/test_beta1_consolidation_verifymodel.py`
  (slow, needs `inputs/models/Human2.xml`), plus unit tests in
  `tests/unit/test_beta1_curation.py`.
- **How to check during runs.** After `deduplicate-and-clean`, read
  `artifacts/deduplicate-and-clean/attempt-*/cleanup.json`:
  `retained_metabolites` should be empty or only exact-structure duplicates,
  and no merged metabolite should have an R in its formula. If a VerifyModel
  task becomes feasible later, run VerifyModel on each stage model in order
  (input, `apply-balance-proposals`, `deduplicate-and-clean`, `export-beta1`,
  `export-beta2`, gapfill) to find the first stage that leaks, and look for
  Human2 reactions whose stoichiometry changed rather than only new reactions.

---

## 4. Workstreams

Each workstream writes to `publication/<ws-id>/` (create the directory). Each
produces machine-readable results (CSV/JSON), a short `README.md` saying what
was run, with which commit, config and solver, and any figure source data.
Figures are generated by scripts in `publication/scripts/`, never by hand.

### WS0: Human2 baseline (start here)

Goal: run the full benchmark harness on Human2 before any THG model is
involved. Human2 is the input to the current pipeline and the main comparison
model. Its results show the harness works, and they become the reference values
for WS4 and WS5.

1. **Identify Human2.** *Done: Human-GEM 2.1.1 (user), patched; see section 3. `Human2.xml` is believed to be 2.0, unverified.* Record the exact version, source (repository, tag or
   commit, download date) and SHA-256 of `inputs/models/Human2.xml`, and how it
   should be cited. If this cannot be determined from the repo, ask the user.
   Write it into `publication/models.json`.
2. **Load and basic statistics.** Load with cobrapy. Record reactions,
   metabolites, genes, compartments, subsystems, exchange reactions and
   annotation coverage. Note any SBML warnings.
3. **Validation.** Run `thg-run validate` with profile `final-standard` and
   `run_memote: true` (`runs/human2-validation` ran without MEMOTE). Record
   mass/charge balance, stoichiometric consistency, energy-generating cycles,
   conservation leaks, dead-ends and blocked reactions (FVA on open and defined
   medium), and the MEMOTE total and section scores.
4. **VerifyModel.** Run the 21 VerifyModel tasks with the stored tables and
   mapping, closed medium, biomass LB relaxed.
   - **Positive control first:** run them on Human1 (2022-06-21). It is known
     to get 21 of 21 infeasible (`metabolic_task_decisions.md`). If the harness
     does not reproduce that, the harness is wrong: stop and report.
   - Then run them on Human2. The 21/21 result is known only for Human1, so
     Human2 is the first real test. Also record how many tasks are
     "invalid" (did not map to Human2 IDs); an invalid task is not an
     infeasible one and does not count towards 21 of 21.

   > *Triggered 2026-11-04 on unpatched 2.1.1 (task 21, via `MAR00012` and `MAR20193`); the user authorised a fix, the patched model passes. See `publication/ws0/verifymodel_leaks.md`.*
   >
   > **STOP CONDITION.** If any VerifyModel task is feasible on Human2, stop
   > and report to the user. On Human2 this most likely means a harness problem
   > (task-to-model ID mapping, medium, bounds) rather than a real leak, and
   > every later task result would be unreliable. Write the same
   > `verifymodel_leaks.md` report described in WS5 under `publication/ws0/`
   > and wait for the user.

5. **Essential and Full tasks.** Run them on Human2 with the same settings. Record
   each task's result. Note any task whose metabolites or reactions are not
   mapped to Human2 IDs ("invalid"), and why.
6. **Gene-essentiality dry run: dropped.** No DepMap work is required.
7. **Fix the settings.** Write `publication/benchmark_settings.json` with the
   solver, tolerances, medium, bounds, task tables (and commit), mapping file,
   explicit numerical tolerances and residual reliability threshold. Every later workstream uses exactly these
   settings for every model.

Output: `publication/ws0/` with `model_stats.csv` (one row, same columns as
WS4), the validation report and MEMOTE output, `task_results.csv` (same format
as WS5), and a `README.md` with commands,
commit and runtime. Plus `publication/benchmark_settings.json`.
Done when: Human2 has 21 of 21 VerifyModel tasks infeasible, all metrics above
are recorded or explicitly marked missing. Report the summary. Pending MEMOTE
does not prevent the corrected WS1 build; reliable task evaluation is required.

### WS1: Frozen, reproducible build of the current THG model

Goal: one pinned, end-to-end build that every other workstream uses.

1. Confirm `configs/reference.json` runs end to end
   on the current `main` head with `thg-run`. Record any failing stage. Do not
   paper over failures: fix them or record them as limitations.
2. Freeze inputs: copy or pin external service caches so the run can be
   replayed offline. Record service versions and cache checksums from the run
   ledger.
3. Write `publication/models.json` (label, path, SHA-256, provenance) for all
   models in section 3.
4. Re-run the build once from scratch and check the exported model has the same
   checksum (determinism). If it does not, find and document the
   nondeterminism. Both builds must run on the same committed source with a
   clean tree, and the commit must be saved next to each run.
5. Export a stage table: per stage, its input/output sizes (reactions,
   metabolites, genes) and runtime. This feeds Fig 1 and Methods.

6. Check the β1 consolidation (see "Known issue: β1 metabolite
   consolidation" above): `cleanup.json` from `deduplicate-and-clean` has no
   merged R-group pools, and VerifyModel on `export-beta1` is 21 of 21
   infeasible. Record both in the stage table.

Output: `publication/ws1/` with the run manifest, stage table and
determinism check.
Done when: two independent runs give identical model checksums, or the
difference is explained and bounded.

### WS2. Pipeline changes and supporting evidence

Goal: document the substantive pipeline changes and measure the examples that
support the paper's scientific claims.

1. Reconcile `publication/ws2/fixes.csv` with the pipeline changes listed in
   section 2. Include later changes to transport safeguards, solver selection,
   coverage and resume behavior alongside the October report and November
   audit. Label the β1 consolidation defect as introduced by the redesign.
2. Use real-model measurements for the selected examples and report the other
   changes with the strongest available evidence. The existing localisation
   result measures an earlier standalone rule. Match the input and use a
   controlled comparison for claims about the effect of changing a rule.
3. Where possible, run the legacy function (adjacent checkout
   `../THG_The-Human-GEM-protocol`) and the standalone function on the same
   input. Use a separate legacy environment; do not import legacy code into the
   package.
4. Record test counts, CI configuration and measured runtimes in the
   engineering supplement. Table 1 reports model statistics and benchmark
   outcomes.

Output: `publication/ws2/fixes.csv` (fix id, description, metric, legacy value,
standalone value, affected entities, evidence path), `publication/ws2/engineering.csv`.
Draft done when three selected examples have measured real-model impact and
regeneration commands, and the supplement accounts for the substantive
changes through the benchmark commit with their evidence and run scope.
Exhaustive benchmarking of every fix is deferred.

### WS3. From the 2023 THG publication to the current model

For the first draft:

1. Map the original β1 curation, β2 expansion, Human Database reconstruction
   and merge, and model assessment to the current stages. For each row, cite
   the 2023 paper and the current manifest or implementation. Record what the
   B/C builds executed, including skipped stages. Verify any specific claim
   about a 2023 implementation rule against the legacy source.
2. Check the pinned THG-2023 SBML file against the published supplement (S2)
   and record the identity check or any unresolved discrepancy. Use
   `publication/scripts/model_stats.py` on the verified historical artifact
   and the current B SBML export with the same loader and record reactions,
   metabolites, genes, compartments and warning counts. Report
   structural differences as descriptive results in Table 1 and Results 3.3.
   Cite published metrics with their original methods if used for context.

Save the workflow mapping, structural statistics and regeneration commands in
`publication/ws3/`. The draft comparison is complete when the two artifacts are
identified and every reported statistic has a source. Keep the matched
quality and task benchmark in WS4 and WS5 focused on the patched baseline
and current THG.

#### Full historical attribution (deferred beyond the first draft)

The controlled runs below would evaluate effects of changing the reference,
database inputs and implementation. They would require database-enabled builds.

1. Compare THG-2023, legacy β1/β2 and current β1/β2/final using
   `thg-compare` (`src/thg_protocol/analysis/compare.py`). Match reactions and
   metabolites by annotation (MetaNetX, KEGG, ChEBI, InChIKey) and
   stoichiometry, not only by ID.
2. **Attribution.** Run the current pipeline with the same inputs the 2023
   pipeline used: Human1 (2022-06-21) as the β1 input and the frozen
   `models/Human Database.xml` (2023-02-25) as the Human Database, instead of
   rebuilding the database from today's services. The `reference` workflow
   always rebuilds the Human Database from records and has no option for a
   prebuilt database model. Two routes:
   - preferred: add a `database_model` option to the `reference` workflow (the
     `final-thg` workflow already accepts `final_thg.database_model`), with a
     test; or
   - chain `beta1` → `beta2` → `final-thg` (with `database_model` set) →
     `gapfill`, after checking that `final-thg`'s merge gives the same result
     as the `reference` workflow's `integrate-human-database` stage on the
     same inputs. If it does not, use the preferred route.

   Call this run current(Human1, DB-2023). Then:
   - THG-2023 vs. current(Human1, DB-2023) = effect of code and method changes
     to the extent other stage inputs and settings match;
   - current(Human1, DB-2023) vs. current(Human1, DB-new) = effect of rebuilding
     the Human Database with current service releases;
   - current(Human1, DB-new) vs. current(Human2, DB-new) = effect of the
     reference update.
   Report all three, as a waterfall of reaction/metabolite counts.
3. Break down the code-change effect by component where feasible: merge
   (annotation-aware vs. name-based), gapfill (`sink-milp`), balancing, and
   localisation fixes. If a component can be toggled through config, ablate it;
   otherwise describe it qualitatively.
4. Characterise the reactions unique to each side: by subsystem, by
   compartment, by evidence source, and how many are balanced, blocked or
   gapfill-added.
5. Run the side-by-side merge comparison flagged as missing in
   `legacy-comparison.md` (legacy `network_reactions_merge_*` vs.
   `generate_merge_plan`) on the same β2 + Human Database input.

Deferred output: `publication/ws3/` with overlap tables, the attribution table, the
unique-reaction characterisation and the merge comparison.
Done when: the attribution accounts for the full count difference (with a
residual if needed) and every large unique set is characterised.

### WS4: Structure and quality vs. Human1/Human2

Goal: a fair, same-pipeline comparison. Reuse the Human2 row from WS0 if the
code commit and `benchmark_settings.json` are unchanged; otherwise rerun it.

Run `thg-run validate` with the same profile (`final-standard`) and
`run_memote: true` on the patched baseline and current THG. Other section-3
models are deferred. `runs/human2-validation` is a
starting point but ran without MEMOTE.

Collect per model:

- counts: reactions, metabolites, genes, compartments, subsystems;
- new coverage in THG: compartments absent from Human-GEM (glycocalyx,
  cytoskeleton, others in `supplementary_material/ListOfCompartments_sept2024.xlsx`),
  reactions and genes absent from Human2;
- network: dead-end metabolites, blocked reactions (FVA, open and defined
  medium), disconnected components;
- quality: mass and charge balance, stoichiometric consistency, energy-generating
  cycles, conservation leaks (`analysis/conservation.py`, `analysis/leakage.py`);
- MEMOTE total and section scores;
- annotation coverage (fraction of metabolites/reactions/genes with
  cross-references).

Output: `publication/ws4/model_stats.csv` (one row per model), per-model
validation reports, MEMOTE HTML/JSON.
Done when: every model has every metric from the same code version and solver,
or a recorded reason for a missing value.

### WS5: Metabolic tasks

Goal: show what the models can do, not only how they look.

1. Use the task tables in `files/metabolic_tasks/` (Human-GEM `develop`
   `2f1d3e33`) and the decisions in `docs/plans/metabolic_task_decisions.md`.
   **Always import the tables with the name mapping**
   (`files/metabolic_tasks/human_gem_names.json`). THG models rename
   metabolites, so without it most tasks do not resolve and run as "invalid".
   An invalid task is neither a pass nor an infeasible VerifyModel result.
   Report the invalid count per model and table in `task_results.csv`, and
   treat any invalid VerifyModel task as a gate failure until explained.

   Preliminary check (2026-11-04, Gurobi, closed medium, LB > 0 / UB < 0 on
   non-boundary reactions relaxed; script not yet in `publication/`):

   | Model | Essential invalid (no map → map) | Full invalid (no map → map) | VerifyModel feasible (should be 0) |
   |---|---|---|---|
   | Human1 2022-06-21 | 1 → 1 of 57 | 2 → 0 of 257 | 0 of 21 |
   | Human2 | 0 → 1 of 57 | 0 → 0 of 257 | 0 of 21 |
   | THG-2023 | 36 → 1 of 57 | 160 → 0 of 257 | 20 of 21 (all but task 16) |
   | THG-β2 (legacy) | 36 → 1 of 57 | 160 → 0 of 257 | 20 of 21 (all but task 16) |
   | current gapfilled candidate (`runs/thg-reference`, older commit) | 0 → 1 of 57 | 0 → 1 of 257 | 4 of 21 (tasks 10, 11, 17, 21) |

   So: the mapping is needed for the legacy models and fixes almost all of
   their invalid tasks. It adds one invalid task on models that keep Human-GEM
   names; find out which task and why before WS5b. The current candidate's 4
   feasible tasks came from the β1 consolidation bug (section 3, "Known
   issue"), now fixed; the WS1 build should pass the gate unless something
   else leaks.
2. **Run VerifyModel first, on the newly generated THG model from WS1.**
   `files/metabolic_tasks/metabolicTasks_VerifyModel.txt` holds 21 tasks that
   **must be infeasible**, for example "oxygen from water" and "ATP from
   nothing". If one is feasible, the model can make mass or energy from
   nothing, and every Essential/Full pass on it is suspect. This is already
   known to happen: with the stored mapping, a closed medium and biomass LB
   relaxed, Human-GEM gets 21 of 21 correct, but the endo models
   (`endoA_251219_preprocessed_baseline.json`, `endoC_final_7.xml`) are wrongly
   feasible on 19 of 21. On endoC, "oxygen from water" runs through the
   unbalanced `R08758_c` (missing NAD(P)+ oxidant) together with
   `MAR07938`/`MAR01987`. See `docs/plans/metabolic_task_decisions.md` and
   `docs/plans/metabolic_task_leaks_plan.md`.

   > **STOP CONDITION.** If the newly generated THG model has **any**
   > VerifyModel task feasible, stop all of WS5 and every workstream that
   > depends on the final model (WS4, model-dependent figures and WS7 exports). Do not attempt
   > to fix the leak, do not edit the model or pipeline to remove it, and do
   > not report Essential/Full results. Instead:
   >
   > 0. First rule out the known consolidation leak (section 3, "Known
   >    issue"): check `cleanup.json` and run VerifyModel per stage to find the
   >    first stage that leaks. Include the result in the report.
   > 1. Write `publication/ws5/verifymodel_leaks.md` with: the model path and
   >    SHA-256, commit, solver, medium and bounds used; which of the 21 tasks
   >    are feasible; for each feasible task, the pFBA flux solution (non-zero
   >    reactions, sorted by absolute flux) and, for each reaction in it,
   >    whether it is mass/charge balanced and where it came from (Human2,
   >    Human Database, gapfill/PTR, curation), if the run provenance says so.
   > 2. Save the raw results to `publication/ws5/verifymodel_results.csv`.
   > 3. Report to the user and wait. The user investigates the leaks and
   >    decides how to proceed. Resume only on the user's explicit go-ahead.
   >
   > WS2 can continue during the stop, since it does not depend on the model.

3. Only after 21 of 21 VerifyModel tasks are reliably infeasible: run Essential
   and Full on the patched Human-GEM 2.1.1 baseline and current THG,
   with the same medium, bounds and solver. The first-draft THG-2023 comparison
   uses structural statistics in WS3. The preliminary historical task run
   above predates the current residual diagnostics. A future matched task
   comparison would need a fresh run and distinct reporting of invalid,
   unresolved and feasible VerifyModel outcomes.
4. For each task that passes in one model and fails in another, give the cause
   (missing reaction, missing transport, blocked metabolite).

Output: `publication/ws5/task_results.csv` (model, table, task id, result,
cause), summary table for Fig 4.
Done when: current THG has 21 of 21 VerifyModel tasks infeasible and every
discordant task has a stated cause. If the stop condition fired, WS5 is not done
until the user has investigated and given the go-ahead.

### WS6: Gene essentiality (dropped)

Skipped by user decision. No cell-line extraction, DepMap download or
essentiality figures are required.

### WS7: Release and reproducibility package

1. Refresh the stale documents flagged in `legacy-comparison.md`
   (`release-status.md`, `implementation-status.md`,
   `refactoring-changes-2026-10.md`).
2. Run hosted CI on the release commit.
3. Write `publication/README.md`: one command per workstream to regenerate its
   results, and the expected runtime.
4. Prepare a tagged release and a Zenodo archive containing the code, configs,
   final model (SBML + JSON) and the `publication/` results. Do not create the
   tag or archive without the user's approval.

Done when: a clean checkout plus the documented commands regenerates every
number in `publication/`.

---

## 5. Order and dependencies

Use the build and draft checklist. Build B, replay C and the
final task benchmark are recorded in the November 20 checkpoint. Resolve the
SBML/JSON discrepancy before making model-quality claims. Complete WS0 and
WS4 validation with the same settings and schedule heavy jobs sequentially.
WS2, the historical workflow mapping and the manuscript opening can proceed
in parallel with validation. The WS3 model row and current-model validation
feed Table 1 before the evidence audit.

If the THG gate fails, follow the WS5 stop condition for model-dependent work.
Numerically unreliable results remain unresolved until investigated. Continue
independent writing and correctness evidence, applying the Day-2 fallback.

WS7 draft scope is local provenance, commands and artifact completeness. Hosted
release CI, tagging and archiving are later release requirements. Publishing
requires the user's approval. The full WS3 attribution is deferred and WS6
is dropped.

## 6. Decisions the user must make

Ask; do not decide alone.

1. **Paper framing** — *decided 2026-11-23.* A methods-led follow-up to the
   2023 THG publication.
2. **Human2 identity:** *decided: Human-GEM 2.1.1 with `MAR20193` blocked.* `Human2.xml` is an older Human2 release. Citations deferred (user: not yet).
3. **Leak fixes:** if the new THG model fails VerifyModel, the user
   investigates and decides the fix. The agent stops and does not choose (see
   the WS5 stop condition).
4. **Venue:** deferred; does not block the internal draft.
5. **Dedup isomer leak:** *decided 2026-11-09: merge only if all database IDs
   agree* (WS1 finding 1).
6. **Unbalanced-parent expansion:** *decided 2026-11-09: never copy an
   unbalanced reaction; balance the parent where possible* (WS1 finding 3;
   charge curation still to do).
7. **WS0 legacy/Human1 rows:** *decided 2026-11-09: not needed for now.*
8. **Commits:** *decided 2026-11-09: commit now.*
9. **Two-tier export:** *decided 2026-11-20: the paper presents the full
   localisation layer.* Added reactions are still classified as flux-capable or
   blocked and reported (dead-end and blocked counts in Results 3.3 and the
   Discussion), but no separate flux-consistent model is exported or presented.
   Reopen only if the user asks for it.
10. **Human Protein Atlas data:** *decided 2026-11-20: approved.* Use HPA
    subcellular locations as an independent check of gene-to-compartment
    assignments in both models; HPA agreement is a column of the ablation
    ladder (Results 3.1).
11. **Comparison models** — THG-2023 provides the historical comparison
    (WS3). Human-GEM 2.1.1 with `MAR20193` blocked remains the matched
    benchmark (WS4 and WS5).
12. **Legacy changes in Results:** *decided 2026-11-11: multi-compartment genes
    and GO-hierarchy compartment mapping; UniProt query and "Cytoplasm" alias
    dropped from Results.*
13. **Gapfill selection:** *decided 2026-11-18: exact MILP, rank-then-ID
    tie-break and removal of inactive connectors approved; describe them in
    Methods.* Removing the connector stage or choosing connectors by flux, and
    FASTCORE-style selection, remain deferred.
14. **HiGHS:** *decided 2026-11-18: add HiGHS as an optional gapfill solver.*
    Paper runs stay on Gurobi. Open: whether to build a faster HiGHS path that
    calls `highspy` directly with warm starts (estimated 2–3 days), so the full
    model can be gap-filled without a commercial license.

## 7. Rules for the agent

- No result enters the manuscript without a file in `publication/` and the
  command that produced it.
- Report failures and negative results as they are. If THG loses a benchmark,
  record it.
- Keep `inputs/` and `models/` read-only. Write new artifacts under `runs/` or
  `publication/`.
- Use the same solver, tolerances, medium and code version across all models
  in a comparison. Record them.
- Commit per workstream, only when the user asks.
- Respect the WS5 stop condition. A feasible VerifyModel task on the new THG
  model halts all model-dependent work until the user says to continue.
