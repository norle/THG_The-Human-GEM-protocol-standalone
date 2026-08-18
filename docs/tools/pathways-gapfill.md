# Pathways and gap filling

## Pathway implementation

Use `thg-pathway` or `implement_pathway_files` to apply an explicit pathway
configuration to a model. Keep source configuration and output paths under
caller control.

## Standalone gapfill

Gap filling is optional and is not a β1/β2 stage or correctness requirement.
Use it with any COBRA JSON or SBML model; it copies the input and writes a
self-contained result directory.

```bash
thg-gapfill --model external-model.xml --method deadends --output-dir runs/gapfill
thg-gapfill --model runs/beta2/artifacts/export-beta2/attempt-0001/thg-beta2-candidate.json --method greedy --output-dir runs/beta2-gapfill
```

Methods are `greedy` (largest measured improvement first), `deadends`
(targetable dead-end coverage), and `milp` (COBRApy's MILP gap filler).
Transport methods accept `max_additions`, `allowed_connections`, and
`candidate_types` (`A`, `B`, `C`); their defaults are respectively 500 with
`c:e,c:m` and all types for greedy, or 1000 with `c:e` and `A,B` for deadends.
MILP requires `universal_model` and `objective`, and accepts `minimum_flux`
(0.05), `penalties`, and `max_additions` (100). Exchange and demand generation
are deliberately unsupported.

Pass values directly with `--max-additions` and repeated
`--allowed-connection c:e`, or through an optional JSON `--parameters` file.
Direct flags override that file; its `method` key is invalid because
`--method` is authoritative.

Every result directory contains `gapfilled-model.json`, `gapfilled-model.xml`,
`gapfill-report.json`, and `gapfill-selected-reactions.jsonl`. Reports include
resolved parameters, input checksum, metrics, solver metadata, selected and
already-present routes, and `solved`, `partial`, or `failed` status. The caller
chooses whether downstream work uses the original or gap-filled model.

Canonical APIs: [`implement_pathway_files`][thg_protocol.pathway.workflow.implement_pathway_files],
[`implement_pathway`][thg_protocol.pathway.workflow.implement_pathway],
[`gapfill_model`][thg_protocol.gapfill.core.gapfill_model], and
[`GapfillResult`][thg_protocol.gapfill.core.GapfillResult]. Legacy
[`generate_candidates`][thg_protocol.gapfill.core.generate_candidates] and
[`run_pipeline`][thg_protocol.gapfill.core.run_pipeline] remain available for
compatibility.
