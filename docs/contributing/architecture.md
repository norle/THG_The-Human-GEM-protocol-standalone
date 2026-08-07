# Architecture

The package separates model ownership, workflow orchestration, analysis, and
external services. Workflows use an evidence → proposal → decision → mutation
boundary and write explicit artifacts rather than silently changing caller-owned
inputs.

The workflow registry defines DAG stages, manifests, locks, fingerprints, and
artifact roles. Service protocols and static clients keep network access,
credentials, caching, and failure behavior injectable. Validation, task suites,
MEMOTE, and solver-backed checks remain separate boundaries so their results
cannot be conflated.

Generated API pages document exact contracts; this page documents the durable
design principles rather than migration audits or parity checkpoints.
