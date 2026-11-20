# Sink-MILP gapfill speedup — handoff, 10 November 2026

> **Status 2026-11-18.** The selection changes were approved by the user. The
> stage wiring, the `coverage_workers` config key and the docs were done after
> this file was written, and `docs/workflows/gapfill-sink-milp.md` records the
> benchmark (536 s, identical coverage for components 1–4). Tests have still
> not run since the tie-break edit, because the Gurobi license expired. The
> remaining steps are in `docs/plans/publication-plan.md`, "Remaining work, in
> order", steps 1–3.

Work was interrupted mid-implementation. Nothing is committed. This file says
what is done, what is written but unverified, and what is left.

## What was agreed

1. Make `compute-gapfill-coverage` faster **without changing its results**.
2. Add a deterministic tie-break to the selection MILP.
3. Stop proposing connectors unconditionally.
4. FASTCORE-style selection and other method changes: **deferred**, to be
   discussed later. Do not start them.

Interpretation chosen for point 3 (not yet confirmed by the user): the
connector stage and the coverage baseline stay as they are; a connector that
cannot carry flux in the final model (no temporary sinks) is removed from the
result. Removing the connector phase entirely was the alternative and belongs
to the deferred method discussion.

## Files touched (uncommitted, branch `main`)

- `src/thg_protocol/gapfill/ptr.py`
- `tests/unit/test_gapfill_ptr.py`
- this file

The other modified files in `git status` (`docs/plans/publication-plan.md`,
`publication/HANDOFF-2026-11-09.md`, `publication/README.md`,
`publication/ws1/numerical-refresh/`) were already modified before this work
and are unrelated.

## Status by piece

| Piece | Code | Tests |
| --- | --- | --- |
| Lower solver overhead in `unblockable` (cached solver variables, read only needed fluxes, plain-sum pre-check before LP7) | written | passing at last run |
| Each cross-component candidate tested once, against both components' targets | written | passing at last run |
| Process pool for candidate tests (`compute_coverage(..., workers=...)`, spawn context) | written | passing at last run |
| Exact MILP (`MIPGap = 0` on Gurobi) and rank-then-ID tie-break (`select_unblockers(..., ranks=...)`) | written | **not run since the edit** |
| Inactive connectors dropped in `run_sink_milp` (status `connector-inactive`) | written | **not run since the edit** |
| Workflow stage passes `workers` to `compute_coverage` | **not started** | – |
| Config key for worker count | **not started** | – |
| Docs | **not started** | – |
| Full test suite, ruff | **not run** | – |

Last verified test state, before the tie-break and connector edit:
`tests/unit/test_gapfill_ptr.py` had 65 passing and 5 failing, the 5 being
exactly the new tests for the tie-break and the inactive connectors. Those 5
are expected to pass now, but that has not been checked.

Baseline before any change: the six gapfill test files passed (148 tests).

## What is left, in order

1. Run `tests/unit/test_gapfill_ptr.py` and fix whatever the last edit broke.
2. Read the benchmark result (see below) and compare the new coverage for
   components 1–4 with the old serial result.
3. Wire the stage in `src/thg_protocol/workflow/gapfill.py`
   (`compute-gapfill-coverage`, around line 611): pass `workers=None` (auto) or
   a configured value. **Until this is done the workflow still runs the
   candidate tests in one process**, because `compute_coverage` defaults to
   `workers=1`.
4. If a config key is added (suggested name `coverage_workers`, positive
   integer): add it to the allowed gapfill keys in
   `src/thg_protocol/workflow/config.py` (set near line 168), validate it,
   exclude it from `_parameters()` in `workflow/gapfill.py`, and exclude it
   from the `algorithm` fingerprint of `generate-gapfill-plan`. It must not
   change any fingerprint, since results do not depend on it.
5. Stage versions in `GapfillStage.__init__`: bump `generate-gapfill-plan`
   (6 → 7), because plans change (tie-break, dropped connectors). Do **not**
   bump `compute-gapfill-coverage`; its output is meant to be identical.
6. Check `tests/integration/test_gapfill_registered_workflow.py` and
   `tests/unit/test_gapfill_api.py` for assertions on connector counts or
   `candidate_coverage` statuses that the connector change affects.
