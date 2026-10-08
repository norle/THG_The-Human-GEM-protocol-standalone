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

Transport methods (`greedy`, `deadends`, `sink-milp`) only propose transports
between the compartment pairs in `allowed_connections`, so that list must name
at least one pair. In the reference workflow, `gate-gapfill` blocks when no
candidate exists while dead ends remain.

## Sink-MILP putative transports

`sink-milp` is the reference default (`configs/reference.json`). It ports the
legacy three-phase putative-transport (PTR) pipeline. Each phase is its own
resumable stage, enabled only for this method and recorded `skipped` otherwise:

1. `generate-gapfill-candidates` pairs metabolites with the same base ID
   (trailing lowercase compartment letters stripped) in an allowed compartment
   pair. A pair qualifies when its ends lie in different network components
   (any type), or both lie in the main component and link two dead ends
   (type A or B). Type A joins a dead-end product and a dead-end substrate, B two
   of the same kind, and C anything else. Components are those of the
   reaction–metabolite graph, numbered by size, with 1 = main. Pairs that an
   existing transport already covers are kept and marked `already-present`.
   Outputs: `ptr-candidates.jsonl` and `ptr-components.json`.
2. `select-gapfill-connectors` joins all components with a minimum spanning
   tree, one reversible PTR per edge. Each component pair is represented by its
   best candidate (A before B before C, then by base). Output: `ptr-connectors.jsonl`.
3. `compute-gapfill-coverage` works on the model with the connectors added.
   For each original component of at least `min_component_size` nodes (default
   4), including the main component, its targets are the reactions that are
   still blocked. It then adds a temporary source for every dead-end substrate
   and a temporary sink for every dead-end product, and records which targets
   each candidate PTR newly unblocks. It writes one line per component to
   `ptr-coverage.jsonl` as each finishes, and a retry reuses the lines of a
   failed or interrupted attempt with the same inputs.

`generate-gapfill-plan` then solves one MILP on the model's solver: maximize
covered targets − `tradeoff_lambda` × selected PTRs (default 0.01; the config
requires 0 < λ < 1), within `max_additions` minus the connectors. The plan
proposes the connectors (`phase: 2`) and the selected PTRs (`phase: 3`), all
reversible at ±1000 with IDs `GAPFILL_PTR_<met1>_<met2>`. The status is
`partial` when the budget binds while coverable targets remain, and `failed`
when the MILP does not solve to optimality.

Two deviations from legacy:

- Targets that the temporary sinks unblock on their own (`sink_only`) are not
  credited to any candidate, so the MILP never pays for what the sinks did.
- A reaction counts as unblocked at a flux of 1e-4. Legacy used 10× the solver
  tolerance, which equals Gurobi's feasibility tolerance and accepted blocked
  reactions. Blocked reactions are found in batches (FASTCC's LP7 for
  irreversible reactions, a random-direction LP pair for reversible ones), not
  with two LPs per reaction.

Temporary sinks and sources never reach the output model. The plan's
`solver.verification` reports, without sinks, which targets the final model
actually unblocks (`verified_unblocked`) and which connectors carry no flux
(`inactive_connectors`). Nothing acts on this report.

The canonical pipeline always runs gapfill before producing a **THG candidate**.
The final gapfill stage writes `thg-reference-gapfilled.json` and `.xml` only after
`gapfill-gate.json` is `passed` or a non-blocking `warning`. Plans, ledgers,
validation reports, semantic diffs, and provenance are exported alongside the
model. This stage-level gate does not replace standalone `validate` and
release export.
Incomplete or failed attempts remain under the run's `failed` directory.
