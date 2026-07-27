# Model comparison

Reaction IDs and stoichiometry can be compared per compartment through the
Python API or `thg-compare`:

```bash
thg-compare model_a.json model_b.json --output-dir results/compare
```

The command writes raw and (by default) blocked-reaction-filtered CSV reports.
Use `--no-include-blocked` when only the raw comparison is required.
