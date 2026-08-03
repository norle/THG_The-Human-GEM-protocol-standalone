# Legacy workflow status

The package APIs under `thg_protocol` are the supported interface. All
source-checkout compatibility wrappers, archived workflow scripts, and
historical duplicate test suites have been removed. They are not included in
wheels and must not be used as release-gate evidence.

The complete pre-removal file, symbol, consumer, and contract record remains
in [`legacy-api-inventory.md`](legacy-api-inventory.md). The final removed-file
manifest is authoritative for the closeout.

## Supported replacements

- Model building uses `thg_protocol.model_build` and `thg_protocol.database`.
- Merge and consistency analysis use `thg_protocol.merge` and
  `thg_protocol.analysis`.
- Annotation uses `thg_protocol.annotation` and injected service clients.
- Pathway, gapfill, and comparison workflows use `thg-pathway`, `thg-gapfill`,
  `thg-compare`, or their corresponding package APIs.
- Historical algorithm characterization fixtures used by maintained tests live
  under `tests/fixtures/legacy_characterization/`.

The package contracts in [`api-contracts.md`](api-contracts.md) document the
intentional migration differences, including explicit output paths, copied
model ownership, normalized result objects, and injected external clients.

## Release boundary

Pytest owns the maintained suite under `tests/`. Optional online, solver, and
MEMOTE checks are marked and remain opt-in; they do not restore or depend on
the removed checkout paths.
