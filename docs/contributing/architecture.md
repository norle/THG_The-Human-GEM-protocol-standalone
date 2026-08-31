# Architecture

The package separates model ownership, workflow orchestration, analysis, and
external services. Workflows use an evidence → proposal → decision → mutation
boundary and write explicit artifacts rather than silently changing caller-owned
inputs.

Scientific domain packages own algorithms and transformations. The
`thg_protocol.workflow` namespace owns configuration-to-stage adaptation and
DAG composition. Its workflow definitions live in `workflow/beta1/`,
`workflow/beta2/`, and the sibling modules for the other workflows. The
`thg_protocol.runtime` namespace owns generic resumable execution (manifests,
locks, fingerprints, artifacts, and stage iteration). Runtime never discovers
built-in workflows. Shared JSON/SBML model dispatch lives in
`thg_protocol.io.models`.

The reusable model-versus-evidence GPR selection policy lives in
`thg_protocol.gpr.selection`. β2 stages load evidence, call that pure policy,
apply the selected rule, and retain ownership of workflow artifacts,
checkpoints, and provenance.

Service protocols and static clients keep network access, credentials, caching,
and failure behavior injectable. Validation, task suites, MEMOTE, and
solver-backed checks remain separate boundaries so their results cannot be
conflated.

Generated API pages document exact contracts; this page documents the durable
design principles rather than migration audits or parity checkpoints.
