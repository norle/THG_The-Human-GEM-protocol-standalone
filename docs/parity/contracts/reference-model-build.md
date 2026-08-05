# Contract: reference model build

- **Legacy:** `build_model/build_model.py` construction workflow.
- **Maintained:** `thg_protocol.model_build.build_model` and
  `build_model_batch`.
- **Inputs/defaults:** caller-owned JSON/SBML model, explicit output/error/cache
  paths, and injected service clients where supported.
- **Result:** enriched model plus deterministic report and unresolved records;
  input is preserved and output ownership is explicit.
- **Comparison:** annotation writes, mass-balance changes, generated reactions,
  groups, compartments, duplicates, cache behavior, warnings, and exceptions.
- **Scope:** this contract distinguishes annotation enrichment from complete
  THG beta1/beta2 construction; an enriched model cannot pass as an artifact
  from the 2023 protocol paper without the separate phase contracts.
