# Repository and data management

Source code lives under `src/thg_protocol`; tests and deterministic fixtures are
under `tests/`; user documentation and small fixture examples are under `docs/`;
runnable workflow recipes are under `examples/`. Run outputs, caches, manifests,
and generated reports belong in explicit run/output directories rather than in
source control.

Large reference inputs and generated artifacts may use Git LFS. Keep checksums,
artifact roles, provenance, and the procedure for obtaining a large file with
the corresponding data policy. Do not commit credentials, live-service caches,
or unreviewed candidate models as canonical scientific artifacts.

Machine-readable inventories can remain alongside the docs without becoming
navigation destinations. Historical parity and migration records are maintained
separately from current support claims.
