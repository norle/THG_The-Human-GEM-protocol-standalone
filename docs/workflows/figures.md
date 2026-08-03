# Figures and reports

Use the figure APIs to turn model summaries or report tables into SVG figures
that you can include in a report or publication.

Report summaries are available through `thg_protocol.figures`; rendering needs
the optional plotting extra:

```bash
python -m pip install 'thg-protocol[figures]'
```

Supply any MEMOTE or algorithm-score data you want to visualize.

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
