# Publication evidence and internal draft

The controlling scope is `docs/plans/publication-plan.md` (November 9–12
methods-led draft). Work is in progress. No gated final candidate, independent
replay or complete model-results draft is available yet. WS3 is deferred;
WS6 is dropped. Public release is deferred.

Run commands from the repository root in conda environment `thg_standalone`.
Gurobi requires access to its configured license service. Run memory-heavy
model jobs sequentially and check `free -m` first. Runtime is measured in task
JSON and workflow manifests; new-job estimates below are not measured results.

| Work | Regeneration command | Runtime / status |
|---|---|---|
| Model provenance | `python publication/scripts/pin_models.py` | seconds; file hashes only, no validation |
| WS0 patched tasks | `python publication/scripts/run_tasks.py runs/human211-patched/Human_211_patched.xml human211-patched publication/ws0/numerical-refresh` | 318.39 s; 21/21 VerifyModel, 57/57 Essential, Full 255 pass + 2 invalid |
| WS0 control | `python publication/scripts/run_tasks.py models/Human-GEM_2022-06-21.xml Human1 publication/ws0/numerical-refresh VerifyModel` | refresh pending |
| WS0 validation | `thg-run validate publication/ws0/validation-config-211-patched.json` | pending; potentially hours |
| WS1 corrected build | `thg-run resume runs/thg-ws1-a --force-step deduplicate-and-clean -v` | running from source `ac56d01`; earlier attempts preserved |
| WS1 fresh checkout | `thg-run reference publication/ws1/reference-a.json -v` | existing run resumes; full build not yet measured |
| WS1 independent replay | `thg-run reference publication/ws1/reference-b.json -v` | pending; frozen offline evidence still required |
| WS1 stage sizes/runtime | `python publication/scripts/stage_table.py runs/thg-ws1-a publication/ws1/current` | live checkpoint; pending/stale outputs omitted |
| WS1 stage task gate | `python publication/scripts/run_tasks.py MODEL STAGE publication/ws1/numerical-refresh VerifyModel` | pending corrected artifacts |
| WS1 corroboration | `THG_SOLVER=glpk python publication/scripts/run_tasks.py MODEL STAGE-glpk publication/ws1/numerical-refresh VerifyModel` | pending; separate solver retained in provenance |
| WS2 fix inventory | `publication/ws2/fixes.csv` | two archived model measurements: `python publication/scripts/measure_correctness.py`; third example pending |
| WS2 tests | `python -m pytest -m "not online" --ignore=tests/docs -q` | 350.38 s; 2,513 passed; `ws2/pytest-offline.log`; six docs checks passed separately |
| WS4 quality/coverage | matched baseline/candidate validation | pending candidate and VerifyModel gate; command not yet available |
| WS5 functional tasks | same `run_tasks.py` command on candidate, with all three tables | blocked on candidate; VerifyModel failure/unresolved result skips later tables |
| WS7 internal draft | `publication/manuscript/draft.md` | Introduction/Methods drafted; results, figures and evidence audit incomplete |

`run_tasks.py` reads pinned numerical settings from `benchmark_settings.json`
and exports detailed JSON as well as per-task CSV. Error outcomes remain
unresolved; unavailable residuals are null. Earlier `ws0/task_results_*.csv` and
`ws1/verifymodel/` results predate residual diagnostics and are historical,
not refreshed benchmark evidence. Task JSON records commit and working-diff
checksum; comparisons require the same source version and settings.

The model inventory records historical legacy-provenance claims as historical;
it does not re-establish their source-byte comparison. Input source-tag and
download-date information not available locally remains explicitly unknown.

No public tag, archive or hosted release was created.
