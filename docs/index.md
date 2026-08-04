# THG Protocol

THG Protocol is a Python package and command-line toolset for constructing,
curating, analysing, and comparing human genome-scale metabolic models (GEMs).

## What it does

- Reconstruct a COBRA model from normalized metabolite and reaction records.
- Annotate model metabolites, reactions, and gene--protein--reaction (GPR)
  rules.
- Add configured pathways, identify transport gapfill candidates, and merge
  model content.
- Check network connectivity, reaction balance, and redundant reactions.
- Compare model versions, derive cell-specific models, and produce reports or
  SVG figures.

## Inputs and outputs

The tools accept normalized records, JSON or SBML models, and, for specific
operations, pathway configurations or measurement data. They write models,
CSV reports, caches, and optional SVG figures to paths supplied by the caller.
Format and dependency requirements are documented in each task guide.

## Choose an operation

| If you need to... | Use |
| --- | --- |
| Create a model from records | [Model reconstruction](workflows/database.md) |
| Add or inspect biological annotations | [Annotation](workflows/annotation.md) |
| Change model content | [Pathway implementation](workflows/pathway.md), [gapfill](workflows/gapfill.md), or [merge](workflows/merge.md) |
| Inspect or compare models | [Network analysis](workflows/network-analysis.md) or [model comparison](workflows/comparison.md) |
| Create a reduced model or visual output | [Cell-specific models](workflows/cell-specific.md) or [figures and reports](workflows/figures.md) |

## Start here

- Follow the [five-minute quickstart](quickstart.md) to reconstruct a small
  model.
- Use the [task guides](usage.md) as the canonical task chooser.
- Read the [workflow overview](workflow-overview.md) for the input-to-output
  map after choosing a task.
- Use the [API reference](api/index.md) for Python interfaces and the
  [installation guide](installation.md) for optional dependencies.

## Research use

Please cite [biosustain/THG](https://github.com/biosustain/THG) when using THG
in research.

Development, release, legacy, and repository-maintenance information is kept
in the [developer and maintainer section](development.md). Internal planning
records are kept in the repository but are not published in the site.
