# Cell-specific models

## What this workflow is for

Derive a model for a cell type from an activity matrix and report which
reactions were retained. The input model is copied rather than mutated.

## When not to use it

Do not use this workflow for simple model comparison or for changing a
pathway definition. Use [model comparison](comparison.md) or
[pathway implementation](pathway.md) instead.

## Prerequisites and inputs

Activity rows must follow model reaction order. CSV and MAT inputs are
supported; MAT files use `all_Solutions_matrix5` by default. Install the
optional extra for solver-backed GIMME/Troppo methods:

```bash
python -m pip install 'thg-protocol[cell-specific]'
```

## Python API

Reduce a model with [`reduce_model_by_activity`][thg_protocol.cell_specific.reduce_model_by_activity]:

```python
from thg_protocol.cell_specific import reduce_model_by_activity

tailored, report = reduce_model_by_activity(
    model, "results/activity.csv", presence_threshold=0.0,
    output_path="results/tailored.xml",
)
```

Boundary matching uses [`match_exchange_reactions`][thg_protocol.cell_specific.exchange.match_exchange_reactions].
Transcriptomics helpers are [`extract_gene_annotation_pairs`][thg_protocol.cell_specific.transcriptomics.extract_gene_annotation_pairs],
[`extract_sgpr_rules`][thg_protocol.cell_specific.transcriptomics.extract_sgpr_rules],
and [`replace_gene_symbols`][thg_protocol.cell_specific.transcriptomics.replace_gene_symbols].

## Outputs

The result is a copied model and an
[`ActivityReductionReport`][thg_protocol.cell_specific.ActivityReductionReport].
Transcriptomics helpers return transformed rules and mappings.

## Common errors

A row-count error means matrix and model order do not match. A MAT input must
contain `all_Solutions_matrix5` unless `matrix_key` is changed.

## Next workflow

Run [network analysis](network-analysis.md) on the tailored model, then use
[figures and reports](figures.md) for presentation output.
