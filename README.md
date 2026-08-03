# THG Protocol

[![CI](https://github.com/norle/THG_The-Human-GEM-protocol-standalone/actions/workflows/ci.yml/badge.svg)](https://github.com/norle/THG_The-Human-GEM-protocol-standalone/actions/workflows/ci.yml)
[![Documentation](https://github.com/norle/THG_The-Human-GEM-protocol-standalone/actions/workflows/docs.yml/badge.svg)](https://github.com/norle/THG_The-Human-GEM-protocol-standalone/actions/workflows/docs.yml)
[![License: CC BY 4.0](https://img.shields.io/badge/License-CC%20BY%204.0-lightgrey.svg)](LICENSE)

Tools for constructing, curating, assessing, and comparing human genome-scale metabolic models (GEMs).

THG Protocol can start from normalized metabolite and reaction records or from an existing JSON/SBML model. It helps you add biological content, check the result, compare versions, and generate reports or figures.

## What it does

- Reconstruct models from normalized records.
- Enrich models with metabolite, reaction, and GPR annotations.
- Add configured pathways, propose transport gapfill candidates, and merge models.
- Check balance and connectivity, compare models, and create cell-specific models.
- Produce CSV reports and optional SVG figures.

## Install

THG Protocol supports Python 3.10–3.12. Install the core package from a checkout:

```bash
git clone https://github.com/norle/THG_The-Human-GEM-protocol-standalone.git
cd THG_The-Human-GEM-protocol-standalone
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

Some workflows need optional extras, such as `figures`, `solver`, or `cell-specific`. See the [installation guide](docs/installation.md) for when to install them.

## Start with a model

The smallest workflow builds a COBRA JSON model from normalized records:

```python
from pathlib import Path

from thg_protocol.analysis.consistency import unbalanced_reactions
from thg_protocol.database import MetaboliteRecord, ReactionRecord, reconstruct_model

output = Path("results/quickstart/model.json")
model = reconstruct_model(
    "quickstart",
    [
        MetaboliteRecord("a_c", compartment="c", name="A", formula="C1H2"),
        MetaboliteRecord("b_c", compartment="c", name="B", formula="C1H2"),
    ],
    [ReactionRecord("R_A_to_B", {"a_c": -1, "b_c": 1}, name="A to B")],
    output_path=output,
)

print(model.id, output, unbalanced_reactions(model))
```

The output is written to `results/quickstart/model.json`. Continue with the [five-minute quickstart](docs/quickstart.md), then use the [full workflow overview](docs/workflow-overview.md) to decide what to do next.

## Typical workflow

```text
records or existing model
        -> build and annotate
        -> add pathways, gapfill, or merge
        -> check connectivity and balance
        -> compare, tailor, and report
```

Each stage is optional and writes models or reports to paths you choose. The [task guides](docs/usage.md) explain the purpose, inputs, outputs, and common issues for every stage.

Common command-line workflows are:

```bash
thg-gapfill --model model.json --output-dir results/gapfill
thg-pathway --model model.json --config pathway.json \
  --database metabolite_ids.json --output results/pathway.json
thg-compare model_a.json model_b.json --output-dir results/compare
```

## Documentation

- [Documentation home](docs/index.md)
- [Full workflow overview](docs/workflow-overview.md)
- [Task guides](docs/usage.md)
- [API reference](docs/api/index.md)
- [Data and model files](docs/data-and-model-files.md)
- [Refactoring closeout plan](docs/plans/REFACTORING_PLAN_NEXT.md)

Developer, release, repository, and legacy information is kept separately in the [developer and maintainer reference](docs/development.md).

## Citation and lineage

Please cite [biosustain/THG](https://github.com/biosustain/THG) when using THG in research. This standalone repository is derived from [MarindeMasLab/THG_The-Human-GEM-protocol](https://github.com/MarindeMasLab/THG_The-Human-GEM-protocol) and preserves its artifact migration procedure in the [standalone-repository runbook](docs/git-lfs-standalone-repository.md).

## License

Project materials are distributed under the [Creative Commons Attribution 4.0 International license](LICENSE).
