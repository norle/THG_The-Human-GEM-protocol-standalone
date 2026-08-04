# Gapfill

## What this workflow is for

Find compartment-specific dead ends that can be connected by transport
reactions, review candidates, and write a revised JSON model with decision
reports.

## When not to use it

Do not use gapfill to add a defined biological pathway; use
[pathway implementation](pathway.md). It also does not replace
[network analysis](network-analysis.md) for diagnosing general connectivity.

## Prerequisites and inputs

The input JSON mapping contains `metabolites` and `reactions`. Choose an
output directory and, when needed, an `allowed_connections` policy.

## Python API

Run the complete workflow with [`run_pipeline`][thg_protocol.gapfill.core.run_pipeline],
or review phases using [`generate_candidates`][thg_protocol.gapfill.core.generate_candidates],
[`run_phase1`][thg_protocol.gapfill.core.run_phase1],
[`run_phase2`][thg_protocol.gapfill.core.run_phase2], and
[`run_phase3`][thg_protocol.gapfill.core.run_phase3].

## CLI

```bash
thg-gapfill --model model.json --output-dir results/gapfill
```

## Outputs

The output directory contains candidate, phase-summary, selection, and final
model files. No input model is mutated.

## Common errors

An empty candidate file means no compatible cross-component metabolite pair was
found. Check compartment suffixes and the allowed connection policy.

## Next workflow

Run [network analysis](network-analysis.md) on the revised model, or compare
it with the previous version using [model comparison](comparison.md).
