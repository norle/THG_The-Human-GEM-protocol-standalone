# Cell-specific models

Cell-specific reduction follows validated Final THG in the canonical pipeline.
Use transcript or activity evidence to reduce that parent model, preserve it,
and record exchange matching and gene-rule transformations. The tool also
accepts an explicitly declared external GEM in standalone use; that does not
turn a generic reduction into a Final-THG-derived or publication-specific cell
model automatically.

See the [workflow API](../api/workflows.md) for
`reduce_model_by_activity`, exchange matching, and transcriptomics helpers.

Canonical API: [`reduce_model_by_activity`][thg_protocol.cell_specific.reduce_model_by_activity].
