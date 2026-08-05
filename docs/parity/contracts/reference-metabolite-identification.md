# Contract: reference metabolite identification

- **Legacy:** `functions/function_metabolite_identification.py::identify_metabolite`
  from the committed legacy snapshot
  `b474d80a34ef3bda9754bad3e24a21dc6cf3e57f`. The top-level
  `metabolite_reac_identification/metabolite_reac_identification.py` script is
  orchestration and is not the operation under comparison.
- **Maintained:** `thg_protocol.annotation.metabolites.identify_metabolite` and
  `thg_protocol.annotation.metabolite_reactions` workflows.
- **Inputs/defaults:** metabolite name, molecular formula, identifier, and the
  default similarity threshold (`0.82`). The first fixture injects the same
  recorded compound response into both implementations; no network is used.
- **Result:** one tab-separated annotation row containing the selected synonym,
  formula, lipid-map, KEGG, ChEBI, PubChem CID, InChIKey, InChI, and source
  identifier fields, or `None` for an unresolved match.
- **Side effects:** none for `identify_metabolite`; file/checkpoint behavior
  belongs to `generate_met_annotation` and is not inferred here.
- **Fixture:** `tests/fixtures/legacy_parity/reference-metabolite-identification.json`
  covers a formula-valid hit and all identifiers used in the row.
- **Comparison:** extract the legacy modules from the recorded commit and run
  each implementation in a separate Python subprocess. The normalized output
  must match the fixture's expected row exactly. Misses, service failures,
  synonym ties, and batch checkpoint behavior require separate cases.
- **Pass/fail:** any difference in the hit decision or row fields fails;
  intentional client-boundary differences are documented separately and do not
  establish legacy parity for the network implementation.
