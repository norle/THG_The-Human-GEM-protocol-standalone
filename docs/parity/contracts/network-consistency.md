# Contract: network consistency

- **Legacy:** historical network-consistency and task checks under
  `network_consistency/` and `memote_and_task_analysis/`.
- **Maintained:** `thg_protocol.analysis.consistency` and network reports.
- **Inputs/defaults:** a loaded COBRA model; solver-backed checks are explicit
  and not part of the default offline gate.
- **Result:** named structural reports with deterministic sorted IDs. Reports
  do not mutate the model and do not constitute scientific convergence.
- **Comparison:** formulas, charge, boundary inclusion, reversibility,
  exchange behavior, stoichiometric consistency, unconserved metabolites,
  inconsistent sets, and energy cycles must use separately named semantics.
- **Pass/fail:** a matching report requires the same definition, not merely the
  same label or count.
