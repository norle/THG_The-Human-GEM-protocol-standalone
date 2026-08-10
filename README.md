# THG Protocol

[![CI](https://github.com/norle/THG_The-Human-GEM-protocol-standalone/actions/workflows/ci.yml/badge.svg)](https://github.com/norle/THG_The-Human-GEM-protocol-standalone/actions/workflows/ci.yml)
[![Documentation](https://github.com/norle/THG_The-Human-GEM-protocol-standalone/actions/workflows/docs.yml/badge.svg)](https://github.com/norle/THG_The-Human-GEM-protocol-standalone/actions/workflows/docs.yml)
[![Hosted documentation](https://img.shields.io/badge/docs-GitHub%20Pages-blue?logo=github)](https://norle.github.io/THG_The-Human-GEM-protocol-standalone/)

> [!NOTE]
> This is a standalone repository derived from
> [MarindeMasLab/THG_The-Human-GEM-protocol](https://github.com/MarindeMasLab/THG_The-Human-GEM-protocol).
> It was created with rewritten Git history to migrate repository artifacts to
> Git LFS, because new LFS objects cannot be added to the existing public fork
> network. It is intentionally **not** part of that repository's GitHub fork
> network.
>
> The source repository is itself a fork of
> [biosustain/THG](https://github.com/biosustain/THG). Please refer to those
> repositories for the original project lineage and upstream history. For the
> publishing rationale and procedure, see
> [the standalone-repository runbook](docs/git-lfs-standalone-repository.md).

THG Protocol is a Python package and command-line toolset for constructing,
curating, expanding, and validating human genome-scale metabolic models. The
scientific workflow comes from Marin de Mas et al., *A Protocol for the
Automatic Construction of Highly Curated Genome-Scale Models of Human
Metabolism* (2023). It has two branches: curate an existing reference GEM such
as Human1, or construct a Human Database from pathway/database information;
merge the branches and validate the result.

This standalone repository is an independent maintained implementation of the
THG workflow. It improves the historical software's architecture, provenance,
resumability, service boundaries, and model-ownership semantics. Historical
repositories and the 2023 paper provide scientific context and useful legacy
references; they are not compatibility targets or the behavioral specification
for this package. See the [project history and lineage](docs/project-history.md)
for background.

Inputs are caller-owned JSON/SBML models or normalized pathway and database
records. Maintained workflows produce revised models, structured validation and
comparison reports, reproducible run artifacts, and optional service caches;
output paths and provenance remain under caller control.

The Human Database workflow separates source collection from model
reconstruction. Offline runs consume normalized records directly. For a live or
credentialed source, callers provide a small source adapter with a `fetch(key)`
method to `harvest_snapshot`; THG supplies bounded retries, deterministic
caching, an error ledger, and normalized-record reconstruction. This explicit
adapter boundary is intentional: network access, credentials, source-specific
queries, and rate limits remain visible and caller-owned rather than being
hidden inside the core workflow.

## Installation

THG Protocol supports Python 3.10–3.12:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[full]'
```

This installs the core package and all runtime capabilities. For the smaller
core-only install, use `python -m pip install -e .`; the full profiles and
their tradeoffs are described in the [installation guide](docs/installation.md).

## Documentation entry points

- [Practical quickstart](docs/quickstart.md): a small deterministic offline
  workflow through reconstruction, enrichment, checks, and comparison.
- [Complete THG workflow](docs/protocol/index.md): the scientific sequence,
  intermediate states, and current support boundaries.
- [Operation reference](docs/usage.md): annotation, reconstruction,
  pathway, gapfill, merge, comparison, figures, and downstream tools.
- [API reference](docs/api/index.md): Python and installed CLI contracts.

For an installation-only check, run the [API smoke test](docs/api-smoke-test.md).
The two-metabolite example there is not a representative human reconstruction.

```python
from pathlib import Path

from thg_protocol.analysis.consistency import unbalanced_reactions
from thg_protocol.database import MetaboliteRecord, ReactionRecord, reconstruct_model

model = reconstruct_model(
    "smoke",
    [MetaboliteRecord("a_c", formula="C1H2"), MetaboliteRecord("b_c", formula="C1H2")],
    [ReactionRecord("R1", {"a_c": -1, "b_c": 1})],
    output_path=Path("results/smoke/model.json"),
)
assert not unbalanced_reactions(model)
```

## Installed commands

```bash
thg-gapfill --model model.json --output-dir results/gapfill
thg-pathway --model model.json --config pathway.json \
  --database metabolite_ids.json --output results/pathway.json
thg-compare model_a.json model_b.json --output-dir results/compare
```

Commands and Python APIs use caller-selected paths. Keep input models unchanged,
save reports/caches with their models, and record package, service, solver, and
optional dependency versions for reproducibility.

## Project status

The supported package workflows are implemented and tested. The standalone
package defines its own maintained behavior and contracts; historical behavior
is preserved only where it remains useful or has been deliberately retained.
External services and credentialed source collection are opt-in and must be
provided through explicit clients or source adapters.

## Lineage and citation

The scientific workflow is described in [the 2023 protocol paper](https://doi.org/10.3390/bioengineering10050576).
This standalone repository is derived from
[MarindeMasLab/THG_The-Human-GEM-protocol](https://github.com/MarindeMasLab/THG_The-Human-GEM-protocol)
and is maintained separately from the historical implementation. Please cite
[biosustain/THG](https://github.com/biosustain/THG) when using THG in research.

Developer, release, repository, and legacy records are in the [maintainer
reference](docs/development.md). The active closeout requirements are recorded
in the [next refactoring plan](docs/plans/REFACTORING_PLAN_NEXT.md). Project
materials are distributed under the [Creative Commons Attribution 4.0
International license](LICENSE).