7. Update the stale docstrings in `ptr.py`: the module docstring and
   `run_sink_milp` ("The result selects the connectors…").
8. Update docs: `docs/workflows/gapfill-sink-milp.md` (stage 3 test
   description, stage 4 MILP, open points on inactive connectors, timings),
   `docs/workflows/gapfill.md`, and `docs/reference/io-and-config.md` if a
   config key is added.
9. Run the full suite and ruff. Commit only when the user asks.

Environment: tests run with
`conda run -n thg_standalone --no-capture-output python -m pytest …`; ruff and
mkdocs exist only in the conda `base` environment.

## Design notes a continuer needs

- **Pre-check in `unblockable`.** For reactions whose sign is fixed by their
  bounds, one LP maximises the plain sum of their fluxes. A maximum below the
  threshold proves none can reach it, with no extra rows. It is skipped when
  any of those bounds is infinite, since the sum could be unbounded; LP7 then
  runs as before.
- **`model.solver.update()` in `_lp7`** is required. The old code flushed the
  pending rows by accident, through `reaction.forward_variable`.
- **Workers** rebuild the model from `model_to_dict` (exact floats, temporary
  sinks included) rather than pickling the optlang model, which round-trips
  through an LP file. Solver constraints that are not reactions are not
  carried over.
- **Auto worker count** (`workers=None`): one process per 64 candidate tests,
  capped at 8 and at the CPU count. Small models therefore stay serial.
- **Tie-break.** After the first solve, two constraints keep the covered count
  and the cost, and a second solve minimises the summed preference position
  (type A < B < C, then reaction ID). An exact tie in that sum is still
  possible in principle and is not detected.
- **Inactive connectors** are removed in a loop that re-verifies after each
  removal, so `verification` describes the final model.
  `verification["inactive_connectors"]` lists what was dropped. Status stays
  `solved`; it must not become `partial`, which blocks `gate-gapfill`.
- **Prefilter** ("skip candidates that cannot carry flux alone") was **not**
  implemented. After the overhead cut its expected gain is small, and it
  costs two LPs per candidate. Decide after seeing the benchmark.

## Measurements so far (run `thg-ws1-a`, 14,888 reactions, Gurobi)

- Old code: about 0.4 s per candidate test, 22,470 tests, roughly 2.5 h.
  Components 1–4 (9,535 tests) took 62 min in the interrupted run.
- Profile of one old test (0.44 s): 0.125 s in three LP solves, the rest in
  Python/optlang overhead.
- Each worker process uses about 560 MB; eight came to about 4.5 GB on a
  15 GB machine.
- New code: **no timing yet.** See the benchmark below.

Scientific findings from the same model are in the conversation summary, not
repeated here: 1 of 152 connectors carries flux without sinks; 1,227 of 3,328
blocked reactions are `sink_only`; single-transport coverage reaches 274 of
626 jointly unblockable targets in components 1–4.

## Background benchmark — check or kill it

A full-model run of the new `compute_coverage` with auto workers was started
with `nohup` and may still be running, holding eight worker processes:

```sh
pgrep -af bench.py          # is it running?
pkill -f bench.py           # stop it if not wanted
```

Scratch directory (session-specific, may be cleaned up):
`/tmp/claude-1000/-home-reinism-THG-The-Human-GEM-protocol-standalone/b42ed6c8-08df-4d37-ae1a-69a5ea9e2626/scratchpad/`

- `bench.py` — the benchmark; arguments: output file, worker count or `auto`,
  optional comma-separated component numbers.
- `bench.log` — per-component completion times and a `TOTAL` line.
- `cov-new.jsonl` — new coverage, one `ComponentCoverage` per line.
- `probe.py`, `probe2.py`, `probe.json`, `ceil.json` — the earlier
  measurements.

It ran on the code as it was before the tie-break and connector edit; the
coverage code has not changed since. The reference for the equality check is
`runs/thg-ws1-a/failed/compute-gapfill-coverage/attempt-0002/ptr-coverage.jsonl`
(components 1–4 from the old serial code; its first line is a fingerprint,
not a component). Old counts of candidates with coverage: 117, 63, 35, 37.
Coverage sets should match up to solver tolerance; any difference needs
explaining before the speedup is called exact.
