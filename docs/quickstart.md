# Quickstart

Build and inspect a tiny model using the included example data. This runs
offline and does not need credentials or a solver.

## Prerequisites

From the repository root, using Python 3.10–3.12:

```bash
python -m pip install -e .
```

## Run it

```python
from pathlib import Path

from cobra.io import load_json_model
from thg_protocol.analysis import find_network_components, write_component_report
from thg_protocol.analysis.compare import compare_models_from_files
from thg_protocol.analysis.consistency import unbalanced_reactions
from thg_protocol.annotation import analyze_model_annotations
from thg_protocol.database import reconstruct_model_from_json
from thg_protocol.pathway import implement_pathway_files

examples = Path("docs/examples")
run_dir = Path("runs/practical-quickstart")
run_dir.mkdir(parents=True, exist_ok=True)

reference_path = run_dir / "reference-model.json"
model = reconstruct_model_from_json(
    examples / "records.json", output_path=reference_path
)
print(model.id, len(model.metabolites), len(model.reactions))

print(analyze_model_annotations(reference_path))

enriched_path = run_dir / "enriched-model.json"
pathway_result = implement_pathway_files(
    examples / "quickstart_model.json",
    examples / "pathway_config.json",
    examples / "metabolite_ids.json",
    enriched_path,
)
print(pathway_result["compartments_added"])

enriched_model = load_json_model(enriched_path)
component_result = find_network_components(enriched_model)
write_component_report(component_result, run_dir / "components.json")
print(component_result["is_fully_connected"])
print(unbalanced_reactions(enriched_model))

comparison = compare_models_from_files(
    enriched_path, examples / "comparison_model.json", run_dir / "comparison"
)
print(comparison["raw"]["_summary"])
```

You should see `docs-toy 2 1`, an annotation mapping containing `chebi`, one
added compartment, and a comparison summary.

## Files after execution

```text
runs/practical-quickstart/
├── reference-model.json
├── enriched-model.json
├── components.json
└── comparison/
    ├── compartments_comparison_raw.csv
    └── compartments_comparison_no_blocked.csv
```

These are demonstration fixtures, not a research-quality human GEM. Next,
[choose a workflow](workflows/index.md) for your own model or evidence.
