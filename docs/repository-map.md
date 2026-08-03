# Repository map

| Path | Ownership and purpose | Safe for default examples? |
| --- | --- | --- |
| `src/thg_protocol/` | Maintained Python package and installed commands | Yes, through APIs |
| `tests/` | Unit, integration, characterization, and docs tests | Yes, as test inputs |
| `models/` | Large or historical model artifacts | No; use small fixtures |
| `files/` | Canonical pathway inputs, configs, and lookup data | Read-only inputs |
| `supplementary_material/` | Reports, figures, spreadsheets, and historical outputs | Read-only/reference |
| `constraints/` | Reproducible dependency constraints for CI gates | Yes for matching gates |
| `docs/` | Published guides, API pages, and artifact policy | Yes |
| `build/`, `dist/` | Local packaging outputs | No; regenerate locally |

Generated models, reports, caches, figures, and temporary files should be
written under a caller-selected output directory such as `results/`, which is
ignored by the repository. Do not put credentials, downloaded service data,
or large model outputs into the documentation fixtures.

Canonical artifact ownership and Git LFS status are recorded in the
[artifact inventory](artifact-inventory.md), [data and model reference](data-and-model-files.md),
and [Git LFS runbook](git-lfs-standalone-repository.md).
