# Contract: location resolution

- **Legacy:** historical `gpr_prediction/location_prediction.py` operation.
- **Maintained:** `thg_protocol.gpr.location.resolve_locations` with injected
  location and Ensembl clients.
- **Inputs/defaults:** a GPR, gene identifiers, recorded location pages, and
  an explicit unresolved-location policy.
- **Result:** deterministic location assignments preserving Boolean complex
  relationships, plus unresolved identifiers and lookup errors.
- **Comparison:** multiple locations, missing pages, Ensembl mapping,
  identifier-type mismatch, ER false positives, and deterministic fallback.
- **Difference policy:** Cytosol fallback is not silently accepted unless the
  contract explicitly requests it through `fallback_location`. Any discarded
  client or GPR input fails the maintained contract.
