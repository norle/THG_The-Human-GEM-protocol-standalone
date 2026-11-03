# THG standalone vs. the legacy repository

*Review of 2026-11-02. Standalone: `THG_The-Human-GEM-protocol-standalone`, branch `main` at `3e46b12`. Legacy: the adjacent checkout `THG_The-Human-GEM-protocol` (branch `repo-reorg-temp`, last commit 2025-10-28, three modified files uncommitted).*

## Summary

The standalone repo is a rewrite of the legacy scripts into an installable, tested Python package with resumable workflows. It is far ahead on engineering quality, reproducibility and (in several places) scientific correctness. It does not yet match the legacy repo's scientific scope: three legacy capabilities have no equivalent, and nothing has been shown to reproduce the 2023 paper's models.

Verified today: `pytest -m "not online" --ignore=tests/docs` gives **2355 passed** in 31 s under the `thg_standalone` env. The docs test was skipped because mkdocs is not installed in that env. I did not run the legacy code.

## At a glance

| | Legacy | Standalone |
| --- | --- | --- |
| Python code | about 10,400 lines in about 56 scripts (excluding the committed `thg/` virtualenv) | about 35,600 lines of package code in `src/thg_protocol`, 81 test files |
| Structure | One folder per protocol step, each importing `functions/` by editing `sys.path` | Installable package (`pip install -e .`), Python 3.10–3.12, four CLIs (`thg-run`, `thg-gapfill`, `thg-pathway`, `thg-compare`) |
| Tests | None. `test_algorithms/` holds prototype scripts and notebooks | 2355 tests in unit, integration, characterization and parity folders, plus offline fixtures |
| CI | None | GitHub Actions on Python 3.10, 3.11 and 3.12 with pinned constraints, ruff, wheel build and smoke test, docs build |
| Dependencies | `requirements.txt` with exact pins (cobra 0.24, numpy 1.21, gurobipy 10) | `pyproject.toml` with optional extras (`memote`, `solver`, `figures`, `docs`) and per-version constraint files |
| Docs | README and a figure | mkdocs site with workflow, tool, protocol and API pages |
| Provenance | None. Scripts write models to fixed folders | Resumable runs with attempt directories, checksums, a service/cache ledger and `gate-*` stages that block bad intermediate results |
| Repo weight | `models/` 49 MB, `files/` 332 MB, a venv, `.DS_Store`, `.ipynb_checkpoints` | Large artifacts under Git LFS (nine paths) |

Legacy hygiene problems seen in the scan: wildcard imports (`from functions.functions_mass_balance import *`), about 860 `print` calls, 14 bare `except:` clauses, and `functions/gpr/auth_gpr.py` duplicated in `test_algorithms/`.

## Where standalone is better

1. **Workflow orchestration.** The legacy protocol is four separate scripts run by hand. Standalone has a registered stage DAG (`thg-run reference` runs β1 → β2 → optional Human Database → gapfill → report and export) that resumes after failure and reruns stages when inputs change.
2. **Correctness fixes found while porting.** `docs/contributing/refactoring-changes-2026-10.md` records these, each with a before and after:
   - UniProt location queries were unfiltered by organism and truncated at 500 results.
   - Genes with more than one compartment were dropped (44 of 50 sampled metabolic genes).
   - A GO term was narrowed to a single arbitrary compartment.
   - Objective reactions were merged as duplicates.
   - Isomers and differently bounded reactions were treated as equivalent.
   - A failed gap-fill could leave a half-modified model.
3. **Gap-filling.** The legacy putative-transport (PTR) scripts are ported as `sink-milp`, a resumable four-stage method. It is the default in `configs/reference.json`.
4. **Validation.** Standalone has release profiles and blocking gates. It checks mass and charge balance, stoichiometric consistency, energy-generating cycles and metabolites that internal flux can create or destroy. It can run MEMOTE as an optional external step.
5. **Cleaner external services.** Lookups go through injectable clients with retries, caching, an error ledger and offline test adapters. Legacy code calls services inline.
6. **Honest status tracking.** `docs/protocol/capability-evidence.json` rates each capability separately for implementation, verification, legacy relationship and paper reproduction. It says outright that nothing is yet parity-tested.

## Where standalone is behind or different

