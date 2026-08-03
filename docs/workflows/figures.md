# Figures and reports

Use the figure APIs to turn explicit model summaries or report tables into
reproducible SVG outputs.

Figure workflows accept explicit model and report paths through
`thg_protocol.figures`. Report summaries are dependency-light; rendering uses
the optional plotting extra:

```bash
python -m pip install 'thg-protocol[figures]'
```

The former legacy figure script was retired with the checkout-only workflows.
Optional MEMOTE and algorithm score data must be supplied rather than
hard-coded.

```python
from thg_protocol.figures.models import summarize_model_components

summary = summarize_model_components({"toy": model})
print(summary["toy"].reactions)
```

## Prerequisites, output, and troubleshooting

Summary APIs need only model-like objects. Rendering requires the `figures`
extra and writes SVG files under the caller-selected directory. Excel-backed
reports must contain the documented sheet and column names; a missing column
raises a clear `ValueError` before any chart is created.
