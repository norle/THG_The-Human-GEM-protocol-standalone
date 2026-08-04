# Model comparison

## What this workflow is for

Compare reaction IDs and stoichiometry, including differences by compartment,
before a merge or after curation.

## When not to use it

Use [network analysis](network-analysis.md) for connectivity or balance, and
[merge](merge.md) when the goal is to combine model content.

## Prerequisites and inputs

Inputs may be JSON or SBML. Blocked-reaction filtering needs a COBRA solver;
structural comparison does not.

## Python API

Use [`compare_models_from_files`][thg_protocol.analysis.compare.compare_models_from_files]:

```python
from thg_protocol.analysis.compare import compare_models_from_files

reports = compare_models_from_files(
    "model_a.json", "model_b.json", "results/compare", include_blocked=False
)
```

## CLI

```bash
thg-compare model_a.json model_b.json --output-dir results/compare
```

Use `--no-include-blocked` when only raw comparison is required.

## Outputs

The command writes raw and filtered CSV reports. The Python function also
returns structured comparison data.

## Common errors

Solver errors indicate that blocked filtering was requested without a working
solver. Repeat with `include_blocked=False` or the CLI flag.

## Next workflow

Use [merge and consistency](merge.md) to combine compatible models, or
[figures and reports](figures.md) to present comparison summaries.
