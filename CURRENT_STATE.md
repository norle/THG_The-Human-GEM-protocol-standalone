# THG Protocol: Current State

Last reviewed: 2026-10-02

The package structure cleanup is complete. Supported code
lives under `src/thg_protocol`; tests use package APIs; preserved artifacts have
canonical locations. Historical implementation details remain in Git history.

## Current status

- Branch: `refactoring-cleanup`
- Reviewed commit: `00c52cd` plus the 2026-10-02 review fixes
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
[`docs/protocol/capability-evidence.json`](docs/protocol/capability-evidence.json)
and its [status matrix](docs/protocol/implementation-status.md). Exact
publication-artifact reproduction remains unverified.

## Latest validation

On 2026-10-02 the full local suite passed under Python 3.12 with memote and
Gurobi installed: `2106 passed`. The mkdocs tests were run separately, from an
environment with mkdocs installed (`6 passed`). The CI offline selection also
passed with memote unavailable (`2100 passed`), and the solver/memote selection
passed on GLPK. `ruff check` and `ruff format --check` are clean.

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
m–i pair. The reference run has not yet been repeated with sink-milp.

## Remaining release gate

Run the hosted Python 3.10–3.12 package matrix on the current head. If it passes,
record the run here and publish the closeout changes. The credential-gated
BioCyc fixture remains optional and does not block the offline release gate.
