# Cell-specific models

Use the dependency-light core to reduce a model from an activity matrix; use
the optional Troppo workflows only when their solver and expression semantics
are required.

The dependency-light tailoring core is available without Troppo:

```python
from thg_protocol.cell_specific import reduce_model_by_activity

tailored, report = reduce_model_by_activity(
    model,
    "results/activity.csv",
    presence_threshold=0.0,
    output_path="results/tailored.xml",
)
```

Activity rows must follow the model reaction order. CSV and MAT inputs are
supported; MAT files use the `all_Solutions_matrix5` key by default. The
optional extra remains required for GIMME/Troppo workflows.

Boundary reaction bounds can be matched without annotation services or a
solver:

```python
from thg_protocol.cell_specific import match_exchange_reactions

tailored, matched, unmatched, inconsistent = match_exchange_reactions(
    model_new, model_base, add_reactions=False
)
```

Dependency-light transcriptomics transformations are also available without
loading the legacy Troppo/GIMME orchestration:

```python
from thg_protocol.cell_specific import (
    extract_gene_annotation_pairs,
    extract_sgpr_rules,
    replace_gene_symbols,
)

pairs = extract_gene_annotation_pairs("inputs/model.xml")
rules = extract_sgpr_rules(model)
mapped_rules = replace_gene_symbols(model, pairs)
```

These helpers return transformed rules and mappings; they do not mutate the
model or access external services. Solver-backed expression workflows remain
explicit and require the optional extra.

Cell-specific model generation depends on the optional `cell-specific` extra:

```bash
python -m pip install 'thg-protocol[cell-specific]'
```

Keep downloaded model inputs and generated outputs outside the source tree.
Characterize external service calls with static fixtures; the package APIs do
not make live requests implicitly.

## Prerequisites, output, and troubleshooting

Activity rows must exactly follow reaction order. The output is a copied model
and an `ActivityReductionReport`; no input model is mutated. A row-count error
means the matrix and model order do not match. A MAT input must contain
`all_Solutions_matrix5` unless `matrix_key` is changed.
