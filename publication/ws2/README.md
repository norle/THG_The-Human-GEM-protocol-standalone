# WS2: correctness fixes and engineering comparison (partial)

Status (2026-11-09): measured identity/parent-balance examples, whole-baseline
location-policy ablation, numerical controls and the actual historical numerical
artifact are saved. Final candidate evaluation remains incomplete.
`fixes.csv` covers October changes, the November audits and subsequent safeguards,
with evidence strength and reasons for deferred measurements. `engineering.csv`
includes the new offline test run; legacy line counts and runtime comparisons
remain pending. Broad legacy attribution is deferred for the internal draft.

## Numerical prerequisite verification (2026-11-09)

`pytest-offline.log`: 2,513 passed, 1,254 warnings, 350.38 s. Command:
```sh
python - <<'PYTEST' > publication/ws2/pytest-offline.log 2>&1
import cobra, pytest
cobra.Configuration().solver = "glpk"
raise SystemExit(pytest.main(["-m", "not online", "--ignore=tests/docs", "-q"]))
PYTEST
```

GLPK is the default for this offline check; solver-specific tests may select
Gurobi and require its license service. The docs tests are excluded because
MkDocs lives in the base environment. This is test evidence, not full-model
benchmark evidence. Additional focused runner/importer/publication tests after
checksum validation: 69 passed. Three measured correctness examples remain
pending; the historical inventory above is not upgraded by these tests.

## Archived real-model measurements

`python publication/scripts/measure_correctness.py` writes `correctness.json`
with source-artifact SHA-256 values and individual metabolite/reaction rows.
All 11 previous consolidation pairs conflict in shared database identifiers.
The archived expansion plan contains 26 copies of 14 unbalanced parents; all
26 match explicit `unbalanced-parent` exclusions in the revised archived plan.
Eleven parents have charge-only imbalance. These are real-model proposal
measurements, not final-model or functional outcomes. The identity defect was
introduced by the redesign; the parent imbalances are inherited. The original
B1 narrative row remains historical and is not treated as refreshed task evidence.
The numerical case and corrected end-to-end effects remain pending.

## Supplement inventory scope

`fixes.csv` now expands the October fixes, all 20 November 3 audit resolutions,
the November 4 nested-expression/cycle/resume fixes (`cef04ea`), and the later
identity/parent-balance/numerical safeguards. Scientific and engineering changes
retain explicit evidence strength and a reason when impact is unmeasured.
Historical narrative counts have not been promoted to current measurements.

## Documentation checks (2026-11-09)

- Base environment: `python -m pytest tests/docs/test_documentation.py -q` —
  3 passed; strict site build, navigation, links and canonical API checks.
  Saved log: `pytest-docs.log`.
- `thg_standalone` with GLPK default: `python -m pytest
  tests/docs/test_examples.py tests/docs/test_practical_quickstart.py -q` —
  3 passed in 60.01 s; CLI subprocesses had Gurobi license access.
  Saved log: `pytest-doc-examples.log`.

These six documentation checks supplement, rather than change the count in,
the earlier 2,513-test offline run.

## Numerical case study (prepared; results pending)

`python publication/scripts/measure_task_numerics.py` compares direct task
construction and COBRA's Gurobi LP-copy construction on the corrected beta1
export and an archived beta2 export, with GLPK corroboration. It uses only
VerifyModel task 21 under the pinned medium, forced-flux relaxation, mapping,
tolerances and native Gurobi threads. It is not the complete VerifyModel gate.
Runtime assertions check the task definition and that task contexts restore
model bounds, metabolite/reaction IDs and the objective. Results are saved
after each solve in `task_numerics.json`; input/script/runner checksums and
solver diagnostics are retained. A reliable feasible result on the current
beta1 sets an investigation flag and stops the experiment. No biochemical
model modification is performed.

Cold construction probe: `task_numerics_cold.json` and
`task-numerics-cold.log` record six infeasible task-21 solves (both models;
Gurobi direct/copy and GLPK copy), with no current-model investigation flag.
The historical numerical artifact was not reproduced in those cold trials.
The artifact records the exact script commit/hash. This negative result does
not establish absence of numerical instability during sequential tasks.

Protocol 2 extends the same command to cold versus sequential VerifyModel
evaluation and a labelled control reenacting the previous publication runner's
unsupported thread attribute under native default zero. That control is not a
pinned benchmark condition. Full sequential task reports are retained; the
corrected beta1 runs under native two-thread Gurobi and GLPK can also serve as
stage-gate evidence. The protocol has 12 planned experiments and stops early
if any current-beta1 task has a reliable feasible outcome. The task/core-source
hashes, input hashes and model-restoration assertions remain part of the record.

## Final shutdown results

`gene_locations.json` and `gene_locations.csv`: all 2,870 baseline-derived
genes have evidence records. Under the historical standalone rejection rule,
1,613 retain mapped targets; the current rule retains 2,461, including 848
multi-location genes that would previously be rejected. 409 have no mapped
target. Regenerate with `python publication/scripts/measure_locations.py`.
This is a policy ablation on identical current evidence, not a legacy lookup
execution; legacy attribution is not established.

`task_numerics.json`: protocol 2 completed 12 experiments / 132 infeasible
solves in 324.92 s. These are negative controls on corrected beta1 and the
historically passing beta2 attempt 2. They do not test the historically failing
beta1 artifact. Native parameter zero is automatic thread selection, not zero
workers. Corrected beta1 passes all 21 VerifyModel tasks with Gurobi and GLPK.

The actual failing beta1 artifact (attempt 1, SHA-256 `fb081fa8…07f5b1`) was
then tested with:
```sh
python publication/scripts/run_tasks.py runs/thg-ws1-a/artifacts/export-beta1/attempt-0001/thg-beta1-candidate.json archived-beta1 publication/ws2/historical-failure VerifyModel
```
It gives 20 passes and one numerical error in 42.92 s. Task 21 reports optimal
with maximum bound violation **3.0275567736916796e-7**, constraint violation
0, native Threads=2 and tolerance 1e-7. The new harness returns unresolved with
no biological outcome. This reproduces the numerical artifact; it is not a
confirmed biochemical leak. Results: `historical-failure/`; raw console:
`historical-beta1.log`. GLPK corroboration of this exact artifact is pending.

The reference resume regression failed before `9174aea` and passes afterward;
33 related workflow/artifact/publication checks passed (one Gurobi-marked test
excluded). The final archive/localization check selection passed 13 tests,
with one Gurobi test excluded. Full suite has not been repeated after these
latest changes. The build was stopped cleanly for shutdown; see the handoff.
