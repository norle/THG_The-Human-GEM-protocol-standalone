# THG Protocol

THG is a Python package and command-line toolkit for building and validating
human genome-scale metabolic models (GEMs).

[Installation](installation.md) · [Quickstart](quickstart.md) · [Workflow overview](workflows/index.md)

## Choose a starting point

- New here? Run the offline [quickstart](quickstart.md).
- Have a model or evidence ready? [Choose a workflow](workflows/index.md).
- Looking for exact options? Use the [CLI](reference/cli.md) or
  [configuration reference](reference/io-and-config.md).

## What you can build

```mermaid
flowchart LR
    A[THG reference model] --> B[Cell-specific model]
```

Build and release the [THG reference model](workflows/final-thg.md), then use
it to generate a [cell-specific model](workflows/cell-specific.md). The
detailed construction stages remain available in the
[workflow overview](workflows/index.md).

THG implements the workflow described in the [2023 protocol
paper](https://doi.org/10.3390/bioengineering10050576). Reproducing a published
artifact also requires the original inputs, configuration, and provenance.
