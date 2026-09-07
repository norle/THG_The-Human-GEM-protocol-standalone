# Gapfill and canonical reference workflows

`thg-run gapfill CONFIG` runs the proposal-first gapfill stages against an
explicit external COBRA JSON or SBML model. The required `gapfill` settings
include `external_input: true`, `method`, `max_additions`, and
`validation_profile`; transport methods also require `allowed_connections` and
`candidate_types`. This standalone mode is independently usable with external
models; that does not make gapfill optional in canonical THG construction.

`thg-run reference CONFIG` combines the maintained β1 and β2 stages with the
same gapfill implementation. Its gapfill section omits `input_model` and
`external_input`; the source is the checksum-verified `export-beta2` artifact.
The β2 candidate remains ungapfilled and is never overwritten. Human Database
integration, when selected, enriches β2 before this required canonical stage.

The canonical pipeline always runs gapfill before producing a **THG candidate**.
The final gapfill stage writes `thg-reference-gapfilled.json` and `.xml` only after
`gapfill-gate.json` is `passed` or a non-blocking `warning`. Plans, ledgers,
validation reports, semantic diffs, and provenance are exported alongside the
model. This stage-level gate does not replace the final validation gate and
release export.
Incomplete or failed attempts remain under the run's `failed` directory.
