# THG Protocol: Current State

Last reviewed: 2026-08-10

The package migration and legacy-directory cleanup are complete. Supported code
lives under `src/thg_protocol`; tests use package APIs; preserved artifacts have
canonical locations. Historical implementation details remain in Git history.

## Current status

- Branch: `refactoring-cleanup`
- Reviewed commit: `2c4294d`
- Supported Python: 3.10–3.12
- Installed commands: `thg-gapfill`, `thg-pathway`, `thg-compare`, and `thg-run`
- Legacy checkout directories: removed and excluded from distributions
- Canonical large artifacts: seven Git LFS paths

The package provides annotation, GPR, pathway, gapfill, comparison, model
construction, merge, network analysis, figures, cell-specific helpers, model
I/O, validation, and resumable workflows. External lookups use injectable
clients and offline test adapters.

Implementation and verification claims are tracked in
[`docs/protocol/capability-evidence.json`](docs/protocol/capability-evidence.json)
and its [status matrix](docs/protocol/implementation-status.md). Exact
publication-artifact reproduction remains unverified.

## Latest validation

The latest local default offline gate passed under Python 3.12 with `1843
passed, 2 skipped`. Ruff, bytecode compilation, legacy-closure policy tests, and
all four installed CLI help checks also passed.

An isolated source/wheel build installed outside the checkout and passed package
imports and CLI smoke tests. `git lfs fsck` passed for all seven approved
objects, and a fresh local clone reproduced their recorded content.

Hosted run `30340915763` passed Python 3.10–3.12. A newer run tested an older
commit and exposed a Python 3.11 compatibility issue fixed on the current branch.

## Remaining release gate

Run the hosted Python 3.10–3.12 package matrix on the current head. If it passes,
record the run here and publish the closeout changes. The credential-gated
BioCyc fixture remains optional and does not block the offline release gate.
