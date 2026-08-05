# Contract: database reconstruction

- **Legacy:** prepared-record/pickle generation and reconstruction under
  `generate_data-base/generate_db.py`.
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
  parity. The recorded legacy commit contains no pickle fixture; ignored local
  files are not used by the parity gate, so this case remains pending until a
  sanitized committed snapshot is authorized and available.
