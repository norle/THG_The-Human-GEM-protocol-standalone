# Contract: location resolution

- **Legacy:** `functions/gpr/get_location_def.py:getLocationnew` from the
  recorded legacy commit.
- **Maintained:** `thg_protocol.gpr.location.resolve_locations` with injected
  location and Ensembl clients.
- **Inputs/defaults:** one offline GPR, gene-name/identifier pair, recorded
  location pages, and an Ensembl mapping injected into both isolated runs.
- **Result:** deterministic location assignments and normalized stoichiometric,
  plain, and Ensembl rules. The compatibility tuple's fourth mapping is not
  part of this case because its key is intentionally different: maintained
  output preserves the supplied identifier while legacy output rewrites it to
  the resolved Ensembl identifier.
- **Comparison:** the basic Mitochondria branch must match after removing only
  legacy square brackets/current grouping parentheses and normalizing location
  capitalization.
- **Scope boundary:** this case does not establish parity for multiple
  locations, complexes spanning compartments, missing pages, identifier
  mismatches, ER false positives, or explicit fallback policy. Cytosol fallback
  is not silently accepted by the maintained API.
