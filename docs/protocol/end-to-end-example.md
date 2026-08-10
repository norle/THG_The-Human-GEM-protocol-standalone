# Worked end-to-end example

!!! warning "Scope and evidence"
    This is a deterministic worked miniature of the workflow structure. It is
    not a regeneration of THG from live databases and omits stages recorded as
    Not implemented in the capability matrix.

## Scope of the example

It represents local normalized-record reconstruction, deterministic pathway
enrichment, connectivity/balance inspection, and comparison. It does not
represent live pathway harvesting, full annotation curation, GPR/location
isoenzyme expansion, a second independently constructed branch, the historical
merge heuristics, MEMOTE, or essential metabolic-task analysis.

## Installation assumptions

Use Python 3.10–3.12 from the repository root:

```bash
python -m pip install -e .
```

The default run is offline and needs no credentials, solver, or optional extra.

## Files before execution

```text
THG_The-Human-GEM-protocol-standalone/
├── docs/examples/
│   ├── records.json
│   ├── quickstart_model.json
│   ├── pathway_config.json
│   ├── metabolite_ids.json
│   └── comparison_model.json
└── runs/
```

## Execute in order

Save the following as `runs/run_miniature.py`, then run
`python runs/run_miniature.py` from the repository root. Every output path
is generated under `runs/` and defined in the script.

```python
from pathlib import Path

from cobra.io import load_json_model
from thg_protocol.analysis import find_network_components, write_component_report
from thg_protocol.analysis.compare import compare_models_from_files
from thg_protocol.analysis.consistency import unbalanced_reactions
from thg_protocol.annotation import analyze_model_annotations
from thg_protocol.database import reconstruct_model_from_json
from thg_protocol.pathway import implement_pathway_files

root = Path(__file__).resolve().parents[1]
examples = root / "docs" / "examples"
run_dir = root / "runs" / "worked-miniature"
run_dir.mkdir(parents=True, exist_ok=True)

reference = run_dir / "reference-model.json"
model = reconstruct_model_from_json(examples / "records.json", output_path=reference)
assert model.id == "docs-toy"
print("reference", len(model.metabolites), len(model.reactions))
print("annotations", analyze_model_annotations(reference))

enriched = run_dir / "enriched-model.json"
pathway = implement_pathway_files(
    examples / "quickstart_model.json",
    examples / "pathway_config.json",
    examples / "metabolite_ids.json",
    enriched,
)
assert pathway["compartments_added"] == 1
print("enrichment", pathway["compartments_added"])

loaded = load_json_model(enriched)
components = find_network_components(loaded)
write_component_report(components, run_dir / "components.json")
print("connected", components["is_fully_connected"])
print("unbalanced", unbalanced_reactions(loaded))

comparison_dir = run_dir / "comparison"
comparison = compare_models_from_files(
    enriched, examples / "comparison_model.json", comparison_dir
)
print("comparison", comparison["raw"]["_summary"])
```

After the reconstruction checkpoint, inspect `reference-model.json` and the
printed annotation mapping. After enrichment, inspect the added compartment.
After analysis, review `components.json` and the unbalanced-reaction list. The
comparison checkpoint is the two CSV files in `comparison/`.

## Files after execution

```text
runs/worked-miniature/
├── reference-model.json
├── enriched-model.json
├── components.json
└── comparison/
    ├── compartments_comparison_raw.csv
    └── compartments_comparison_no_blocked.csv
```

## Reproducibility note

Record the package version and commit, fixture checksums, Python and optional
dependency versions, and output checksums. If adding service-backed stages,
also record client configuration, database releases, query/cache dates, and
credentials-independent service response caches. Follow the [implementation
status matrix](implementation-status.md) before describing this miniature as a
scientific reproduction.
