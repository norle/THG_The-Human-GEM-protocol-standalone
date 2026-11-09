# Publication plan: THG protocol re-implementation and model benchmark

Hand-off for an agent. Written 2026-11-04. It describes the analyses the paper
needs, the outputs each one must produce, and where those outputs go in the
manuscript.

Read first: `docs/about/legacy-comparison.md`,
`docs/contributing/refactoring-changes-2026-10.md`,
`docs/plans/metabolic_task_decisions.md`,
`docs/plans/metabolic_task_leaks_plan.md`,
`docs/protocol/implementation-status.md`.

## Progress (updated 2026-11-09)

| WS | State |
|---|---|
| WS0 | **Not done.** Harness validated (Human1 21/21). Human 2.1.1 leaks (task 21); patched model (`MAR20193` blocked) 21/21, Essential 57/57, Full 255/255 (2 invalid). Missing: MEMOTE/`final-standard` validation of the patched model, README final summary (Human1/legacy rows not needed for now, user 2026-11-09). Gene-essentiality dry run **skipped by user decision**. |
| WS1 | **Started; fixes in, re-run pending.** Configs point at the patched model. Run `runs/thg-ws1-a` (2026-11-05, after `0e5584b`) failed `gate-beta2` ("added reactions include mass- or charge-unbalanced chemistry"). Both causes fixed 2026-11-09 (below); WS1 build must be re-run from `deduplicate-and-clean`. `thg-ws1-b` (determinism twin) not run. |
| WS2 | Started: inventory only (`publication/ws2/fixes.csv`, `engineering.csv`); no real-data impact measured. |
| WS3, WS4, WS5, WS7 | Not started; all wait on the WS1 model. WS3 legacy comparison deprioritised by user (2026-11-09). |
| WS6 | **Dropped** (essentiality benchmark skipped by user; DepMap not used). Fig 5 loses its essentiality panel. |

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
   numerics. Follow-up (open): make the task harness report the max bound and
   constraint violation of every "optimal" task solve and flag > 1e-7 as
   numerically unreliable, so VerifyModel cannot pass or fail on slack.
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

**Next actions:** re-run WS1 (`thg-ws1-a` from `deduplicate-and-clean`, or a
fresh run) → stage-wise VerifyModel with Gurobi and GLPK → `thg-ws1-b` for
determinism. Then: charge curation of the 11 parents (β1), harness violation
check, WS0 MEMOTE on the patched model.

Results so far: `publication/ws0/` (task results, `verifymodel_leaks.md`), `publication/ws1/` (stage VerifyModel, dedup bisect, run configs), `publication/benchmark_settings.json`.
Machine memory was exhausted on 2026-11-04; check `free -m` before MEMOTE runs (2026-11-09: ~11 GB available).

Environment: conda env `thg_standalone` (has Gurobi). Use memote and
optlang/Gurobi for model-scale LPs. mkdocs and ruff live only in the base env.

---

## 1. Framing of the paper

**Main claim (software/methods):** THG has been re-implemented as a
reproducible, tested and resumable protocol. Porting it exposed and fixed
scientific errors in the legacy pipeline, and the redesigned protocol produces
a model that is at least as consistent as Human-GEM while extending its
coverage.

**Supporting claim (resource):** the resulting THG model is compared with
Human1 and Human2 on structural, quality and functional benchmarks, with every
model run through the same pipeline.

Wording rule: the paper describes a **redesigned and re-implemented
protocol**. It does not claim to reproduce the 2023 artifact
(`publication.final_artifact` is unverified). Every claim in the text must
point to a result file produced by this plan.

Candidate venues: *Bioinformatics* (Application Note) or *PLOS Comput Biol*
(Software) for a methods-led paper. *NAR Genomics & Bioinformatics* or
*Metabolic Engineering* are realistic if the functional results (WS5) are
strong.

## 2. Proposed manuscript structure

