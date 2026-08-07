# THG Standalone Project Notes

This repository is an independent maintained implementation of the THG workflow.
It improves the historical software's architecture, provenance, resumability,
service boundaries, and model-ownership semantics.

## Legacy project relationship

The historical THG repositories and the 2023 protocol paper are useful sources
of scientific context, terminology, examples, and legacy behavior. They are not
compatibility targets and do not define the maintained package's behavioral
specification. Documentation and development decisions should be based on the
current package contracts, tests, and workflow artifacts.

Historical or migration-specific material may still be useful to maintainers,
but it should be kept in developer, contributing, or archival documentation
rather than presented as a requirement for normal users.

## Human Database source integration

The Human Database workflow is functional for normalized offline records and for
live collection through an explicit source adapter. `harvest_snapshot` provides
bounded retries, deterministic caching, an error ledger, and normalized-record
reconstruction. The caller supplies the adapter that owns source-specific
queries, credentials, rate limits, and network policy.

This adapter boundary is intentional and is not a correctness gap. A future
release may provide a bundled pathway-list/source adapter and expose it through
the resumable CLI workflow. That would improve turnkey integration while
preserving the existing harvesting and reconstruction primitives.
