# Contract: database reconstruction

- **Legacy:** historical prepared-record/pickle reconstruction under
  `generate_database/`.
- **Maintained:** `reconstruct_model_from_json` and
  `reconstruct_model_from_pickle`.
- **Inputs/defaults:** normalized JSON records or an authentic sanitized legacy
  pickle; all referenced metabolites must be declared.
- **Result:** COBRA model, pathway membership, annotations, and explicit output
  file. Reconstruction performs no live harvesting.
- **Comparison:** use `model_signature` for metabolites, reactions, genes,
  groups, compartments, GPRs, and objective; separately compare unresolved
  references and serialized checksums.
- **Pass/fail:** hand-built dictionaries do not establish authentic pickle
  parity; missing legacy fixtures leave this case pending.