| Section | Content | Evidence from |
|---|---|---|
| Abstract | Claim, key numbers (bugs fixed, model size, task pass rates, essentiality AUC) | all WS |
| 1. Introduction | Human GEMs (Recon3D, Human1, Human2), 2023 THG protocol, reproducibility problem in GEM curation | literature |
| 2. Methods / Implementation | Package architecture, stage DAG, resumable runs and provenance, gates, service clients, merge, `sink-milp` gapfill, validation profiles, task evaluation, benchmark protocol | WS1, WS7 |
| 3.1 Results: re-implementation | Correctness fixes with quantified impact; engineering metrics | WS2 |
| 3.2 Results: legacy vs. current THG | Model-level diff, attribution of differences to reference-model change vs. code changes | WS3 |
| 3.3 Results: THG vs. Human1/Human2, structure and quality | Size, overlap, compartments, dead-ends, blocked reactions, balance, consistency, EGCs, MEMOTE | WS4 |
| 3.4 Results: function | Metabolic tasks (VerifyModel, Essential, Full), gene essentiality in cell-specific models | WS5, WS6 |
| 4. Discussion | What the redesign changes scientifically, limitations, future work | all WS |
| Data and code availability | Tagged release, Zenodo DOI, pinned configs, run manifests | WS7 |
| Supplementary | Full tables, per-fix before/after, per-task results, run manifests | all WS |

### Planned figures and tables

| ID | Content | Produced by |
|---|---|---|
| Fig 1 | Protocol overview: stage DAG β1 → β2 → Human Database → merge → gapfill → validation → export, with gates and provenance | WS1 |
| Fig 2 | Impact of the correctness fixes (before vs. after per fix) | WS2 |
| Fig 3 | Legacy THG vs. current THG: reaction/metabolite/gene overlap (UpSet or Venn) and attribution waterfall | WS3 |
| Fig 4 | THG vs. Human1 vs. Human2: structure and quality panel (size, compartments, dead-ends, blocked, balance, EGCs, MEMOTE) | WS4 |
| Fig 5 | Function: task pass rates and gene-essentiality ROC/PR curves | WS5, WS6 |
| Table 1 | Legacy vs. standalone engineering comparison (short) | WS2 |
| Table 2 | Model statistics for all compared models | WS3, WS4 |
| Table S* | Per-fix evidence, per-task results, per-cell-line essentiality, MEMOTE detail | all WS |

## 3. Models in scope

Pin every model by path and SHA-256 in `publication/models.json` (WS1).

| Label | File | Role |
|---|---|---|
| Human1 (2022-06-21) | `models/Human-GEM_2022-06-21.xml` | Legacy reference and input of the 2023 pipeline |
| Human Database (2023-02-25) | `models/Human Database.xml` | Legacy Human Database used to build THG-2023 |
| Human2 (benchmark) | `runs/human211-patched/Human_211_patched.xml` | Current reference: Human-GEM 2.1.1 (`inputs/models/Human_211.xml`, SHA-256 `dc0efd80…5ddf`) with reaction `MAR20193` blocked (bounds 0,0). Made by `publication/scripts/patch_human211.py`; SHA-256 `04cb9de9…3f38`. Decided 2026-11-05. Name it "Human-GEM 2.1.1 with MAR20193 blocked" in the paper |
| Human2 unpatched | `inputs/models/Human_211.xml` | 2.1.1 as released. Fails VerifyModel task 21 (20 of 21); report it as is, Essential/Full as upper bounds |
| Human2.0 (extra) | `inputs/models/Human2.xml` | Believed 2.0 (user, unverified). 21 of 21 VerifyModel. Optional comparison row |
| THG-2023 (legacy final) | `models/THG-2023-02-25.xml` | Published legacy model |
| THG-β1 / β2 (legacy) | `models/THG-beta1.xml`, `models/THG-beta2.xml` | Legacy intermediates |
| THG current (β2, gapfilled, final) | produced by WS1 from `configs/reference.json` | The model being presented |

Provenance of the legacy inputs (checked 2026-11-04): `Human-GEM_2022-06-21.xml`,
`Human Database.xml` and `THG-2023-02-25.xml` in `models/` are byte-identical to
the copies committed in the legacy repository in February–March 2023 (commits
`fad16c2`, `3ee4f60`, `5ff6f1d`, `bbcae83` in `../THG_The-Human-GEM-protocol`),
so they are the files the 2023 pipeline used. Record this in
`publication/models.json`.

