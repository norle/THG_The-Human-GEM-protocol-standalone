# THG Protocol

THG Protocol is a Python package for reconstructing, curating, annotating,
comparing, and analyzing human genome-scale metabolic models. The maintained
package boundary is deterministic by default: callers provide input, output,
cache, and report paths, while network services and optional solvers are
injected explicitly.

## Choose a starting point

- New users: [five-minute quickstart](quickstart.md).
- Workflow users: [workflow guides](usage.md) and the [architecture overview](architecture.md).
- Python developers: [API reference](api/index.md) and [development guide](development.md).
- Artifact maintainers: [repository map](repository-map.md) and [artifact inventory](artifact-inventory.md).

The intended GitHub Pages URL is
<https://norle.github.io/THG_The-Human-GEM-protocol-standalone/>. It becomes
live after the repository Pages source is enabled for GitHub Actions and the
default-branch deployment succeeds. Builds are strict and examples run without
credentials, solvers, large model files, or live services.

## Supported entry points

The installed commands are `thg-gapfill`, `thg-pathway`, and `thg-compare`.
The [API reference](api/index.md) covers every maintained module under
`thg_protocol`, while the [workflow section](usage.md) explains when to use
each interface.

Historical checkout workflows and preserved outputs remain documented under
[maintainer and legacy](legacy-workflows.md); they are not release interfaces.
The broader migration context is recorded in the repository-root
`REFACTORING_PLAN.md`, `REFACTORING_PLAN_NEXT.md`, and
`REFACTORING_PLAN_LEGACY_REMOVAL.md` files.

## Citation and lineage

Please cite [biosustain/THG](https://github.com/biosustain/THG) when using THG
in research. This standalone repository preserves the Git LFS migration and
publishing procedure in the [standalone repository runbook](git-lfs-standalone-repository.md).
