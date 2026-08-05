# Contract: model merge

- **Legacy:** historical similarity-aware merge under
  `functions_merge_metabolic_networks/`.
- **Maintained current API:** `thg_protocol.merge.merge_models`, an explicit
  identifier-based merge that copies inputs and writes a caller-selected
  output.
- **Comparison:** conflicting formulas/charges/bounds, equal IDs with changed
  chemistry, different IDs with equal chemistry, reversals, GPR rewrites,
  isolated-object cleanup, and report mappings.
- **Difference policy:** the current identifier-based API must not be called
  similarity-aware. An implementation matching the 2023 protocol paper requires a separate
  API and differential contract; it is not present today.
