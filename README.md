# THG Protocol

[![CI](https://github.com/norle/THG_The-Human-GEM-protocol-standalone/actions/workflows/ci.yml/badge.svg)](https://github.com/norle/THG_The-Human-GEM-protocol-standalone/actions/workflows/ci.yml)
[![Documentation](https://github.com/norle/THG_The-Human-GEM-protocol-standalone/actions/workflows/docs.yml/badge.svg)](https://github.com/norle/THG_The-Human-GEM-protocol-standalone/actions/workflows/docs.yml)
[![Hosted documentation](https://img.shields.io/badge/docs-GitHub%20Pages-blue?logo=github)](https://norle.github.io/THG_The-Human-GEM-protocol-standalone/)

THG Protocol is a Python package and command-line toolkit for building and
validating human genome-scale metabolic models.

The repository is independently maintained from its source repositories,
[MarindeMasLab/THG_The-Human-GEM-protocol](https://github.com/MarindeMasLab/THG_The-Human-GEM-protocol)
and [biosustain/THG](https://github.com/biosustain/THG). See the [project
history](docs/about/history.md) for lineage and publication context.

## Installation

THG Protocol supports Python 3.10–3.12:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[full]'
```

For a core-only installation, use `python -m pip install -e .`. See the
[installation guide](docs/installation.md) for optional capabilities.

## Start here

- [Quickstart](docs/quickstart.md): run the included offline example.
- [Workflow overview](docs/workflows/index.md): build a THG reference model,
  then a cell-specific model.
- [CLI reference](docs/reference/cli.md): see the available commands.

## Repository layout

```text
src/thg_protocol/  Package code.
docs/              User and contributor documentation.
tests/             Tests and deterministic fixtures.
inputs/            Read-only source models, records, and evidence.
configs/           Version-controlled workflow configurations.
runs/              Generated resumable runs and artifacts.
```

Start a configured workflow with, for example:

```bash
thg-run beta1 configs/beta1.json
```

Commands and Python APIs use caller-selected paths. Keep input models unchanged
and retain reports, caches, versions, and provenance with generated models.

## Installed commands

```bash
thg-run --help
thg-gapfill --help
thg-pathway --help
thg-compare --help
```

## Status and citation

Supported package workflows are implemented and tested. External services and
credentialed collection are opt-in through explicit clients or source adapters.
The [current state](CURRENT_STATE.md) records the remaining release gate.

The scientific workflow is described in [the 2023 protocol
paper](https://doi.org/10.3390/bioengineering10050576). Please cite
[biosustain/THG](https://github.com/biosustain/THG) when using THG in research.
Project materials use the [Creative Commons Attribution 4.0 International
license](LICENSE).
