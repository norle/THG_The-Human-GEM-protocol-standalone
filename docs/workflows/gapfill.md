# Gapfill

`thg_protocol.gapfill` provides a deterministic JSON phase 1→2→3 workflow.
It accepts an input model and writes CSV selections plus a final model only
under the caller-provided output directory:

```bash
thg-gapfill --model model.json --output-dir results/gapfill
```

For library callers, use `run_pipeline(model_path, output_dir)` or call
`generate_candidates`, `run_phase1`, `run_phase2`, and `run_phase3` separately.
The legacy COBRA strategy script remains available while its solver-specific
report contract is being characterized.