Out of scope: Human-GEM 1.19 and the 2025 legacy intermediates built on it
(`THG-beta-batch_251106*`, endo models). They are not part of the published
lineage and are not compared.

**Important confounder:** the legacy THG was built on Human1 (2022-06-21) and
the 2023-02-25 Human Database. The current pipeline uses `Human2.xml` and
rebuilds the Human Database from today's service releases. A raw
legacy-vs-current diff mixes the reference change, the database change and the
code changes. WS3 must separate them.

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
for WS4, WS5 and WS6.

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
6. **Gene-essentiality dry run.** *SKIPPED by user decision (2026-11-05); WS6 dropped.* Do the WS6 pipeline end to end on Human2 for
   one cell line: data download (pin the DepMap release), cell-specific model
   extraction with the package's GIMME, knockouts, scoring. This checks the method and the runtime before
   the THG models exist. Compare with Human1's published essentiality numbers
   where they are comparable, and explain any large gap.
7. **Fix the settings.** Write `publication/benchmark_settings.json` with the
   solver, tolerances, medium, bounds, task tables (and commit), mapping file,
   DepMap release and thresholds. Every later workstream uses exactly these
   settings for every model.

Output: `publication/ws0/` with `model_stats.csv` (one row, same columns as
WS4), the validation report and MEMOTE output, `task_results.csv` (same format
as WS5), the essentiality dry-run results, and a `README.md` with commands,
commit and runtime. Plus `publication/benchmark_settings.json`.
Done when: Human2 has 21 of 21 VerifyModel tasks infeasible, all metrics above
are recorded, and the essentiality dry run completes for one cell line. Report
the summary to the user before starting WS1.

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
   nondeterminism.
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

### WS2: Correctness fixes and engineering comparison

Goal: quantify each scientific bug fixed during the port.

1. Take every fix in `docs/contributing/refactoring-changes-2026-10.md` plus the
   later audit fixes (commits `c841863`, `cef04ea`,
   `reviews/2026-11-03-function-audit/`), and the β1 consolidation fix
   (section 3, "Known issue"). That one is a bug introduced by the redesign,
   not inherited from the legacy code; report it as such, with before/after
   VerifyModel on Human2 and the 2026-09-11 candidate.
2. For each fix, measure impact on **real data**, not just the fixture. For
   example: how many genes in Human2 lose localisation under the legacy
   multi-compartment rule (the doc reports 44 of 50 sampled; extend it to all
   genes); how many UniProt hits were non-human; how many reactions the legacy
   duplicate rule wrongly merged.
3. Where possible, run the legacy function (adjacent checkout
   `../THG_The-Human-GEM-protocol`) and the standalone function on the same
   input. Use a separate legacy environment; do not import legacy code into the
   package.
4. Build Table 1 from verifiable numbers: lines of code, tests (run
   `pytest -m "not online"` and record the count), CI matrix, runtime.

Output: `publication/ws2/fixes.csv` (fix id, description, metric, legacy value,
standalone value, affected entities, evidence path), `publication/ws2/engineering.csv`.
Done when: each fix has a numeric impact measured on a full model or is
explicitly marked "fixture only" with a reason.

### WS3: Legacy THG vs. current THG

Goal: explain how and why the current model differs from the published one.

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
   - THG-2023 vs. current(Human1, DB-2023) = effect of code and method changes;
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

Output: `publication/ws3/` with overlap tables, the attribution table, the
unique-reaction characterisation and the merge comparison.
Done when: the attribution accounts for the full count difference (with a
residual if needed) and every large unique set is characterised.

### WS4: Structure and quality vs. Human1/Human2

Goal: a fair, same-pipeline comparison. Reuse the Human2 row from WS0 if the
code commit and `benchmark_settings.json` are unchanged; otherwise rerun it.

Run `thg-run validate` with the same profile (`final-standard`) and
`run_memote: true` on every model in section 3. `runs/human2-validation` is a
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
   > depends on the final model (WS3, WS4, WS6, figures, WS7). Do not attempt
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

