# Model comparison

!!! info "Status: Supported"
    Model comparison APIs and the `thg-compare` CLI are maintained and covered
    by current tests.

## Outcome

Describe reaction, compartment, identifier, and stoichiometric differences
between two model files without mutating either input.

## Place in the THG protocol

Supporting review operation after each protocol checkpoint; comparison is not
the structural merge itself.

## When to use it

Use it to review curation, enrichment, gapfill, or merge changes.

## When not to use it

Use [merge](merge.md) when the goal is to combine compatible model content, or
[network analysis](network-analysis.md) for connectivity and balance.

## Inputs

Two JSON or SBML model paths and an optional output directory. The comparison
mapping includes raw and, by default, no-blocked views.

## Requirements

Local model I/O. Blocked-reaction filtering can use a solver through COBRA;
avoid it or configure the environment when it is not available.

## Run from the command line

```bash
thg-compare results/model-a.json results/model-b.json \
  --output-dir results/comparison
```

## Run from Python

```python
from thg_protocol.analysis.compare import compare_models_from_files

reports = compare_models_from_files(
    "results/model-a.json",
    "results/model-b.json",
    "results/comparison",
)
print(reports["raw"]["_summary"])
```

## Outputs

Returns a comparison mapping and, when an output directory is supplied, writes
`compartments_comparison_raw.csv` and `compartments_comparison_no_blocked.csv`.
Inputs are read-only.

## Inspect the result

Review summary counts, IDs only in each model, stoichiometric matches, and
compartment-specific differences. Save the input checksums with the CSVs.

## Common problems

Missing files or unsupported suffixes indicate an I/O issue. Large apparent
differences can be namespace or compartment differences; compare annotations
before treating them as new biology.

## Next step

Use [merge](merge.md) for compatible content or [figures](figures.md) to
present comparison summaries.

## API reference

[`compare_models_from_files`][thg_protocol.analysis.compare.compare_models_from_files]
is the explicit file-based entry point.

## Differences from the historical workflow

The current comparison API has explicit output ownership and optional CSV
writing; it does not establish historical model equivalence.
