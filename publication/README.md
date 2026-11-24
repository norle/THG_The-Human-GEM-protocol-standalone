# Publication evidence and internal draft

- [November 23 progress and handoff](HANDOFF-2026-11-23.md)
- [Publication plan](../docs/plans/publication-plan.md)
- [Bullet-point manuscript draft](manuscript/draft.md)
- [Table 1 source](manuscript/table1.csv) and [figure sources](figures/README.md)
- [Pinned models](models.json) and [benchmark settings](benchmark_settings.json)

Run from the repository root in `thg_standalone`. The Gurobi analyses need
access to the configured license service. Run memory-heavy validation jobs
sequentially. The November 9 acquisition shutdown is recorded in the
[historical handoff](HANDOFF-2026-11-09.md).

| Work | Regeneration and evidence |
|---|---|
| Model identity | `python publication/scripts/pin_models.py`. The original THG asset is verified against the paper's S2 supplement in [WS3](ws3/README.md) |
| Patched baseline tasks | `python publication/scripts/run_tasks.py runs/human211-patched/Human_211_patched.xml human211-patched publication/ws0/pinned-refresh`. Native threads, solver tolerances and residuals are in the JSON |
| Unpatched recheck | `python publication/scripts/run_tasks.py inputs/models/Human_211.xml human211-unpatched publication/ws0/unpatched-recheck VerifyModel` |
| Rebuilt B and replay C | `python publication/ws1/run_build.py publication/ws1/reference-b-frozen.json` and the corresponding `reference-c-frozen.json`. See [build comparison](ws1/replay-b-vs-c/README.md) for source commits, limits and comparison command |
| Correctness and localisation | [WS2 evidence](ws2/README.md), [fix inventory](ws2/fixes.csv) and [compartment ablation](ws2/compartment-resolution/README.md) |
| HPA model comparison | [Input provenance, command and summary](ws2/hpa/README.md) |
| Gapfill | [Version 6/7 comparison](ws1/gapfill-change/README.md) and pinned follow-up commands below |
| Format consistency | [SBML and JSON comparison with shared exclusions](ws4/consistency/README.md) |
| Matched validation | [Configuration, commands and output status](ws4/matched-refresh/README.md) |
| Figures 2–4 and Table 1 | `python publication/scripts/plot_update_results.py` |

## Solver-backed follow-up commands

```sh
export OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2
run_pinned() {
  python -c 'import runpy,sys; runpy.run_path("publication/ws1/run_build.py")["pin_solver"](); sys.argv=sys.argv[1:]; runpy.run_path(sys.argv[0],run_name="__main__")' "$@"
}
run_pinned publication/scripts/measure_gapfill_selection_ablation.py
run_pinned publication/scripts/recheck_gapfill_coverage.py runs/thg-ws1-b publication/ws1/reference-b-frozen.json publication/ws1/gapfill-change/serial
python publication/scripts/run_tasks.py runs/thg-ws1-b/artifacts/export-reference/attempt-0002/thg-reference.json b-rebuilt-final-verify publication/ws1/rebuild-b/gates VerifyModel
```

## Structural coverage

```sh
python -c 'import cobra,runpy,sys; cobra.Configuration().solver="glpk"; sys.argv=sys.argv[1:]; runpy.run_path(sys.argv[0],run_name="__main__")' \
  publication/scripts/measure_coverage.py \
  runs/human211-patched/Human_211_patched.xml \
  runs/thg-ws1-b/artifacts/export-reference/attempt-0002/thg-reference.json \
  runs/thg-ws1-b/artifacts/generate-gapfill-plan/attempt-0002 \
  runs/thg-ws1-b/artifacts/resolve-compartment-evidence/attempt-0001/beta2-compartment-resolution-evidence.json \
  publication/ws4/coverage-rebuilt-b
```

The structural coverage script uses GLPK to load the models and performs no
optimization. Flux-capability counts come from the Gurobi construction report.
