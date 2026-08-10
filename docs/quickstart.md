# Practical quickstart

This offline example demonstrates a small but realistic direct-API workflow: load a
normalized record bundle, inspect annotations, apply a deterministic pathway
configuration, check connectivity and formula balance, and compare the result.
It intentionally uses the tracked documentation fixtures in
[`docs/examples/`](examples/README.md), rather than caller-owned workspace
inputs. The model is deliberately tiny and does not reproduce a research-quality
human GEM or create a resumable `thg-run` manifest.

## Prerequisites

From a fresh checkout, use Python 3.10–3.12 and install the core package:

```bash
python -m pip install -e .
```

No network, credentials, solver, or optional extra is required.

## Files before execution

The commands below use the repository's tracked `docs/examples/` fixtures
directly. For a real research run, place caller-owned source material under
`inputs/`, author a config under `configs/`, and use the registered workflows
documented in [THG workflows](workflows/index.md).

## Run the workflow

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

# 1. Load normalized records and write a generated run artifact.
reference_path = run_dir / "reference-model.json"
model = reconstruct_model_from_json(
    examples / "records.json", output_path=reference_path
)
print(model.id, len(model.metabolites), len(model.reactions))

# 2. Inspect identifier coverage before changing model content.
print(analyze_model_annotations(reference_path))

# 3. Apply a deterministic, local pathway configuration.
enriched_path = run_dir / "enriched-model.json"
pathway_result = implement_pathway_files(
    examples / "quickstart_model.json",
    examples / "pathway_config.json",
    examples / "metabolite_ids.json",
    enriched_path,
)
print(pathway_result["compartments_added"])

# 4. Check connectivity and formula balance on the enriched model.
enriched_model = load_json_model(enriched_path)
component_result = find_network_components(enriched_model)
write_component_report(component_result, run_dir / "components.json")
print(component_result["is_fully_connected"])
print(unbalanced_reactions(enriched_model))

# 5. Compare the enriched model with a second prepared model.
comparison = compare_models_from_files(
    enriched_path, examples / "comparison_model.json", run_dir / "comparison"
)
print(comparison["raw"]["_summary"])
```

Expected stable checkpoints are `docs-toy 4 1`, an annotation mapping
containing `chebi`, one added compartment, and a written JSON component report.
The exact comparison summary is data-dependent; inspect
`runs/practical-quickstart/comparison/` rather than treating it as a
scientific quality score.

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

The first branch above demonstrates local reconstruction and model enrichment
building blocks. It writes generated artifacts under `runs/`, but does not
create the manifest, stage attempts, or resume behavior of a registered
workflow. It omits live biological harvesting, GPR expansion, a second
scientific model branch, merge iteration, MEMOTE, and metabolic-task analysis.
Continue with the [workflow overview](workflows/index.md) for those distinctions.

## Troubleshooting

Run the script from the repository root so the fixture paths resolve. If an
output is absent, check that the selected run directory is writable. Service
backed operations are intentionally excluded; use static clients or the
operation guides when testing those boundaries offline.
