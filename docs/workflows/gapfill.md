# Gapfill

Use gapfill when a JSON model has compartment-specific dead ends that may be
connected by transport reactions. The workflow proposes compatible transport
candidates, selects a set of additions, and writes both the decision reports
and the revised model:

```bash
thg-gapfill --model model.json --output-dir results/gapfill
```

Use `run_pipeline(model_path, output_dir)` in Python for the complete workflow,
or call `generate_candidates`, `run_phase1`, `run_phase2`, and `run_phase3`
when you want to review or control each phase yourself.

## Prerequisites, output, and troubleshooting

The input is a JSON mapping with `metabolites` and `reactions`. The output
directory contains candidate, phase-summary, selection, and final-model files.
An empty candidate file means no compatible cross-component metabolite pair was
found. Use the Python API's `allowed_connections` to restrict or expand the
intended compartment pairs.
