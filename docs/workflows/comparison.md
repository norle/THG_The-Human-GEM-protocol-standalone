# Model comparison

Use comparison to see how two models differ in reaction IDs and stoichiometry,
including differences by compartment. It is useful before a merge and after a
curation step, when you want a report of what changed.

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

Inputs may be JSON or SBML. Reports are CSV files under the output directory,
and the Python function also returns structured data. Blocked-reaction
filtering requires COBRA's solver path; use `--no-include-blocked` when you
only need structural comparison.
