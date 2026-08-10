# Model enrichment

!!! info "Status: Supported"
    `thg_protocol.model_build.build_model` is a maintained, tested enrichment
    building block with explicit output, cache, error, and client paths.

## Outcome

Enrich an existing COBRA JSON/SBML model with matching KEGG reaction, BioCyc EC,
and Ensembl annotations while preserving model stoichiometry.

## Place in the THG protocol

Supporting building block in the reference-model branch, not a complete THGβ1
or THGβ2 orchestrator.

## When to use it

Use it after preserving a reference model when matching service annotations and
reviewable caches/errors are needed.

## When not to use it

Use [model reconstruction](database.md) for normalized records, or
[annotation](annotation.md) for a focused inventory or identifier task.

## Inputs

Provide a `.json` or SBML model path, explicit output path, optional `cache_dir`
and `errors_path`, and optional injected BioCyc, KEGG, and Ensembl clients.

## Requirements

Empty/toy models can run offline. Matching annotations invoke the selected
service client; production clients may need network access, credentials, and
rate-limit planning. No solver is required.

## Run from the command line

No installed model-enrichment CLI exists. Use the Python API with explicit
paths.

## Run from Python

```python
from thg_protocol.model_build import build_model

report = build_model(
    "input/reference.json",
    "runs/reference/enriched.json",
    cache_dir="runs/reference/cache",
    errors_path="runs/reference/errors.json",
)
print(report.output_path, report.errors)
```

For offline tests, inject the static clients from `thg_protocol.services` and
provide responses for each identifier.

## Outputs

Returns `ModelBuildReport`, writes the selected JSON/SBML model, three JSON
cache files below `cache_dir`, and an error file when requested. The input file
is not mutated. Existing caches are read and updated; record their dates.

## Inspect the result

Review `report.errors`, cache contents, annotation fields, and unchanged
reaction stoichiometry. Follow with [annotation](annotation.md) and
[network analysis](network-analysis.md).

## Common problems

Service errors are collected rather than silently treated as successful
annotation. Check cache keys, credentials, network status, and the error file
before retrying.

## Next step

Use the [reference-model protocol route](../protocol/reference-model.md) or
run local balance and connectivity checks.

## API references

[`build_model`][thg_protocol.model_build.build_model],
[`build_model_batch`][thg_protocol.model_build.batch.build_model_batch],
[`formula_atoms`][thg_protocol.model_build.mass_balance.formula_atoms],
[`atom10`][thg_protocol.model_build.mass_balance.atom10],
[`missing_atoms`][thg_protocol.model_build.mass_balance.missing_atoms], and
[`reformulate_glycan_equation`][thg_protocol.model_build.mass_balance.reformulate_glycan_equation].

## Differences from the historical workflow

The refactored API uses injected clients and explicit caller-owned paths; it
does not silently write repository-relative outputs or establish the 2023
protocol paper's THG stage names.
