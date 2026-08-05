# Contract: network consistency

- **Legacy:** `functions/functions_network_consistency.py` plus the archived
  task checks under `memote_and_task_analysis/`.
- **Maintained:** `thg_protocol.analysis.consistency` and network reports.
- **Inputs/defaults:** a loaded COBRA model; solver-backed checks are explicit
  and not part of the default offline gate.
- **Result:** named structural reports with deterministic sorted IDs. The
  maintained definitions are: elemental imbalance includes all reactions with
  available formulas; charge imbalance excludes boundary reactions; orphan
  metabolites participate in no reactions; dead ends occur on only one side;
  produced/consumed reports are directional. Reports do not mutate the model
  and do not constitute scientific convergence.
- **Comparison:** formulas, charge, boundary inclusion, reversibility,
  exchange behavior, stoichiometric consistency, unconserved metabolites,
  inconsistent sets, and energy cycles must use separately named semantics.
- **Pass/fail:** a matching report requires the same definition, not merely the
  same label or count.
