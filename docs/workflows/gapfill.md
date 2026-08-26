# Gapfill and canonical reference workflows

`thg-run gapfill CONFIG` runs the proposal-first gapfill stages against an
explicit external COBRA JSON or SBML model. The required `gapfill` settings
include `external_input: true`, `method`, `max_additions`, and
`validation_profile`; transport methods also require `allowed_connections` and
`candidate_types`.

`thg-run reference CONFIG` combines the maintained β1 and β2 stages with the
same gapfill implementation. Its gapfill section omits `input_model` and
`external_input`; the source is the checksum-verified `export-beta2` artifact.
The β2 candidate remains ungapfilled and is never overwritten.

The final stage writes `thg-reference-gapfilled.json` and `.xml` only after
`gapfill-gate.json` is `passed` or a non-blocking `warning`. Plans, ledgers,
validation reports, semantic diffs, and provenance are exported alongside the
model. Incomplete or failed attempts remain under the run's `failed` directory.
