# Contract: reference reaction identification

- **Legacy:** `functions/function_reac_identification.py::identify_reaction`
  and its companion helpers from the committed legacy snapshot
  `b474d80a34ef3bda9754bad3e24a21dc6cf3e57f`.
- **Maintained:** `thg_protocol.annotation.reactions.identify_reaction` and
  related helpers.
- **Inputs/defaults:** an SBML reaction XML fragment, integer row number,
  metabolite-ID regular expression, hydrogen IDs, and water IDs. The first
  parity case explicitly supplies `water_ids=["h2o"]`; the default empty
  water-ID value is not covered by this case. It does not call a live service.
- **Result:** one space-delimited identification row with the reaction number,
  reaction ID, filtered and unfiltered compartments, reversibility, filtered
  reactant/product IDs, filtered and unfiltered rounded stoichiometry, EC
  numbers, gene IDs, and MAR ID in that order. The maintained and legacy
  functions must not mutate input strings or write files.
- **Side effects:** none for `identify_reaction`; file/report behavior belongs
  to the separate `process_reac` contract and is not inferred here.
- **Fixture:** `tests/fixtures/legacy_parity/reference-reaction-identification.json`
  covers filtered hydrogen, reactant/product compartments, stoichiometry, EC,
  gene, MAR, and reaction-ID extraction.
- **Comparison:** extract the legacy module from the recorded commit and run
  each implementation in a separate Python subprocess. Normalize only the
  comma-separated set-derived compartment fields (fields 2 and 3) by sorting
  their members; preserve species and stoichiometry order. The normalized
  output must match the fixture's expected row. This first case does not
  establish parity for `execute_jaccard`, duplicate metabolites, service
  failures, or full-file processing.
- **Difference policy:** any difference in this case fails. Jaccard and
  broader parsing differences require their own contract and must not be
  generalized from this result.
