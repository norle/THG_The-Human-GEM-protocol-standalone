# Repository and data management

## Maintained software and workspace

- `src/` contains the installable package.
- `tests/` contains unit, integration, characterization, and documentation
  tests.
- `docs/` contains user and contributor documentation.
- `configs/` contains version-controlled workflow configurations.
- `inputs/` contains caller-owned, read-only workflow inputs.
- `runs/` contains generated resumable workflow runs.

## Preserved research and reference corpus

- `models/` contains canonical and historical model artifacts.
- `files/` contains retained research inputs and intermediate artifacts.
- `supplementary_material/` contains publication and supporting research
  material.

These two groups have different ownership and lifecycle expectations. The
package structure itself should not be reorganized to make the repository root
look smaller.

Run outputs, caches, manifests, and generated reports belong in explicit
run/output directories rather than in source control.

Large reference inputs and generated artifacts may use Git LFS. Keep checksums,
artifact roles, provenance, and the procedure for obtaining a large file with
the corresponding data policy. Do not commit credentials, live-service caches,
or unreviewed candidate models as canonical scientific artifacts.

Machine-readable inventories can remain alongside the docs without becoming
navigation destinations. Historical implementation records are maintained
separately from current support claims.
