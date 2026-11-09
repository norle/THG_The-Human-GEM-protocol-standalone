# WS0: Human-GEM baseline

Commit `968c2a8`; solver Gurobi via cobrapy/optlang, 2 threads; closed medium; non-boundary
forced fluxes relaxed (none needed); name mapping `files/metabolic_tasks/human_gem_names.json`.
Settings: `publication/benchmark_settings.json`. **Status: halted at the VerifyModel gate; WS0 not done.**

## Models
| Label | File | SHA-256 | Version |
|---|---|---|---|
| Human1 | `models/Human-GEM_2022-06-21.xml` | see plan | 2022-06-21 (positive control) |
| Human2.xml | `inputs/models/Human2.xml` | `cc5a4383…a4a7a` | believed 2.0 (user, unverified) |
| Human_211 | `inputs/models/Human_211.xml` | `dc0efd80…5ddf` | 2.1.1 (user); chosen as benchmark Human2 |
| Human_211 patched | `runs/human211-patched/Human_211_patched.xml` | `04cb9de9…3f38` | 2.1.1 with `MAR20193` blocked |

## Results (`task_results_*.csv`, `model_stats*.csv`)
| Model | VerifyModel infeasible (want 21) | Essential | Full |
|---|---|---|---|
| Human1 | 21/21 | not run | not run |
| Human2.xml (2.0) | 21/21 | 56 pass, 1 invalid (`GR`: `biomass[e]` absent) | 257/257 |
| Human 2.1.1 | **20/21** (task 21 feasible) | 57/57 | 255 pass, 2 invalid |
| Human 2.1.1, `MAR20193` blocked | 21/21 | 57/57 | 255 pass, 2 invalid |

Model size: 2.0: 12,931 rxn / 8,461 met / 2,848 genes; 2.1.1: 12,748 / 8,374 / 2,870.

## Leak
See `verifymodel_leaks.md` (pFBA, imbalance, differences from 2.0, block tests).

## Not done
- MEMOTE/`final-standard` validation: only partial (2.1.1 `validate-checks` finished; MEMOTE unfinished; no report). Patched model not validated.
- Gene-essentiality dry run (step 6): skipped by user decision.
- Patched-model baseline use: awaiting user decision.

## Commands
```
python publication/scripts/run_tasks.py MODEL LABEL publication/ws0 [VerifyModel Essential Full]
THG_BLOCK=MAR20193 python publication/scripts/run_tasks.py ...
python publication/scripts/model_stats.py MODEL LABEL OUT.csv
python publication/scripts/verifymodel_leak.py MODEL REF TASK OUT.json
python publication/scripts/patch_human211.py IN.xml OUT.xml
thg-run validate publication/ws0/validation-config-211.json
```
