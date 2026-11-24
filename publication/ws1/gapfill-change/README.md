# Gapfill selection change (plan stage version 6 -> 7)

Evidence for Methods ("Gapfill selection" in `docs/plans/publication-plan.md`).
Old = `runs/thg-ws1-b` before the rebuild (version 6, archived in `old-b-v6/`).
New = `runs/thg-ws1-b` rebuilt on source commit `1805783` (version 7),
Gurobi 12.0.1, `MIPGap = 0`, `coverage_workers = 8`. Build record:
`../rebuild-b/` (commit, `git status --porcelain`, command, logs).

## Command

```sh
python publication/scripts/measure_gapfill_change.py \
  publication/ws1/gapfill-change/old-b-v6/generate-gapfill-plan/attempt-0001/gapfill-plan.jsonl \
  runs/thg-ws1-b/artifacts/generate-gapfill-plan/attempt-0002/gapfill-plan.jsonl \
  runs/thg-ws1-b/artifacts/generate-gapfill-plan/attempt-0002/gapfill-report.json \
  runs/thg-ws1-b/artifacts/select-gapfill-connectors/attempt-0001/ptr-connectors.jsonl \
  publication/ws1/gapfill-change/plan_v6_vs_v7.json
```

Output: `plan_v6_vs_v7.json`.

## Measured

| Quantity | Version 6 (old B) | Version 7 (rebuilt B) |
|---|---|---|
| Connectors proposed | 152 | 152 |
| Connectors kept | 152 | 16 (136 inactive, dropped) |
| Selected (non-connector) PTRs | 162 | 162 |
| Reactions added | 314 | 178 |
| Dead ends before / after | 6,150 / not recorded here | 6,150 / 6,018 |
| Components before / after | 203 / not recorded here | 203 / 123 |

- The 16 kept connectors are a subset of the old 152.
- The two selections of 162 PTRs are **not identical**: 72 PTRs are in each
  one only. 280 reactions differ in total (136 dropped connectors + 72 + 72).
- Version 7 plan header: MILP optimal, `mip_gap` 0.0, objective 619.38,
  tie-break solve optimal ("rank, then ID"), 3,328 targets, 621 coverable,
  1,227 `sink_only`.

## Open at the November 20 checkpoint

- The effect of each change alone. The 72 + 72 PTR difference mixes the exact
  gap, the tie-break and the changed connector set. Separating them needs
  extra solves (version-7 selection with all 152 connectors kept; version 6
  with `MIPGap = 0`). Not run.
- Whether the tie-break was needed (selection of the second solve vs the
  first). Not recorded in the plan.
- B vs C plan identity (build C running).
- The serial-code benchmark is not rerun (see below for the other equality
  check).

## Coverage equality (rebuilt vs old B)

`ptr-coverage.jsonl` of the rebuilt run (`compute-gapfill-coverage/attempt-0003`,
721.6 s, eight workers) and of the old run (serial, archived in `old-b-v6/`)
both have 142 records; 141 are identical and the only difference is the
`fingerprint` record (the solver is now part of the fingerprint). Command:
load both files and compare the records, excluding nothing else.

## Fixed-coverage selection ablation

`selection_ablation.json` replays the historical single solve with the Gurobi
default MIP gap, the same solve forced to gap zero, and the current solve
with its secondary objective. All three use rebuilt B's saved coverage,
unchanged costs and the same budget of 848 with 152 connectors included
in the coverage model. The first two select the same 162 PTRs. The
tie-break exchanges 72 PTRs per selection and covers the same 621 targets.
The current selection matches the saved B plan.

Connector removal is downstream of selection. It drops 136 connectors
from that plan without changing the 162 selected non-connector PTRs. The
[B/C comparison](../replay-b-vs-c/README.md) verifies plan identity.

Run with the pinned solver bootstrap in the [evidence index](../../README.md).
The serial comparison there runs current code with one worker on the
same input. The saved version-6 coverage records provide a separate
old-code equality comparison.

## Current code with one worker

The [serial comparison](serial/comparison.json) reports 2,093.32 seconds with
one worker and no reused components. All 141 component records match the
earlier eight-worker B run. This verifies record equality. The elapsed times
come from separate runs with different concurrent workloads. The serial run
overlapped publication validation.
