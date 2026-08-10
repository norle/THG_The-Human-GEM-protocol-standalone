# THG workspace inputs

This directory contains local, caller-owned source material for THG workflows.
THG may read these files, but it treats them as read-only and must never modify
them in place.

Users may place models, normalized database or pathway records, gene/reaction/
metabolite/localization evidence, metabolic-task suites, and similar source
files here. Real research inputs may be large, private, licensed, or
machine-specific, so they are not committed by default.

The recommended layout is:

```text
inputs/
├── models/
├── database/
├── evidence/
└── validation/
```

The categories are intended for:

- `inputs/models/`: COBRA JSON or SBML input models;
- `inputs/database/`: normalized database and pathway record bundles;
- `inputs/evidence/`: gene, reaction, metabolite, localization, and other
  evidence;
- `inputs/validation/`: metabolic-task suites and other validation inputs.

Workflow runs should create their own checksummed copies or snapshots of
consumed inputs inside the corresponding run directory. Those run-owned copies
provide exact provenance for the execution without modifying the caller-owned
files in this directory.
