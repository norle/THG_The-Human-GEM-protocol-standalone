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
published strategy has two branches: curate an existing reference GEM such as
Human1, or construct a Human Database from pathway/database information; merge
the branches and validate the result.

This repository provides maintained building blocks for that strategy.

## Installation

THG Protocol supports Python 3.10–3.12:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

Optional extras are documented in the [installation guide](docs/installation.md).

## Choose a route

- [Practical quickstart](docs/quickstart.md): a small deterministic offline
  journey through reconstruction, enrichment, checks, and comparison.
- [Complete THG workflow](docs/protocol/index.md): the scientific sequence,
  intermediate states, and current support boundaries.
- [Individual-operation chooser](docs/usage.md): annotation, reconstruction,
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

## Implementation status

The complete published orchestration and exact final-artifact reproduction are
currently **Partial**; see the [implementation-status matrix](docs/protocol/implementation-status.md).

## Lineage and citation

The scientific workflow is described in [the published protocol](https://doi.org/10.3390/bioengineering10050576).
This standalone repository is derived from
[MarindeMasLab/THG_The-Human-GEM-protocol](https://github.com/MarindeMasLab/THG_The-Human-GEM-protocol)
and is maintained separately from the historical implementation. Please cite
[biosustain/THG](https://github.com/biosustain/THG) when using THG in research.

Developer, release, repository, and legacy records are in the [maintainer
reference](docs/development.md). The active closeout requirements are recorded
in the [next refactoring plan](docs/plans/REFACTORING_PLAN_NEXT.md). Project
materials are distributed under the [Creative Commons Attribution 4.0
International license](LICENSE).
