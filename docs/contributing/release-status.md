# THG Protocol: Current State

Last reviewed: 2026-11-09

The package structure cleanup is complete. Supported code
lives under `src/thg_protocol`; tests use package APIs; preserved artifacts have
canonical locations. Historical implementation details remain in Git history.

## Current status

- Branch: `main`
- Latest numerical prerequisite: `ac56d01`; publication evidence through `e2c5e68`
- Supported Python: 3.10–3.12
- Installed commands: `thg-gapfill`, `thg-pathway`, `thg-compare`, and `thg-run`
- Legacy checkout directories: removed and excluded from distributions
- Canonical large artifacts: nine Git LFS paths

The package provides annotation, GPR, pathway, gapfill, comparison, model
construction, merge, network analysis, figures, cell-specific helpers, model
I/O, validation, conservation analysis, and resumable workflows. External
lookups use injectable clients and offline test adapters.

The completed workflow, gapfill, first-class workflow, sGPR, and structural
cleanup plans were consolidated into this state record; Git history retains the
implementation detail.

Implementation and verification claims are tracked in
[`docs/protocol/capability-evidence.json`](../protocol/capability-evidence.json)
and its [status matrix](../protocol/implementation-status.md). Exact
publication-artifact reproduction remains unverified.

## Latest validation

On 2026-11-09 the offline suite passed under Python 3.12: **2,513 passed**,
1,254 warnings, 350.38 seconds. It used GLPK as the default, with Gurobi
available for solver-specific tests. The command excluded `tests/docs` because
MkDocs is installed in the base environment. The saved log is
`publication/ws2/pytest-offline.log`. Six docs checks subsequently passed
separately: three strict-build/link/API checks in the base environment and
three example/CLI checks in `thg_standalone` (logs under `publication/ws2/`). Focused task/importer/publication checks
passed after the input-checksum guard was added; later publication exporters
have their own targeted checks. These results do not establish hosted CI or
final-model scientific validity.

The patched reference task refresh passes VerifyModel 21/21 and Essential
57/57; Full has 255 pass and two invalid mappings. Evidence and exact settings
are in `publication/ws0/numerical-refresh/` and
`publication/benchmark_settings.json`. The corrected WS1 build is in progress;
its stage gates, final VerifyModel, matched MEMOTE validation and independent
replay remain pending. The manuscript is a methods/validation draft, not a
completed model-results paper.

The isolated wheel build, `git lfs fsck`, and source-archive checks were last
run at `601b9d9` and have not been repeated since.

Hosted run `30340915763` passed Python 3.10–3.12 on an earlier commit.

## Reference gapfill: sink-milp

Since 2026-10-08 the reference workflow gapfills with `sink-milp`, the ported
legacy putative-transport pipeline (see `docs/workflows/gapfill.md`). One run
on `runs/thg-reference/artifacts/export-beta2/attempt-0001/thg-beta2-candidate.json`
(12,877 reactions, an older β2 attempt with empty location evidence) with
Gurobi took:

- 3.7 s for candidates, 174 s for coverage (170 s of it on the main component)
  and 0.06 s for the MILP;
- 61 components (25 with at least 4 nodes) and 240 candidates (97 type A, 132 B,
  11 C; 223 main-component-only; 66 already present), giving 7 connectors;
- 1,195 blocked targets, of which 638 are unblocked by the temporary sinks
  alone and 39 are coverable by a candidate;
- an optimal MILP selecting 24 PTRs (7 A, 15 B, 2 C) that cover all 39 coverable
  targets;
- verification without sinks: 32 targets carry flux, and 4 of the 7 connectors
  carry none.

The curated `allowed_connections` (the 21 legacy pairs) contain no c–e and no
m–i pair. The corrected publication reference build is running; no new completed
sink-milp result or gated final model is recorded yet.

## Remaining release gate

Hosted Python 3.10–3.12 CI on the release commit, tagging and archiving are
deferred beyond the internal draft. Before public release, run the matrix on
the chosen commit and record its result. Publication requires user approval. The credential-gated
BioCyc fixture remains optional and does not block the offline release gate.
