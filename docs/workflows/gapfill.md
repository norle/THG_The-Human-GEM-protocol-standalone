# Gapfill

`thg_protocol.gapfill` provides a deterministic JSON phase 1→2→3 workflow.
Use it when a mapping model has compartment-specific dead ends that can be
connected by transport candidates.
It accepts an input model and writes CSV selections plus a final model only
under the caller-provided output directory:

```bash
thg-gapfill --model model.json --output-dir results/gapfill
```

For library callers, use `run_pipeline(model_path, output_dir)` or call
`generate_candidates`, `run_phase1`, `run_phase2`, and `run_phase3` separately.
The former solver-heavy checkout strategy scripts were retired. Solver-backed
experiments remain opt-in and are not part of the default release gate.

## Prerequisites, output, and troubleshooting

The input is a JSON mapping with `metabolites` and `reactions`. The output
directory contains candidate, phase-summary, selection, and final-model files.
The default example is deterministic and requires no solver or network access.
An empty candidate file means no compatible cross-component metabolite pair was
found; use the Python API's `allowed_connections` to restrict or expand the
intended compartment pairs.
