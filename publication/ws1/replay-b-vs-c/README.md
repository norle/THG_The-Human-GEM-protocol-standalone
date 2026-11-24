# Build B vs build C (independent replay, Results 3.4)

Both builds ran from the frozen evidence snapshot (`publication/ws1/frozen/`) on
source commit `1805783f` with Gurobi 12.0.1, Threads 2, tolerances 1e-7
(`publication/ws1/run_build.py`), and `coverage_workers = 8`. They differ in run name only
(`reference-b-frozen.json`, `reference-c-frozen.json`).

- **B** is a resumed run (`runs/thg-ws1-b`): stages 1–41 were reused from the
  earlier B run (completed 2026-11-10 on the previous source tree), and
  stages 42–52 were recomputed on `1805783` (record: `../rebuild-b/`).
- **C** is a fresh run from scratch (`runs/thg-ws1-c`, 44 stage executions,
  13:02:59–15:59:52, about 2 h 57 min; record: `../build-c/`).

Neither tree was fully clean: `git status --porcelain` listed only untracked
`publication/` files (saved next to each run); `src/`, `tests/`, `docs/` and
the configs were committed.

## Command

```sh
python publication/scripts/compare_replay.py runs/thg-ws1-b runs/thg-ws1-c \
  publication/ws1/replay-b-vs-c/comparison.json
```

## Result

| Check | Result |
|---|---|
| Final `thg-reference.json` | identical bytes, SHA-256 `fd7da017…636dda` |
| Final `thg-reference.xml` | identical bytes, SHA-256 `087cf3b5…a2ef4ee` |
| Semantic comparison of final models | equal |
| Gapfill plan (`gapfill-plan.jsonl`) | identical bytes |
| Stage model checksums | 37 of 44 stages identical; 7 differ (below) |

The 7 stages that differ differ only in provenance and bookkeeping, not in a
model or plan:

| Stage | File that differs | Cause (measured) |
|---|---|---|
| `export-beta1` | `beta1-provenance.json` | `config_snapshot_sha256` (config contains the run name) |
| `export-beta2` | `beta2-provenance.json` | stage fingerprints derived from the config snapshot (16 entries) |
| `gate-beta2` | `beta2-gate.json` | run name and run directory |
| `load-gapfill-source` | `gapfill-source-provenance.json` | run name, paths, upstream run |
| `export-gapfilled-reference` | `provenance.json` | run name, paths, upstream run |
| `summarize-reference` | `reference-report.json` | run name, attempt numbers in artifact paths |
| `compute-gapfill-coverage` | `ptr-coverage.jsonl` | only the `fingerprint` record; the other 141 records are identical |

So the final models and the gapfill plan are bit-identical across the two
builds on the same inputs and code; the checksum differences are confined to
files that record the run name, paths or fingerprints.

## Limits

- B reused stages 1–41 from an earlier run, so B vs C tests those stages as
  well (C recomputed them), but B's stages 1–41 were produced by the earlier
  source tree. That tree differs from `1805783` in the gapfill code; those
  stages' checksums match C's, which supports that the change did not affect
  them.
- Both builds used the same machine and the same pinned input snapshot; this is
  a replay of the computation, not a replay of the HTTP acquisition.
- B's manifest does not record the source commit; `../rebuild-b/source-commit.txt`
  does.
