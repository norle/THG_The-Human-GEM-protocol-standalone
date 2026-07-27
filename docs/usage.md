# Usage

Reusable workflow code is exposed through the `thg_protocol` Python API. The
JSON gapfill and pathway workflows, and reaction-level model comparison, can
be used without relying on repository-relative output directories:

```python
from thg_protocol.gapfill import run_pipeline
from thg_protocol.pathway import implement_pathway_files
from thg_protocol.analysis.compare import compare_models_from_files

gapfill = run_pipeline("model.json", "results/gapfill")
pathway = implement_pathway_files(
    "model.json", "pathway.json", "metabolite_ids.json", "results/pathway.json"
)
reports = compare_models_from_files("model_a.json", "model_b.json", "results/compare")
```

Existing top-level scripts remain available during the migration. New command
line entry points will be added only after their workflow modules are
import-safe, parameterized, and covered by help smoke tests.

Installed command-line workflows:

```bash
thg-gapfill --model model.json --output-dir results/gapfill
thg-pathway --model model.json --config pathway.json \
  --database metabolite_ids.json --output results/pathway.json
thg-compare model_a.json model_b.json --output-dir results/compare
```
