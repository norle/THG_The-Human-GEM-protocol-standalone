# Cell-specific workflow

`cell-specific` is an independent workflow. It accepts a versioned source GEM
and pre-normalized expression evidence; it does not implicitly consume β1, β2,
gapfill, or Final THG.

The run records expression evidence, identifier mapping, GPR activity,
proposal-first reduction decisions, exchange settings, validation, and JSON/XML
model exports. Missing genes default to `uncertain-retain`; use `inactive` or
`reject` explicitly when that policy is scientifically justified.

```json
{
  "workflow": "cell-specific",
  "run": {"name": "cell", "output_dir": "../runs/cell"},
  "cell_specific": {
    "input_model": "../inputs/models/model.json",
    "expression_file": "../inputs/expression.jsonl",
    "gene_identifier_namespace": "Ensembl",
    "activity_strategy": "gpr-threshold",
    "unknown_gene_policy": "uncertain-retain",
    "validation_profile": "structural-fast"
  }
}
```