| Area | Status in standalone | Source |
| --- | --- | --- |
| Similarity-aware merge | **Implemented as a redesign**, not a port. `generate_merge_plan` links metabolites across IDs by KEGG/ChEBI/HMDB/InChIKey annotations in the same compartment and merges only on identical formula and charge. The legacy name-based matching and consistency-tested reaction addition (`network_reactions_merge_3`–`7`) are not ported, and the two merges have not been run side by side. | `merge.publication_compatible` |
| β2 verification against legacy | β2 **is implemented** (`thg-run beta2`, `workflow/beta2/`, `curation/beta2.py`), but nothing compares its output to legacy THG-beta2 (18,136 reactions, 12,919 metabolites) or the paper. The registry row `publication.reference_beta2` still says "Not implemented"; that entry is stale (evidence commit `0c91fde`, no sources or tests listed). | `publication.reference_beta2` |
| Exact reproduction of the 2023 THG artifact | **Not possible yet.** No frozen paper-stage inputs exist. The README states the workflows do not reproduce the publication artifact. | `publication.final_artifact` |
| Essential metabolic tasks | **Implemented** (`tasks.py`, `raven_tasks.py`): a versioned task contract plus a RAVEN table importer, run only when `task_suite` is configured. No essential-task result for a THG model is recorded, and legacy evaluation was not compared. | `workflow.essential_tasks` |
| Cell-specific algorithms | Legacy ships GIMME, iMAT, FASTCORE and tINIT scripts plus single and multi-round PTR (`ptr_one_round.py`, `ptr_multi_round.py`). Standalone has GIMME, expression consensus, exchange matching and GPR helpers. I found no iMAT, FASTCORE or tINIT code. | `src/thg_protocol/cell_specific/` |
| Live Human Database harvesting | The adapter is deliberately left to the caller, so there is no bundled paper-specific pathway-list adapter. | `database.harvesting` |
| Network analysis | Standalone reports are described as a smaller structural subset of the legacy consistency analysis. | `analysis.consistency` |
| Figures and model comparison | Both exist in the package. Legacy plots are not shown to be reproduced. | `figures/`, `analysis/compare.py` |

## Parity evidence is thin

The status matrix marks almost every capability `Not assessed` or `Intentional difference` for legacy relationship, and none as `Parity-tested`. The few comparisons that exist use one fixture each, for example one `identify_reaction` case, one formula hit and one atom-count vector. Known open items include:

- legacy substring handling for overlapping element symbols;
- GPR source precedence, complexes and transferred ECs;
- the location fallback behaviour.

The project notes (`docs/plans/thg-standalone-project-notes.md`) state that legacy code is a scientific reference but **not** a compatibility target. That is a defensible position, but then the claim "implements THG" should be read as "implements a redesigned protocol".

## Housekeeping observations on the standalone repo

- `docs/contributing/release-status.md` is stale. It was last reviewed 2026-10-02 and lists 2106 passed, while the suite is now 2355. Its remaining release gate (hosted CI on the current head) is not recorded as done.
- *Done 2026-11-02:* the registry and status matrix were re-reviewed against `3e46b12`. β2, essential tasks and the annotation-aware merge changed from "Not implemented"/"Archived" to implemented, and rows were added for gap-filling, GIMME, validation and conservation. Legacy relationships stay "Not assessed" or "Intentional difference", and nothing is marked parity-tested.
- `docs/contributing/refactoring-changes-2026-10.md` dates itself 2026-10-14 and lists a MILP-balancing change as uncommitted. It has since landed, so the report should be refreshed.
- Generated directories (`site/`, `dist/`, `build/`, `runs/*`) sit in the working tree. Confirm they are ignored or LFS-tracked rather than committed.
- `mkdocs` is missing from the `thg_standalone` env, so the docs test fails there. That is expected and matches your notes, but the test could skip itself when mkdocs is absent, as another test already does for gitignored inputs.
- The default branch on the remote is `refactoring-cleanup`, while local work is on `main`. Make sure the two have not diverged.

## Recommendations, in priority order

1. Decide whether the goal is to reproduce the paper or to maintain a redesigned protocol. If reproduction matters, port the similarity-aware merge and build a frozen-input parity test for it (`Parity-tested` needs isolated runs of both implementations on the same fixture).
2. Run two or three end-to-end legacy stages on a small model and record the resulting differences against the standalone output. That would move rows in the matrix out of `Not assessed`.
3. Either port iMAT, FASTCORE and tINIT or document them as dropped, so users of the legacy cell-specific scripts are not surprised.
4. Run an essential-task suite against a built THG model and record the result.
5. Refresh `docs/contributing/release-status.md`, `implementation-status.md` and `docs/contributing/refactoring-changes-2026-10.md`, and run the hosted CI matrix on the current head.
6. Archive the legacy repo (remove its committed virtualenv and large `files/`) once the above is settled, so it stops being an unversioned reference.
