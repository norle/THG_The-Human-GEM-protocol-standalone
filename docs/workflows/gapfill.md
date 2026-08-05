# Gapfill

!!! info "Status: Supported"
    The deterministic JSON gapfill pipeline and `thg-gapfill` CLI are maintained
    and covered by current tests.

## Outcome

Find compartment-crossing transport candidates, select minimal connectors, and
write a revised JSON model plus phase reports.

## Place in the THG protocol

Supporting operation for structural gaps; it is not a mandatory stage in every
published THG construction.

## When to use it

Use it after diagnosing compartment-specific dead ends and when candidate
transport reactions are an appropriate scientific repair.

## When not to use it

Do not use it as a replacement for curated pathway implementation or general
network diagnosis; use [network analysis](network-analysis.md) first.

## Inputs

Input is a JSON mapping with `compartments`, `metabolites`, and `reactions`.
`max_additions` bounds phase-three additions.

## Requirements

Local JSON only. No network, credentials, or solver is implicit. The pipeline
writes under the caller-selected directory and mutates only its loaded copy.

## Run from the command line

```bash
thg-gapfill --model docs/examples/quickstart_model.json \
  --output-dir results/gapfill
```

## Run from Python

```python
from thg_protocol.gapfill import run_pipeline

result = run_pipeline(
    "docs/examples/quickstart_model.json",
    "results/gapfill",
    max_additions=1,
)
print(result["model"])
```

## Outputs

Writes `candidates_all.csv`, phase selection CSVs, and `gapfilled_model.json`;
returns their paths and selected rows. The source model is not overwritten.

## Inspect the result

Review every candidate and selected connector, then check components and
balances on `gapfilled_model.json`.

## Common problems

No candidates usually means the model's compartment suffixes or reaction
metabolite IDs do not match the supported JSON shape. A large selection should
be reviewed rather than accepted automatically.

## Next step

Run [network analysis](network-analysis.md) and compare the original and
gapfilled models.

## API references

[`generate_candidates`][thg_protocol.gapfill.core.generate_candidates],
[`run_phase1`][thg_protocol.gapfill.core.run_phase1],
[`run_phase2`][thg_protocol.gapfill.core.run_phase2],
[`run_phase3`][thg_protocol.gapfill.core.run_phase3], and
[`run_pipeline`][thg_protocol.gapfill.core.run_pipeline].

## Differences from the historical workflow

This is a deterministic package pipeline for JSON transport candidates, not the
complete curation or merge loop from the 2023 protocol paper.
