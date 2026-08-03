# Model comparison

Use comparison to measure reaction-ID and stoichiometric overlap by
compartment.

Reaction IDs and stoichiometry can be compared per compartment through the
Python API or `thg-compare`:

```bash
thg-compare model_a.json model_b.json --output-dir results/compare
```

The command writes raw and (by default) blocked-reaction-filtered CSV reports.
Use `--no-include-blocked` when only the raw comparison is required.

The equivalent Python API is:

```python
from thg_protocol.analysis.compare import compare_models_from_files

reports = compare_models_from_files(
    "model_a.json", "model_b.json", "results/compare", include_blocked=False
)
```

## Prerequisites, output, and troubleshooting

Inputs may be JSON or SBML. Reports are CSV files under the explicit output
directory and the return value contains raw structured data. Blocked filtering
uses COBRA's solver path; disable it for deterministic structural comparison.
