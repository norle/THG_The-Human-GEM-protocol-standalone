# WS0: Human-GEM baseline

Commit `968c2a8`; solver Gurobi via cobrapy/optlang, 2 threads; closed medium; non-boundary
forced fluxes relaxed (none needed); name mapping `files/metabolic_tasks/human_gem_names.json`.
Settings: `publication/benchmark_settings.json`. **Status (2026-11-09): gate resolved; benchmark Human2 is 2.1.1 with `MAR20193` blocked (user decision 2026-11-05). WS0 not done: MEMOTE validation of the patched model and final summary remain.**

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
- Human1 Essential/Full and legacy THG rows: not needed for now (user, 2026-11-09).

## Commands
```
python publication/scripts/run_tasks.py MODEL LABEL publication/ws0 [VerifyModel Essential Full]
THG_BLOCK=MAR20193 python publication/scripts/run_tasks.py ...
python publication/scripts/model_stats.py MODEL LABEL OUT.csv
python publication/scripts/verifymodel_leak.py MODEL REF TASK OUT.json
python publication/scripts/patch_human211.py IN.xml OUT.xml
thg-run validate publication/ws0/validation-config-211.json
```

## Numerical refresh (2026-11-09)

Command (318.39 s):
```sh
python publication/scripts/run_tasks.py runs/human211-patched/Human_211_patched.xml human211-patched publication/ws0/numerical-refresh
```

Evidence: `numerical-refresh/task_results_human211-patched.json` and `.csv`.
Gurobi; feasibility/optimality/integrality 1e-7, two threads; closed medium,
stored name mapping; no forced bounds needed relaxation. The JSON records
commit `eac7144` and the working-diff checksum (numerical diagnostics were
uncommitted during this run). Later script changes add input-checksum checking;
the exact run script checksum is retained in the JSON.

- VerifyModel: 21 passed; all solver statuses infeasible. Residuals are null.
- Essential: 57 passed; maximum optimal-solve violation 1.03e-8.
- Full: 255 passed / 257 total, 2 invalid, no errors or failed tasks; maximum
  optimal-solve violation 1.14e-13.
- Invalid Full tasks: 180 (row 320 OUT, cytosol) and 239 (row 437 IN,
  extracellular). `10,13,16-docosatriynoic acid` does not map to the model's
  annotated docosatrienoic-acid species. Candidate names are retained in JSON;
  no biochemical identity substitution was made.

These results supersede the patched-model task row for numerical reliability.
Positive-control refresh and matched MEMOTE/quality validation remain pending.
Historical counts elsewhere in this README have not been refreshed.

## Native thread correction

The first numerical refresh did **not** verify the requested two Gurobi threads:
`configuration.threads` is not an optlang Gurobi setting. Its counts/residuals
remain historical evidence, but cannot establish a comparison with pinned
thread settings (`numerical-refresh/limitations.json`). The corrected runner
sets the native Gurobi default before model construction so task copies inherit
it, and records the effective native count for every solve. A licensed toy-model
regression verifies two threads on the actual task copies.

Required refresh:
```sh
python publication/scripts/run_tasks.py runs/human211-patched/Human_211_patched.xml human211-patched publication/ws0/pinned-refresh
```

Basic patched-model statistics are saved separately in `model_stats_patched.csv`
(model SHA-256 `04cb9de9…3f38`). They require no optimization and were read with
GLPK as the default solver:
```sh
python - <<'STATS'
import cobra, runpy, sys
cobra.Configuration().solver = "glpk"
sys.argv = ["publication/scripts/model_stats.py", "runs/human211-patched/Human_211_patched.xml", "Human-GEM 2.1.1 with MAR20193 blocked", "publication/ws0/model_stats_patched.csv"]
runpy.run_path(sys.argv[0], run_name="__main__")
STATS
```

Counts: 12,748 reactions, 8,374 metabolites, 2,870 genes, nine compartments,
146 subsystems and 1,654 exchanges. Cross-reference fractions (SBO excluded):
metabolites 0.9987, reactions 0.9895, genes 1.0. No Python SBML warnings were
captured. These are structural statistics, not MEMOTE/quality validation.
