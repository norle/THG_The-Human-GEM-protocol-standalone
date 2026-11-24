# Matched final-standard validation

Run the patched baseline and rebuilt B sequentially in `thg_standalone`.
The candidate SBML lacks subsystem names that the original baseline retains.
Its config explicitly supplies the 64 verified pseudo-subsystem exclusions
for the curated stoichiometric-consistency check. The MEMOTE suite runs on the
SBML files under MEMOTE's own validation semantics.

```sh
export OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2
for model in patched rebuilt-b; do
  python -c 'import runpy,sys; runpy.run_path("publication/ws1/run_build.py")["pin_solver"](); from thg_protocol.workflow.cli import main; sys.argv=["thg-run","validate",sys.argv[1],"-v"]; raise SystemExit(main())' "publication/ws4/matched-refresh/$model.json" > "publication/ws4/matched-refresh/$model.log" 2>&1
done
```

Run directories: `runs/publication-ws4-patched-memote` and
`runs/publication-ws4-rebuilt-b-memote`.

The first baseline attempt was stopped during the default MEMOTE subprocess
after the curated checks had completed. The candidate configuration omits
MEMOTE so its curated checks can finish independently. Use the two curated
validation reports for the matched quality table. MEMOTE scores have their
own benchmark pass and output files.

```sh
python publication/scripts/quality_table.py publication/ws4/matched-refresh/quality_table.csv \
  patched=runs/publication-ws4-patched-memote/artifacts/assemble-validation-report/attempt-0001/validation-report.json \
  rebuilt-b=runs/publication-ws4-rebuilt-b-memote/artifacts/assemble-validation-report/attempt-0001/validation-report.json
```

For the separate MEMOTE pass, run once per model with Gurobi, two solver
threads, one COBRA process and the MEMOTE default 10-second per-solver
timeout. Generate scores and HTML from the same raw result rather than
running the suite a second time to render it.

```sh
export OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2
run_memote() {
  model=$1
  out=$2
  mkdir -p "$out"
  python -c 'import runpy,sys; runpy.run_path("publication/ws1/run_build.py")["pin_solver"](); from memote.suite.cli.runner import cli; sys.argv=["memote","run","--solver","gurobi","--solver-timeout","10","--ignore-git","--filename",sys.argv[2],sys.argv[1]]; cli()' "$model" "$out/result.json" > "$out/run.log" 2>&1 &&
  python publication/scripts/score_memote_result.py "$out/result.json"
}
run_memote runs/human211-patched/Human_211_patched.xml publication/ws4/matched-refresh/memote-patched
run_memote runs/thg-ws1-b/artifacts/export-reference/attempt-0002/thg-reference.xml publication/ws4/matched-refresh/memote-rebuilt-b
```

## Matched check outcomes

Both curated reports completed. The table records blocked reactions (1,257
and 3,471), structural dead ends (623 and 3,651) and the passing curated
stoichiometric check in each model. The candidate's energy-cycle test was
unevaluable. Several cytosolic metabolites share each relevant MetaNetX
cross-reference after expansion. For example, the detailed candidate report
lists four matches for MNXM3. The table uses `n/a` for the skipped count.
See `quality_sources.json` for the curated report paths and checksums.

The MEMOTE status row of the quality CSV describes the original integrated
attempts. Paired MEMOTE scores should come from the separate pinned runs.

## Standalone MEMOTE checkpoint

At the 16:14 CET documentation check, the baseline log had advanced to the blocked-reaction test. Neither standalone score file was present, and the candidate run had yet to start. The baseline progress log is local at `memote-patched/run.log`.