3. Only after 21 of 21 VerifyModel tasks are infeasible: run Essential and Full
   (CellfieConsensus optional) on Human1, Human2, THG-2023 and current THG,
   with the same medium, bounds and solver. Also run VerifyModel on the other
   models and report it. A comparison model that fails it (THG-2023 may) is
   reported as is, with its Essential/Full passes marked as upper bounds; this
   does not trigger the stop condition.
4. For each task that passes in one model and fails in another, give the cause
   (missing reaction, missing transport, blocked metabolite).

Output: `publication/ws5/task_results.csv` (model, table, task id, result,
cause), summary table for Fig 5.
Done when: current THG has 21 of 21 VerifyModel tasks infeasible and every
discordant task has a stated cause. If the stop condition fired, WS5 is not done
until the user has investigated and given the go-ahead.

### WS6: Gene essentiality in cell-specific models

Goal: an external, biological benchmark.

1. Pick 3–5 cell lines that have both expression data (CCLE/DepMap RNA-seq) and
   CRISPR essentiality (DepMap Chronos). Prefer lines used in Human1's
   benchmark so results can be compared.
2. Build cell-specific models from Human2 and from current THG with the
   package's own GIMME implementation (`src/thg_protocol/cell_specific/gimme.py`,
   `thg-run` `cell_specific` workflow), with the same thresholds for every
   model. Do not port or use other extraction methods. Map THG and Human2
   gene IDs to DepMap gene identifiers and report coverage per model.
3. Predict single-gene knockouts (growth below a set fraction of wild type) and
   score against DepMap: ROC-AUC, PR-AUC, MCC, at a stated Chronos threshold.
4. Bootstrap or permutation test the difference between THG and Human2.

Output: `publication/ws6/` with per-cell-line predictions, metrics and data
versions (DepMap release).
Done when: metrics exist for every model × cell line, with confidence
intervals. Report the result honestly even if THG does not win.

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

```
WS0 (Human2 baseline) ──> WS1 ──> WS5a: VerifyModel gate on new THG
                                     │  (any task feasible → STOP, hand to user)
                                     ▼
                       ┌─────────────┼──────────────┬─────────────┐
                       ▼             ▼              ▼             ▼
                      WS4      WS5b: Essential/    WS6          WS3
                               Full, all models                  │
                       └─────────────┴──────────────┴─────────────┘
                                     ▼
                              figures/tables ──> WS7

WS2 (independent, can start immediately; continues during a stop)
WS3 steps 2 and 5 (Human1/DB-2023 attribution run, merge comparison) do not
use the new THG model and can run before or during a stop.
```

Suggested sequence: **WS0 first**, and report its results to the user → WS2 and
WS1 in parallel (plus the WS3 attribution run) → WS5a VerifyModel gate on the
new model (**stop and hand over to the user if any task is feasible**) → WS4 →
WS5b → WS3 (remaining steps) → WS6 → figures → WS7. The model is not frozen for
the paper until it passes the gate, because the user's fix may change it.

## 6. Decisions the user must make

Ask; do not decide alone.

1. **Paper framing:** *decided 2026-11-09: methods-led.*
2. **Human2 identity:** *decided: Human-GEM 2.1.1 with `MAR20193` blocked.* `Human2.xml` is an older Human2 release. Citations deferred (user: not yet).
3. **Leak fixes:** if the new THG model fails VerifyModel, the user
   investigates and decides the fix. The agent stops and does not choose (see
   the WS5 stop condition).
4. **Venue:** deferred; no manuscript text is written yet.
5. **Dedup isomer leak:** *decided 2026-11-09: merge only if all database IDs
   agree* (WS1 finding 1).
6. **Unbalanced-parent expansion:** *decided 2026-11-09: never copy an
   unbalanced reaction; balance the parent where possible* (WS1 finding 3;
   charge curation still to do).
7. **WS0 legacy/Human1 rows:** *decided 2026-11-09: not needed for now.*
8. **Commits:** *decided 2026-11-09: commit now.*

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
