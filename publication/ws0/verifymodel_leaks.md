# WS0 stop condition: VerifyModel task 21 feasible on Human-GEM 2.1.1

- Model: `inputs/models/Human_211.xml` (Human-GEM 2.1.1, per user), SHA-256 `dc0efd8009a8b680bde7040440f2e3592027dd118833445092ebd8d7bc425ddf`
- Commit: `968c2a858e2a5216ce8252244133a54308bf115f`; solver Gurobi (cobrapy/optlang); closed medium; non-boundary reactions with LB>0/UB<0 relaxed (0 changed); name mapping `files/metabolic_tasks/human_gem_names.json`
- Result: 20 of 21 infeasible (correct). **Task 21 "ATP production from Pi and O2 [#102]" is feasible.** 0 invalid VerifyModel tasks.
- Control: Human1 (2022-06-21) 21/21 infeasible; Human2.xml (believed 2.0) 21/21 infeasible, same harness and settings.
- Raw results: `task_results_Human2.1.1.csv`; pFBA: `verifymodel_leak_task21.json`; scripts: `publication/scripts/run_tasks.py`, `publication/scripts/verifymodel_leak.py`.
- Provenance: all active reactions are Human2.1.1 reactions (no pipeline, gapfill or curation step is involved; the model is the pipeline input).

## pFBA solution (385 non-zero reactions; top by |flux|)

| Reaction | Flux | Equation | Imbalance |
|---|---|---|---|
| MAR06328 | 1.018 | ADP + ATP <=> ADP + ATP |  |
| TEMPORARY_1 | 1.000 | ATP + H2O --> ADP + H+ + Pi |  |
| MAR05043 | 1.000 | H+ + Pi --> H+ + Pi |  |
| MAR04888 | -0.994 | H2O <=> H2O |  |
| MAR06916 | 0.941 | ADP + 3.0 H+ + Pi --> ATP + 2.0 H+ + H2O |  |
| MAR07638 | 0.855 | H+ --> H+ |  |
| MAR06918 | 0.438 | 2.0 ferricytochrome C + 2.0 H+ + ubiquinol --> 2.0 ferrocytochrome C + 4.0 H+ + ubiquinone |  |
| MAR06921 | 0.299 | 5.0 H+ + NADH + ubiquinone --> 4.0 H+ + NAD+ + ubiquinol |  |
| MAR04896 | -0.219 | O2 <=> O2 |  |
| TASK_IN_MAM02630e | 0.219 |  --> O2 |  |
| MAR04898 | 0.219 | O2 <=> O2 |  |
| MAR06914 | 0.219 | 4.0 ferrocytochrome C + 8.0 H+ + O2 --> 4.0 ferricytochrome C + 4.0 H+ + 2.0 H2O |  |
| MAR02225 | -0.154 | HCO3- <=> HCO3- |  |
| MAR03956 | 0.154 | CO2 + H2O <=> H+ + HCO3- |  |
| TASK_OUT_MAM02046e | 0.138 | HCO3- -->  |  |

## Unbalanced reactions in the solution

- `MAR00012` flux 0.0107, in Human2.xml: True, identical: True
  - fatty acid-uptake pool --> 0.0001 (10Z)-heptadecenoic acid + 0.0001 (11Z,14Z)-eicosadienoic acid + 0.0001 (11Z,14Z,17Z)-eicosatrienoic acid + 0.0001 (13Z)-eicosenoic acid + 0.0001 (13Z)-octadecenoic a
  - imbalance {'charge': -0.9999999999999999, 'C': 16.205600000000004, 'H': 30.715400000000002, 'R': -1.0}
- `MAR03437` flux 0.0000, in Human2.xml: True, identical: True
  - (4Z,7Z,10Z,13Z,16Z,19Z)-docosahexaenoyl-CoA + 3.0 H+ + NADPH <=> (7Z,10Z,13Z,16Z)-docosatetraenoyl-CoA + NADP+
  - imbalance {'charge': -2.0}
- `MAR03483` flux 0.0000, in Human2.xml: True, identical: True
  - 3-oxo-all-cis-6,9,12,15,18-tetracosapentaenoyl-CoA + CoA + 2.0 H+ <=> (7Z,10Z,13Z,16Z)-docosatetraenoyl-CoA + acetyl-CoA
  - imbalance {'charge': -2.0}

## Differences from Human2.xml (2.0)

- `MAR20193` flux 0.0247, absent from 2.0: 2.0 H+ + succinate --> 2.0 H+ + succinate
- `MAR11506` flux 0.0000, changed vs 2.0: (R)-mevalonate + H+ <=> H2O + Mevalonate-Lactone
- `MAR05378` flux 0.0000, changed vs 2.0: (2E,7Z,10Z,13Z,16Z)-docosapentaenoyl-CoA + CoA + H2O + NAD+ --> acetyl-CoA + arachidonoyl-CoA + H+ + NADH
- `MAR05383` flux 0.0000, changed vs 2.0: 3,7,10,13,16-docosapentenoyl-CoA --> (2E,7Z,10Z,13Z,16Z)-docosapentaenoyl-CoA

## Observations (not a fix)

- `MAR00012` ("fatty acid-uptake pool" composition) carries flux and is mass-imbalanced by an R group plus about C16 H31 and a negative charge: a lipid-pool composition reaction can create fatty-acid carbon, which beta-oxidation could turn into ATP. This is the same class of leak as the consolidation bug described in the plan, but it is in the input model itself. Not yet confirmed as the sole cause: blocking it and re-running task 21 would test that.
- The solution also contains `MAR20193` (succinate transport, absent from 2.0) and `MAR11506`, `MAR05378`, `MAR05383` (changed vs 2.0, zero flux).
- Per the stop condition no model or pipeline change was made.

## Status

WS0 halted. Waiting for the user.

## Fix investigation (user authorised, 2026-11-04)

Tested in memory; `inputs/` untouched.

| Blocked | VerifyModel |
|---|---|
| none | 20/21 (task 21 feasible) |
| `MAR00012` (pool composition) | 21/21 |
| `MAR20193` (succinate/H+ efflux, SLC16A1, new in 2.1.1) | 21/21 |
| `MAR11506`, `MAR05378`, `MAR05383` (changed vs 2.0, no flux) | 20/21 |

- `MAR00012` is identical in 2.0 and unbalanced there too; 2.0 passes. So it is a latent imbalance (generic R-group pool), not the new cause.
- `MAR20193` is the only flux-carrying reaction absent from 2.0. It is mass and charge balanced; it gives the pool-derived carbon a way out of the cell, which lets the `MAR00012` imbalance sustain ATP synthesis. Interpretation from the flux solution, not independently proven.
- Blocking `MAR20193` costs nothing in the task suites: Essential 57/57, Full 255/255 (2 invalid, as before), see `task_results_Human2.1.1_block-MAR20193.csv`.
- Patched model: `runs/human211-patched/Human_211_patched.xml` (script `publication/scripts/patch_human211.py`), 21/21 infeasible.

Caveats: this is a minimal patch that closes the leak, not a curated fix. The underlying cause is the generic-R-group pool-composition reactions (`MAR00012`), which may allow other leaks through other outlets; only the 21 VerifyModel tasks were checked. Whether to block `MAR20193`, rebalance the pool reactions, or report upstream is your decision.
