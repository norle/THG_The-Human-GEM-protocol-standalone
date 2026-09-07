# Cell-specific workflow

In the canonical pipeline, run `cell-specific` after the final release gate and
use the released **THG reference model** as its parent model. The workflow accepts an
explicitly versioned source GEM rather than implicitly discovering an upstream
artifact.

It may also run independently from an explicitly declared external GEM. That
standalone mode must preserve the external model's identity, checksum, and
provenance and must not imply that the parent is a THG reference model.

The run records expression evidence, identifier mapping, GPR activity,
proposal-first reduction decisions, exchange settings, validation, and JSON/XML
model exports. It supports three deliberately distinct strategies:

- `gimme`: native solver-agnostic reconstruction from per-sample expression;
  emits reaction scores, GIMME results, sample status, an ID-labeled activity
  matrix, and consensus evidence. This is the recommended legacy-compatible path.
- `gpr-threshold`: lightweight deterministic baseline; it is not GIMME.
- `activity-matrix`: imports precomputed reaction activity/reconstruction output,
  as CSV headed by `reaction_id` so rows are aligned by ID. An unlabeled legacy
  CSV/MAT requires `legacy_row_order: true` and the source model checksum in
  `model_signature`.

GIMME failures are visible and excluded from the consensus denominator; a run
fails when the configured successful-sample fraction is not met. Exchange bound
settings may only target boundary reactions unless `allow_internal_bound_override`
is explicitly enabled. See [Native GIMME](../tools/gimme.md) for its math and
missing-expression semantics.

```json
{
  "workflow": "cell-specific",
  "run": {"name": "cell", "output_dir": "../runs/cell"},
  "cell_specific": {
    "input_model": "../inputs/models/final-thg.json",
    "expression_file": "../inputs/expression.jsonl",
    "gene_identifier_namespace": "Ensembl",
    "reduction_strategy": "gimme",
    "sample_aggregation": "none",
    "gpr": {"and_rule": "min", "or_rule": "max", "unknown_policy": "unpenalized"},
    "gimme": {
      "expression_threshold": 1.0,
      "objectives": [{"id": "biomass", "coefficients": {"BIOMASS": 1.0}, "minimum_fraction_of_optimum": 0.2}]
    },
    "consensus": {"presence_threshold": 0.0},
    "validation_profile": "cell-specific-standard"
  }
}
```
