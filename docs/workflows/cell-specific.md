# Cell-specific models

!!! info "Status: Partial"
    CSV/MAT activity reduction and transcriptomic helpers are maintained and
    tested, but a complete publication-style cell-specific workflow is not an
    automatic THG construction stage.

## Outcome

Reduce a model using activity data and retain a caller-owned report of removed
and retained reactions.

## Place in the THG protocol

Optional downstream analysis after a general model is curated; it is not a
mandatory stage in every THG construction.

## When to use it

Use a prepared activity matrix when a cell- or tissue-specific model is the
scientific question.

## When not to use it

Do not use reduction to repair a general model or replace pathway curation,
merge, or validation.

## Inputs

Provide a COBRA model and a matrix-like value, CSV, or MAT activity file. Gene
annotation/transcript helpers accept explicit model/XML paths as documented by
the API.

## Requirements

Basic reduction accepts CSV/MAT without Troppo. Some methods need the
`cell-specific` extra and a solver; no network or credentials are implicit.

## Run from the command line

No installed cell-specific CLI exists. Use Python.

## Run from Python

```python
from cobra.io import load_json_model
from thg_protocol.cell_specific import reduce_model_by_activity

model = load_json_model("results/model.json")
tailored, report = reduce_model_by_activity(
    model,
    "inputs/activity.csv",
    output_path="results/cell-specific/model.json",
)
print(report.retained_reactions, report.removed_reactions)
```

## Outputs

Returns a copied model and `ActivityReductionReport`, and writes only the
explicit JSON/SBML path. The input model and activity file are not mutated; no
cache is created.

## Inspect the result

Review threshold/sample metadata, retained and removed reactions, orphan
metabolites, and whether boundary reactions were preserved as intended.

## Common problems

Wrong matrix orientation or missing activity values can remove unexpected
reactions. Check sample order, gene IDs, and the chosen threshold before
interpreting the report.

## Next step

Run [network analysis](network-analysis.md) on the tailored model and use
[figures](figures.md) for presentation.

## API references

[`reduce_model_by_activity`][thg_protocol.cell_specific.reduce_model_by_activity],
[`match_exchange_reactions`][thg_protocol.cell_specific.exchange.match_exchange_reactions],
[`extract_gene_annotation_pairs`][thg_protocol.cell_specific.transcriptomics.extract_gene_annotation_pairs],
[`extract_sgpr_rules`][thg_protocol.cell_specific.transcriptomics.extract_sgpr_rules],
and [`replace_gene_symbols`][thg_protocol.cell_specific.transcriptomics.replace_gene_symbols].

## Differences from the historical workflow

The current reduction helper is a maintained local building block; historical
solver-heavy cell-specific orchestration is not implied.
