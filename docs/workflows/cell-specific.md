# Cell-specific workflow

In the canonical pipeline, run `cell-specific` after the final release gate and
use the validated **Final THG** as its parent model. The workflow accepts an
explicitly versioned source GEM rather than implicitly discovering an upstream
artifact.

It may also run independently from an explicitly declared external GEM. That
standalone mode must preserve the external model's identity, checksum, and
provenance and must not imply that the parent is a Final THG.

The run records expression evidence, identifier mapping, GPR activity,
proposal-first reduction decisions, exchange settings, validation, and JSON/XML
model exports. Missing genes default to `uncertain-retain`; use `inactive` or
`reject` explicitly when that policy is scientifically justified.

```json
{
  "workflow": "cell-specific",
  "run": {"name": "cell", "output_dir": "../runs/cell"},
  "cell_specific": {
    "input_model": "../inputs/models/final-thg.json",
    "expression_file": "../inputs/expression.jsonl",
    "gene_identifier_namespace": "Ensembl",
    "activity_strategy": "gpr-threshold",
    "unknown_gene_policy": "uncertain-retain",
    "validation_profile": "structural-fast"
  }
}
```
