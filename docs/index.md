# THG Protocol

THG is a Python package and command-line toolkit that turns a general human
genome-scale metabolic model (GEM) into a curated reference model, then derives
cell-specific models by integrating transcriptomics data. Each workflow
records validation results, checksums, and provenance so the model's lineage can
be inspected and reproduced.

[Installation](installation.md) · [Quickstart](quickstart.md) · [Workflow overview](workflows/index.md)

## Choose a starting point

- New here? Run the offline [quickstart](quickstart.md).
- Have a model or evidence ready? [Choose a workflow](workflows/index.md).
- Looking for exact options? Use the [CLI](reference/cli.md) or
  [configuration reference](reference/io-and-config.md).

## What THG does

```mermaid
flowchart TB
    subgraph reference[Build the THG reference model]
        direction LR
        A([Human reference GEM]) --> B[Curate reactions and annotations<br/>THGβ1]
        B --> C[Expand gene rules and locations<br/>THGβ2]
        C --> F[Gapfill]
        C -. optional .-> D[Integrate Human Database evidence]
        E([Human Database model]) --> D
        D --> F
        F --> G[Validate]
        G --> H([Validated THG reference model])
    end

    subgraph context[Build a cell-specific model]
        direction LR
        H --> I[Integrate transcriptomics data]
        I --> J[Reduce and validate]
        J --> K([Validated cell-specific model])
    end
```

Rounded nodes are models; rectangular nodes are workflow stages.

The reference workflow curates model content, expands biological evidence,
optionally integrates the Human Database, fills network gaps, and applies the
final validation boundary. The cell-specific workflow integrates transcriptomics
data while preserving the parent model and selecting the reactions supported by
a tissue or cell's evidence.

See the [workflow overview](workflows/index.md) for the available commands and
the current release-handoff boundary, or go directly to the
[cell-specific workflow](workflows/cell-specific.md) when you already have a
released reference model.

THG implements the workflow described in the [2023 protocol
paper](https://doi.org/10.3390/bioengineering10050576). Reproducing a published
artifact also requires the original inputs, configuration, and provenance.
