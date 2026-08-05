# Project history and lineage

THG Protocol has two related histories: the scientific protocol described in a
paper, and the software that has been reorganized into this package. Keeping
them separate makes the support statements in the documentation easier to
interpret.

## Scientific origin

The scientific workflow comes from Marin de Mas et al., *A Protocol for the
Automatic Construction of Highly Curated Genome-Scale Models of Human
Metabolism* (2023), [Bioengineering 10(5), 576](https://doi.org/10.3390/bioengineering10050576).
That paper describes the construction of THG from a reference human GEM such
as Human1 and a complementary Human Database. It names the intermediate model
states THGβ1 and THGβ2 and describes how the branches are merged and assessed.

Throughout these docs, “the 2023 protocol paper” or “the paper” means that
scientific publication. It does not mean a release of this Python package.

## Software lineage

The current repository is not a fresh, independent implementation of every
step in the paper. Its software lineage is:

1. The original project was developed in the [`biosustain/THG`](https://github.com/biosustain/THG)
   repository.
2. The work continued in
   [`MarindeMasLab/THG_The-Human-GEM-protocol`](https://github.com/MarindeMasLab/THG_The-Human-GEM-protocol),
   which is the historical source repository for this checkout.
3. This standalone repository reorganizes that code into the
   `thg_protocol` package, adds explicit APIs, tests, documentation, and
   artifact ownership, and removes the former source-checkout-only legacy
   namespaces.

The standalone repository has rewritten Git history because the repository
artifacts were migrated to Git LFS. It is intentionally independent of the
historical repository's GitHub fork network. See the [standalone repository
runbook](git-lfs-standalone-repository.md) for the maintainer procedure and
the [legacy API inventory](legacy-api-inventory.md) for the removed source
layout.

## What the current package represents

The package provides maintained building blocks that correspond to parts of the
paper's workflow: model I/O, annotation, mass-balance and consistency checks,
record-based reconstruction, pathway operations, merge primitives, and other
analysis helpers. Some operations preserve or adapt behavior from the
historical implementation; others are maintained package interfaces without a
legacy equivalent.

The current package does not contain a verified, one-command reconstruction of
the paper's final THG artifact. In particular, the complete β1/β2 construction,
live Human Database harvesting, convergence matching the paper, and exact
final-artifact reproduction are separate status questions. Their status is
tracked in the [capability and evidence matrix](protocol/implementation-status.md).

## How to read the workflow docs

- **Paper workflow** means the scientific sequence and named model states in
  the 2023 protocol paper.
- **Historical implementation** means behavior, reports, or inputs inherited
  from the earlier repositories.
- **Current package** means the maintained APIs and commands in this
  standalone checkout.
- **Published-artifact reproduction** means comparison with a frozen artifact
  from the paper, not merely running a similarly named package operation.

The [complete workflow](protocol/index.md) maps the paper's stages to the
current package. The [practical quickstart](quickstart.md) demonstrates a small
offline package workflow; it is not a reproduction of the paper's THG model.
