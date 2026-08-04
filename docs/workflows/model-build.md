# Model enrichment

## What this workflow is for

Add BioCyc, KEGG, and Ensembl information to an existing JSON or SBML model,
while retaining caches and an explicit error report for review.

## When not to use it

Use [model reconstruction](database.md) for normalized records and
[annotation](annotation.md) when you need identifier or GPR analysis without
the complete enrichment pipeline.

## Prerequisites and inputs

Provide a JSON or SBML model, caller-owned output paths, and optional service
clients. The default package does not require network access for the
dependency-light helpers; live service lookups need credentials and rate-limit
planning.

## Python API

Use [`build_model`][thg_protocol.model_build.build_model] for one model:

```python
from thg_protocol.model_build import build_model

report = build_model(
    "input.xml", "results/model.xml", cache_dir="results/cache",
    errors_path="results/errors.json",
)
```

For batch processing use [`build_model_batch`][thg_protocol.model_build.batch.build_model_batch].
Formula-only helpers are [`formula_atoms`][thg_protocol.model_build.mass_balance.formula_atoms],
[`atom10`][thg_protocol.model_build.mass_balance.atom10], and
[`missing_atoms`][thg_protocol.model_build.mass_balance.missing_atoms]. Use
[`reformulate_glycan_equation`][thg_protocol.model_build.mass_balance.reformulate_glycan_equation]
with an injected KEGG client for glycan resolution.

## Outputs

The pipeline writes an enriched model, JSON service caches, and an optional
error report under the paths selected by the caller. Formula helpers return
data and do not mutate models.

## Common errors

Inspect the error file and cache contents before retrying a failed service.
Malformed JSON or SBML should be corrected before enrichment.

## Next workflow

Use [annotation](annotation.md) to inspect identifiers or
[network analysis](network-analysis.md) to assess the enriched model.
