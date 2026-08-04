# Figures and reports

!!! info "Status: Supported"
    Summary and SVG figure APIs are maintained, with rendering covered when the
    optional plotting dependencies are installed.

## Outcome

Summarize model components, annotation groups, comparisons, and selected MEMOTE
scores as caller-owned report data or SVG figures.

## Place in the THG protocol

Downstream presentation and review operation; figures are not a mandatory
construction stage.

## When to use it

Use it after saving stable model/report inputs and when a visual summary helps
review or communicate a result.

## When not to use it

Do not use figures as a substitute for inspecting raw merge, balance, or MEMOTE
reports.

## Inputs

Summary functions accept model-like objects or report rows. Rendering functions
require an explicit report/input path and output directory.

## Requirements

Summary functions are local. Install `python -m pip install -e '.[figures]'`
for matplotlib/seaborn rendering. No network or solver is implicit.

## Run from the command line

No installed figures CLI exists. Use Python.

## Run from Python

```python
from thg_protocol.figures.models import model_component_summary
from cobra.io import load_json_model

model = load_json_model("results/model.json")
summary = model_component_summary(model)
print(summary.reactions, summary.metabolites)
```

## Outputs

Summary functions return structured values. Rendering returns result objects
and writes deterministic SVGs under the selected directory. Inputs are not
mutated and no cache is created.

## Inspect the result

Open SVGs and compare their labels/counts with the source report. Record the
model/report checksum and plotting dependency versions.

## Common problems

Import-safe summary APIs do not guarantee plotting dependencies are installed.
Install the figures extra and check that output directories are writable.

## Next step

Return to [usage](../usage.md), [comparison](comparison.md), or
[MEMOTE](memote.md).

## API references

[`summarize_model_components`][thg_protocol.figures.models.summarize_model_components],
[`summarize_annotation_rows`][thg_protocol.figures.comparison.summarize_annotation_rows],
and [`generate_model_comparison_figures`][thg_protocol.figures.models.generate_model_comparison_figures].

## Differences from the historical workflow

Current figure APIs require explicit inputs and output directories and do not
silently recreate historical repository figures.
