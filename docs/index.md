# THG Protocol

THG Protocol helps you construct, curate, assess, and compare human
genome-scale metabolic models (GEMs). It is designed for a workflow where you
keep ownership of your models, configurations, and resulting reports.

## What can I do with it?

- Build a model from normalized metabolite and reaction records.
- Improve an existing model with annotations, pathways, gapfill candidates, or
  content from another model.
- Check network connectivity and reaction balance, then compare versions of a
  model.
- Create a cell-specific model and summarize results in reports or figures.

## Start here

- Follow the [five-minute quickstart](quickstart.md) to create a small model.
- Read the [full workflow overview](workflow-overview.md) to see how the
  individual tasks fit together.
- Go straight to the [task guides](usage.md) if you already know what you need
  to do.

## How THG fits into a project

You can start from normalized records or from an existing JSON/SBML model.
Each workflow writes its result to a location you choose, so models and reports
can be reviewed and used as inputs to subsequent steps. Some capabilities,
such as live database lookups, optimization, and plotting, require optional
dependencies; their guides explain when they are needed.

For concrete input formats and data locations, see [data and model
files](data-and-model-files.md). For function-level details, use the [API
reference](api/index.md).

## Research use

Please cite [biosustain/THG](https://github.com/biosustain/THG) when using THG
in research.

Development, release, legacy, and repository-maintenance information is kept
in the [developer and maintainer section](development.md).
