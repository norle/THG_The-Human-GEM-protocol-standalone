# β2 Open Evidence Integration Progress

Date: 2026-08-14

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

## Verification

- `ruff check src tests`: passed.
- `pytest -q -m 'not online'`: 1,960 passed, 6 skipped, 10 deselected.
- Focused GO/β2/live-snapshot tests: passed, including arbitrary compartment
  IDs, GOA resolution, EC→Rhea candidate GPRs, Reactome catalyst semantics,
  and zero-network snapshot replay.

## Remaining boundary

Credentialed BioCyc online tests were not claimed: the environment could not
resolve `websvc.biocyc.org`. Provider release coverage and biological parity
remain operational verification work, not model-mutation work.
