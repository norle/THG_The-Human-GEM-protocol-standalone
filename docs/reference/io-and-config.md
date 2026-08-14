# Inputs, outputs, and configuration

## Supported inputs

Models may be COBRA JSON or SBML. Human Database reconstruction accepts a
normalized JSON bundle with required `metabolites` and `reactions` arrays and
optional `genes`, `pathways`, and `model_name`. Task suites and workflow
configuration are JSON contracts. Small documentation fixtures live under
`docs/examples/`; caller-owned research inputs belong under `inputs/` and
version-controlled run specifications belong under `configs/`.

## Workflow configuration

Workflow configurations have `workflow`, `run`, and a workflow-specific
section. Registered workflow IDs include `beta1`, `beta2`,
`validate`, and `compare`. Generic `start` also accepts `human-database` and
`final-thg` configurations.

## Artifacts and provenance

Run directories contain a manifest, configuration snapshot, stage fingerprints,
artifact records, checksums, validation reports, and provenance. Candidate
artifacts are not promoted artifacts: release gates and `release_beta1` or
`release_beta2` create the promoted names. Final-THG acceptance is a scientific
review boundary, not an automatic publication claim.

Solver, MEMOTE, database, figures, and cell-specific features are optional
dependencies. Record versions, commands, cache manifests, and failure states
when using them.
