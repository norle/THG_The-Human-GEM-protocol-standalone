# Pathways and gap filling

## Pathway implementation

Use `thg-pathway` or `implement_pathway_files` to apply an explicit pathway
configuration to a model. Keep source configuration and output paths under
caller control.

## Deterministic gapfill

The gapfill pipeline generates a candidate universe and runs its supported
phases. Candidate additions are reports for review; gapfill is an optional
extension and is not part of β1/β2 correctness.

The current boundary is deterministic candidate generation. A MILP-compatible
strategy requires the optional solver environment and must record its solver,
version, objective, and failure state. See the [workflow API](../api/workflows.md)
for `generate_candidates`, `run_phase1`, `run_phase2`, `run_phase3`, and
`run_pipeline`.

Canonical APIs: [`implement_pathway_files`][thg_protocol.pathway.workflow.implement_pathway_files],
[`implement_pathway`][thg_protocol.pathway.workflow.implement_pathway],
[`generate_candidates`][thg_protocol.gapfill.core.generate_candidates], and
[`run_pipeline`][thg_protocol.gapfill.core.run_pipeline].
