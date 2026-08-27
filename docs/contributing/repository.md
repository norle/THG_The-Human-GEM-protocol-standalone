# Repository and data management

The repository is organized as follows:

- `src/thg_protocol/` contains the package code.
- `src/thg_protocol/runtime/` contains generic resumable execution.
- `src/thg_protocol/workflow/` contains workflow configuration, registry,
  runners, and workflow adapters. β1 and β2 stage wiring lives in their own
  subpackages.
- `tests/` contains tests and deterministic fixtures.
- `docs/` contains user and contributor documentation.
- `configs/`, `inputs/`, and `runs/` contain workflow configurations, source
  inputs, and generated run artifacts.

Run outputs, caches, manifests, and generated reports belong in explicit
run/output directories rather than in source control.

Large reference inputs and generated artifacts may use Git LFS. Keep checksums,
artifact roles, provenance, and the procedure for obtaining a large file with
the corresponding data policy. Do not commit credentials, live-service caches,
or unreviewed candidate models as canonical scientific artifacts.

Machine-readable inventories can remain alongside the docs without becoming
navigation destinations. Historical implementation records are maintained
separately from current support claims.
