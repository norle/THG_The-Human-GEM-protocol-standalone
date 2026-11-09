# WS1: Frozen build of the current THG model

Status (2026-11-09): **corrected build running; not done.** Deduplication
attempt 2 completed without merges; beta1 validation is running. The manifest
and live log remain authoritative; independent replay is pending.

## Files
| File | What |
|---|---|
| `reference-a.json`, `reference-b.json` | Build configs for runs `thg-ws1-a` / `thg-ws1-b` (determinism pair); input `runs/human211-patched/Human_211_patched.xml` |
| `verifymodel/task_results_stage-*.csv` | VerifyModel per stage of `thg-ws1-a` (2026-11-05, before the 2026-11-09 fixes). `stage-beta2` was the β2 export attempt 2; its 21/21 is a solver-tolerance artefact, not a fix |
| `bisect_dedup_task21.json` | Undoing each dedup merge in turn; undoing `MAM04041m → MAM01576m` alone removed the task-21 result |

## Findings from `thg-ws1-a`
1. Dedup merged isomers (11 merges). Fixed in `4bc7a54`: merges need all
   shared database IDs to agree; 0 merges on 2.1.1; VerifyModel 21/21 (Gurobi
   and GLPK) on the new dedup output.
2. The task-21 "leak" on β1 relied on a 3.0e-7 bound violation (tolerance
   1e-7) through `MAR00012`; GLPK finds it infeasible. Task results near the
   tolerance are not trustworthy until the harness reports violations.
3. `gate-beta2` failed on copies of unbalanced reactions. Fixed in `9fe67fa`
   (no copies of unbalanced parents; 14 parents, 26 copies). 11 parents are
   charge-only imbalances still to be curated in β1.

## Next
Re-run the build, stage-wise VerifyModel with Gurobi and GLPK, then `thg-ws1-b`
for determinism.

## Corrected run started (2026-11-09)

Numerical prerequisite implemented at `ac56d01`. Baseline refresh: VerifyModel
21/21, Essential 57/57, Full 255 pass + 2 invalid; detailed numerical evidence
is under `publication/ws0/numerical-refresh/`.

After `thg-run unlock runs/thg-ws1-a` verified and cleared the stale lock:
```sh
thg-run resume runs/thg-ws1-a --force-step deduplicate-and-clean -v > publication/ws1/corrected-build.log 2>&1
```

The run is active at deduplication attempt 2; upstream artifacts were reused.
The live manifest/log is authoritative. A fresh independent replay remains
pending; reusing valid artifacts in this run is not independent replay evidence.
This build uses source commit `ac56d01`; subsequent publication scripts and prose
do not alter its workflow implementation.

Deduplication attempt 2 completed in 484.60 s with zero metabolite/reaction
merges; its model SHA-256 equals the `apply-balance-proposals` input
(`50f9e3ae…b02cb6`). Beta1 validation is now running.

Checkpoint export (solver-free, seconds):
```sh
python publication/scripts/stage_table.py runs/thg-ws1-a publication/ws1/current
```

`current/stage_table.csv` and its manifest snapshot report input/output sizes,
runtime and cleanup merges. Completed states with incomplete upstream stages
are labelled stale; their old outputs are omitted. The checkpoint is not a
final run manifest or an independent-replay result.
