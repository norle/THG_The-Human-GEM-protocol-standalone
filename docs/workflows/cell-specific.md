# Cell-specific models

The dependency-light tailoring core is available without Troppo:

```python
from thg_protocol.cell_specific import reduce_model_by_activity

tailored, report = reduce_model_by_activity(
    model,
    "results/activity.csv",
    presence_threshold=0.0,
    output_path="results/tailored.xml",
)
```

Activity rows must follow the model reaction order. CSV and MAT inputs are
supported; MAT files use the `all_Solutions_matrix5` key by default. The
optional extra remains required for GIMME/Troppo workflows.

Cell-specific model generation depends on the optional `cell-specific` extra:

```bash
python -m pip install 'thg-protocol[cell-specific]'
```

This workflow remains compatibility-only. Keep downloaded model inputs and
generated outputs outside the source tree, and characterize external service
calls with static fixtures before promoting a package API.
