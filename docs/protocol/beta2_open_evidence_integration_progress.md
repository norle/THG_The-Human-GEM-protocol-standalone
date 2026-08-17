# β2 Open Evidence Integration Progress

Date: 2026-08-17

## Delivered

- Added a pure GO Cellular Component parser/resolver with exact matching,
  synonym support, nearest configured targets, ambiguity rejection, and only
  `is_a`/`part_of` upward traversal.
- Added injectable GOA, UniProt, Rhea, Reactome, and GO ontology boundaries with
  static snapshot adapters and live clients where configured.
- Extended strict β2 configuration for GO targets, source selection, ontology
  and evidence snapshots, release metadata, and checksums.
- Integrated GOA/UniProt location evidence, Rhea candidate GPR evidence,
  Reactome location/catalyst evidence, optional BioCyc CCO evidence, explicit
  precedence, and conflict/unresolved reporting.
- Exported GO release/subgraph, gene-location, reaction-identity,
  reconciliation, unresolved, provenance, and replay snapshot artifacts.
- Kept model mutation downstream of normalized evidence and preserved the
  proposal-first expansion engine.
- Added load-time validation for compartment/GO target completeness, valid and
  unique GO IDs, and pinned live GO metadata.
- Made UniProt SL-to-GO mapping location-specific, preserved duplicate-free
  provenance, rejected unknown Reactome catalyst structures, and gated external
  GPR selection on accepted confidence/status.
- Propagated live GO, GOA, UniProt, Rhea, Reactome, and BioCyc release/URL/
  parser/checksum metadata into `go-release.json`, `beta2-provenance.json`,
  and `beta2-evidence-snapshot.jsonl`; canonicalized file-backed source names.
- Added regression coverage for the new configuration, UniProt, and Reactome
  safety rules plus all five live-provider metadata boundaries.

## Verification

- `ruff check src tests`: passed.
- `pytest -q -m 'not online'`: 1,963 passed, 6 skipped, 10 deselected.
- Focused GO/β2/live-snapshot tests: passed, including arbitrary compartment
  IDs, GOA resolution, EC→Rhea candidate GPRs, Reactome catalyst semantics,
  zero-network snapshot replay, invalid GO registries, and location-specific
  UniProt mappings; live provider metadata and snapshot checksum replay also
  pass.

## Remaining boundary

Credentialed BioCyc online tests were not claimed: the environment could not
resolve `websvc.biocyc.org`. Provider availability and release-specific
biological parity remain operational verification work; live-to-snapshot
provenance and offline replay are covered.
