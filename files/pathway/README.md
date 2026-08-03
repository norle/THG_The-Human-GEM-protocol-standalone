# Pathway Configuration Guide

This directory contains pathway configuration examples and the metabolite ID
database used by the supported `thg_protocol.pathway` workflow.

## Directory structure

```text
files/pathway/
├── README.md
├── inputs/
│   ├── endoA_250917_3.json
│   └── config_example.json
├── config/
│   └── pathway-specific/
└── data/
    └── metabolite_id_database.json
```

Generated models and reports should be written to a caller-selected output
directory outside this artifact tree.

## Apply a configuration

```bash
thg-pathway \
  --model files/pathway/inputs/endoA_250917_3.json \
  --config files/pathway/inputs/config_example.json \
  --database files/pathway/data/metabolite_id_database.json \
  --output results/example_pathway.json
```

The command loads the model and configuration, applies the configured
compartments, metabolites, and reactions, and writes the modified model to the
explicit output path. The package does not discover pathways automatically;
the JSON configuration is the user-authored pathway specification.

The equivalent Python API is:

```python
from thg_protocol.pathway import implement_pathway_files

result = implement_pathway_files(
    "files/pathway/inputs/endoA_250917_3.json",
    "files/pathway/inputs/config_example.json",
    "files/pathway/data/metabolite_id_database.json",
    "results/example_pathway.json",
)
print(result["reactions_added"])
```

## Configuration contents

The example configuration demonstrates the main sections:

- `pathway_name`: name used to select pathway-specific metabolite records;
- `compartments`: names and abbreviations to add or resolve in the model;
- `metabolites.targets`: compounds to resolve from the ID database;
- `metabolites.<pathway>_specific`: pathway-specific metabolite metadata;
- `reactions`: reaction IDs, names, equations, bounds, and annotations.

For example, a reaction entry can define its equation and bounds as follows:

```json
{
  "id": "R_Example_Transport_ATP",
  "name": "Transport of ATP",
  "equation": "1 ATP[c] <=> 1 ATP[ck]",
  "lower_bound": -1000.0,
  "upper_bound": 1000.0
}
```

Edit `files/pathway/inputs/config_example.json` to create a custom pathway,
or use one of the maintained configurations under `files/pathway/config/`.
The `pathway-specific/` directory contains focused configurations for
pathways such as aggrecan, decorin, hyaluronan, syndecans, versican, and
related glycocalyx components.

## Choosing inputs and outputs

Use any compatible JSON model as the `--model` input and keep generated files
outside the canonical input/configuration directories:

```bash
thg-pathway \
  --model path/to/model.json \
  --config files/pathway/config/config_glycocalyx_pg.json \
  --database files/pathway/data/metabolite_id_database.json \
  --output results/glycocalyx_proteoglycans.json
```

For the full supported workflow, see
[`docs/workflows/pathway.md`](../../docs/workflows/pathway.md).
