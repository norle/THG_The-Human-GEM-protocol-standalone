# From records to a usable human GEM

THG Protocol supports a model-building workflow in which each stage produces a
model or report that you can inspect, keep, and use in the next stage. You do
not need every stage: start with the input you have and choose the operations
that answer your biological question.

```text
records or an existing model
            |
            v
build or prepare a model
            |
            +--> annotate (when identifiers or GPRs are incomplete)
            |
            v
curate the network: add pathways, close gaps, or merge content
            |
            v
check and compare the result
            |
            +--> tailor to a cell type
            |
            v
share reports and figures
```

## 1. Start with your input

Choose the route that matches what you already have.

| If you have... | Use THG Protocol to... | Output |
| --- | --- | --- |
| Normalized metabolite and reaction records | [Reconstruct a model](workflows/database.md) | A new JSON or SBML model |
| A JSON or SBML model | [Build or enrich it](workflows/model-build.md) | An annotated model and optional error report |
| Two models | [Compare them](workflows/comparison.md) before deciding what to retain | Per-compartment CSV reports |

The [quickstart](quickstart.md) demonstrates the smallest version of the
record-to-model route with an offline example.

## 2. Make the model more informative

Use [annotation](workflows/annotation.md) when you need to inventory existing
identifiers, fill in metabolite or reaction annotations, or resolve gene–protein–reaction
(GPR) rules. Annotation can be part of model building or a focused task on an
existing model. Lookups that use external resources are supplied explicitly,
so you stay in control of the data sources and credentials.

## 3. Curate the network

Choose one or more curation steps depending on the change you want to make.

| Goal | Workflow | What it does |
| --- | --- | --- |
| Add a known biological process | [Pathway implementation](workflows/pathway.md) | Applies reactions and compartments from your pathway configuration to a JSON model. |
| Connect compatible compartment-specific metabolites | [Gapfill](workflows/gapfill.md) | Proposes and selects transport candidates, then writes a revised JSON model. |
| Combine complementary models | [Merge](workflows/merge.md) | Creates a merged copy and records which content was added or retained. |

Save the output from each curation step as the input to the next one. This
makes it straightforward to review changes and reproduce the sequence later.

## 4. Check the result

Use [network analysis](workflows/network-analysis.md) to find disconnected
components, compact redundant reactions, and check formula-based balance.
Use [model comparison](workflows/comparison.md) to quantify how a curated
model differs from a reference or an earlier version. For an optional broader
quality assessment, run [MEMOTE and task analysis](workflows/memote.md).

These checks answer different questions: connectivity finds isolated parts of
the network; balance identifies reactions with inconsistent formulas; and
comparison identifies changed reaction content.

## 5. Adapt and communicate

When expression or activity measurements are available, create a focused model
with the [cell-specific workflow](workflows/cell-specific.md). Then use
[figures and reports](workflows/figures.md) to summarize models and render
publication-ready SVG figures.

## A practical first pass

For many projects, the shortest useful route is:

1. Reconstruct a model from records, or load an existing model.
2. Add one pathway or run gapfill for a defined connectivity problem.
3. Check balance and connected components.
4. Compare the result with the starting model.
5. Save the model and reports together in a project results directory.

The [task guides](usage.md) help you jump directly to an individual operation;
the [API reference](api/index.md) is useful when you are ready to automate the
same workflow in Python.
