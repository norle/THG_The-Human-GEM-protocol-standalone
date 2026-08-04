# Figures and reports

## What this workflow is for

Turn model summaries or report tables into SVG figures suitable for reports
and publications.

## When not to use it

Use [network analysis](network-analysis.md) or [model comparison](comparison.md)
to produce the underlying diagnostics before rendering figures.

## Prerequisites and inputs

Summary APIs accept model-like objects. Rendering needs the optional plotting
extra:

```bash
python -m pip install 'thg-protocol[figures]'
```

## Python API

Start with [`summarize_model_components`][thg_protocol.figures.models.summarize_model_components]:

```python
from thg_protocol.figures.models import summarize_model_components

summary = summarize_model_components({"toy": model})
print(summary["toy"].reactions)
```

Use [`summarize_annotation_rows`][thg_protocol.figures.comparison.summarize_annotation_rows]
for annotation tables and
[`generate_model_comparison_figures`][thg_protocol.figures.models.generate_model_comparison_figures]
for SVG output.

## Outputs

Summary functions return structured data. Rendering writes SVG files under the
caller-selected directory.

## Common errors

Excel-backed reports must contain the documented sheet and columns. A missing
column raises `ValueError` before a chart is created.

## Next workflow

Use [MEMOTE and task analysis](memote.md) for broader quality diagnostics, or
return to the relevant task guide in [usage](../usage.md).
