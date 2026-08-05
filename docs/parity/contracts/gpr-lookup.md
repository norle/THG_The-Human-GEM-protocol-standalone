# Contract: GPR lookup

- **Legacy:** `functions/gpr/gpr_def.py::pattern_match_org_3` from committed
  snapshot `b474d80a34ef3bda9754bad3e24a21dc6cf3e57f`.
- **Maintained:** `thg_protocol.gpr.lookup.parse_gene_pairs`. Full
  `get_gpr` parity is a separate contract because the legacy implementation
  performs additional live-page and gene-page parsing.
- **Inputs/defaults:** one recorded BioCyc-like HTML page containing gene and
  identifier pairs. No network, credentials, or client state is used.
- **Result:** sorted `(gene symbol, identifier)` pairs. The first fixture has
  unique well-formed pairs; duplicate handling and malformed pages remain
  separate cases.
- **Side effects:** none.
- **Fixture:** `tests/fixtures/legacy_parity/gpr-page-parser.json`.
- **Comparison:** extract the legacy GPR modules from the recorded commit and
  run each parser in a separate Python subprocess. The sorted pair result must
  match exactly.
- **Pass/fail:** any difference in the declared fixture fails. This result does
  not establish Boolean AND/OR, complex, isoform, transferred-EC, source
  precedence, or stoichiometric GPR parity.
