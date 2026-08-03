# THG Protocol

[![CI](https://github.com/norle/THG_The-Human-GEM-protocol-standalone/actions/workflows/ci.yml/badge.svg)](https://github.com/norle/THG_The-Human-GEM-protocol-standalone/actions/workflows/ci.yml)
[![Documentation](https://github.com/norle/THG_The-Human-GEM-protocol-standalone/actions/workflows/docs.yml/badge.svg)](https://github.com/norle/THG_The-Human-GEM-protocol-standalone/actions/workflows/docs.yml)
[![License: CC BY 4.0](https://img.shields.io/badge/License-CC%20BY%204.0-lightgrey.svg)](LICENSE)

Python tools for reconstructing, curating, annotating, comparing, and
analyzing human genome-scale metabolic models.

The Human GEM (THG) protocol can build a curated metabolic network from
normalized records, or curate and expand an existing human GEM. Network-backed
services and optional solver workflows are explicit opt-ins; the maintained
package APIs are deterministic by default and accept caller-owned input,
output, cache, and report paths.

> [!NOTE]
> This is a standalone repository derived from
> [MarindeMasLab/THG_The-Human-GEM-protocol](https://github.com/MarindeMasLab/THG_The-Human-GEM-protocol).
> It was created with rewritten Git history to migrate repository artifacts to
> Git LFS and is intentionally outside that repository's GitHub fork network.
> The source project is itself based on [biosustain/THG](https://github.com/biosustain/THG).
> See the [standalone-repository runbook](docs/git-lfs-standalone-repository.md)
> for the publishing rationale and procedure.

## Package status

This checkout contains the `thg-protocol` package, version `0.1.0`, using a
`src/` layout and supporting Python 3.10–3.12. The maintained package surface
includes Python APIs under `thg_protocol`, three installed command-line tools,
and documentation-backed workflow examples. Historical checkout-only
implementations and their old import namespaces have been removed; preserved
reports, figures, inputs, and model files remain available under their
canonical artifact locations.

The [current-state snapshot](CURRENT_STATE.md) records validation evidence and
remaining release work for the refactoring branch.

## Features

- Reconstruct models from normalized metabolite and reaction records.
- Annotate metabolites, reactions, and GPRs through injectable service clients.
- Run deterministic gapfill and pathway workflows with explicit file paths.
- Merge models and perform structural consistency, network, and mass-balance
  analysis.
- Compare JSON and SBML models and generate figures and reports.
- Use optional solver, MEMOTE, database, cell-specific, and figure extras when
  a workflow requires them.

## Installation

The package is currently installed from a repository checkout:

```bash
git clone https://github.com/norle/THG_The-Human-GEM-protocol-standalone.git
cd THG_The-Human-GEM-protocol-standalone

python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

Install the development tools or workflow-specific extras as needed:

```bash
python -m pip install -e ".[database]"
python -m pip install -e ".[dev]"
python -m pip install -e ".[docs]"
python -m pip install -e ".[solver]"
python -m pip install -e ".[memote]"
python -m pip install -e ".[cell-specific]"
python -m pip install -e ".[figures]"
```

| Extra | Provides |
| --- | --- |
| `database` | Compatibility support for database checkpoints |
| `dev` | Tests, linting, and package builds |
| `docs` | MkDocs documentation and API rendering |
| `solver` | Solver-backed workflows and tests |
| `memote` | MEMOTE analysis |
| `cell-specific` | Cell-specific model workflows |
| `figures` | Matplotlib and Seaborn figure generation |

See the [installation guide](docs/installation.md) for the supported Python
range and the complete [dependency compatibility matrix](docs/dependency-compatibility.md).

## Quickstart

The following offline example reconstructs a small COBRA JSON model and runs a
structural consistency check:

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

Read the [five-minute quickstart](docs/quickstart.md) for the full example,
including reusable JSON inputs and the next workflows to try.

## Command-line tools

The package installs these commands:

```bash
thg-gapfill --help
thg-pathway --help
thg-compare --help
```

For example:

```bash
thg-gapfill --model model.json --output-dir results/gapfill
thg-pathway --model model.json --config pathway.json \
  --database metabolite_ids.json --output results/pathway.json
thg-compare model_a.json model_b.json --output-dir results/compare
```

The [usage guide](docs/usage.md) and [CLI API reference](docs/api/cli.md)
describe the supported arguments and workflow boundaries.

## Documentation

- [Documentation home](docs/index.md)
- [Hosted documentation](https://norle.github.io/THG_The-Human-GEM-protocol-standalone/)
- [Quickstart](docs/quickstart.md)
- [Workflow guides](docs/usage.md)
- [Python API reference](docs/api/index.md)
- [Examples and deterministic fixtures](docs/examples/README.md)
- [Development guide](docs/development.md)
- [Release validation](docs/release-validation.md)
- [Data and model files](docs/data-and-model-files.md)
- [Repository map and artifact inventory](docs/repository-map.md) ·
  [tracked artifacts](docs/artifact-inventory.md)

The hosted site is deployed by GitHub Actions when GitHub Pages is enabled for
the repository's default branch. The source documentation under `docs/` is
always available in the checkout.

## Development

Run the default offline test suite and linter with:

```bash
ruff check src tests
pytest -m "not slow and not online and not solver and not gurobi and not memote"
```

The [release-validation guide](docs/release-validation.md) covers source and
wheel builds, outside-checkout imports, installed CLI smoke tests, and optional
solver or online checks.

## Citation and lineage

If you use THG in research, please cite the original
[biosustain/THG project](https://github.com/biosustain/THG). This repository is
a standalone packaging and artifact-migration line for that project.

## License

Project materials are distributed under the
[Creative Commons Attribution 4.0 International license](LICENSE). Please
review the license and retain attribution when reusing the repository's code,
models, documentation, or other materials.
