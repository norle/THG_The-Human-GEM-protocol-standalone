# Merge

!!! info "Status: Supported"
    Merge planning/application, bounded repair, validation, and the legacy
    non-mutating merge APIs are maintained and covered by current tests.

## Outcome

Combine two compatible COBRA models into a copied result while reporting added,
overlapping, and optionally removed isolated objects.

## Place in the THG protocol

Core convergence building block for THGβ2 plus Human Database; it does not
implement the full historical similarity-aware merge orchestration.

## When to use it

Use it when both branch inputs have compatible IDs, compartments, and formats.

## When not to use it

Use [comparison](comparison.md) to ask what differs without combining models.

## Inputs

Two loaded COBRA models or JSON/SBML paths, an explicit output path for the
path-based API, and an explicit isolated-metabolite policy.

## Requirements

Local COBRA I/O only; no network, credentials, or solver.

## Run from the command line

No installed merge CLI exists. Use the Python API or a caller script.

## Run from Python

```python
from thg_protocol.merge import merge_models_from_paths

merged, report = merge_models_from_paths(
    "runs/beta2/model.json",
    "runs/human-database/model.json",
    "runs/final-thg/merged.json",
    remove_isolated_metabolites=False,
)
print(report.added_reactions, report.overlapping_reactions)
```

## Outputs

Returns a copied model and `MergeReport`; writes only the selected JSON/SBML
path. Base and incoming inputs are not mutated. Existing base stoichiometry and
bounds are retained on overlap; non-empty incoming metadata may be added.

## Inspect the result

Review every report field, collision IDs, retained stoichiometry, GPRs, and
isolated-metabolite decision before running [validation](../protocol/merge-and-validate.md).

## Common problems

Unexpected overlap or missing metabolites usually indicates incompatible ID
namespaces or compartments. Use comparison before changing identifiers.

## Next step

Continue to [network analysis](network-analysis.md) or the
[merge-and-validate protocol route](../protocol/merge-and-validate.md).

## API references

[`merge_models`][thg_protocol.merge.merge_models],
[`merge_models_from_paths`][thg_protocol.merge.merge_models_from_paths], and
[`generate_merge_plan`][thg_protocol.merge.generate_merge_plan],
[`apply_merge_plan`][thg_protocol.merge.apply_merge_plan],
[`MergePolicy`][thg_protocol.merge.MergePolicy],
[`bounded_repair`][thg_protocol.merge.bounded_repair],
[`validate_merged_model`][thg_protocol.merge.validate_merged_model], and
[`MergeReport`][thg_protocol.merge.MergeReport].

## Differences from the historical workflow

The current API has intentional retained-base semantics and returns a
structured report rather than historical positional overlap lists.
