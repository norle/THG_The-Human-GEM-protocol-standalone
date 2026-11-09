# Capability and evidence status

!!! info "Evidence baseline"
    This matrix is keyed to [`capability-evidence.json`](capability-evidence.json).
    It reports implementation, evidence strength, callable scope, historical
    relationship, and reproduction of the 2023 protocol paper's artifact
    independently.

The maintained evidence baseline was re-reviewed on 2026-11-02 against commit
`3e46b12a1408a03381a66628b1fc90a3a74d6dd4` (`3e46b12`); the offline suite (2355 tests, docs build excluded) passed at
that commit. Changes after it are not treated as verified evidence until their
relevant checks are rerun. The legacy source commit is recorded in the registry
but lives in an adjacent dirty checkout, so no parity is claimed until isolated
cases run. A frozen artifact from the 2023 protocol paper is not present. The
registry is authoritative for the controlled vocabulary and source/test paths
behind each row.

| Registry ID | 2023 protocol paper concept | Implementation | Verification | Workflow coverage | Legacy relationship | Paper-artifact reproduction | Known difference or evidence boundary |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `reference.annotation.reactions` | Reference reaction identification | Implemented | Unit-tested | Operation | Not assessed | Not yet verified | Archived reaction-identification fixtures are replayed through the maintained API and checked against their recorded expectations; the legacy code was not run side by side. Jaccard, duplicate, and full-file cases remain unverified |
| `reference.annotation.metabolites` | Reference metabolite identification | Implemented | Unit-tested | Operation | Not assessed | Not yet verified | Archived formula-valid hit fixtures are replayed through the maintained API against a static PubChem client; the legacy code was not run side by side. Misses, service failures, synonym ties, and batch behavior remain unverified |
| `reference.model_build.annotation` | Reference model annotation enrichment | Implemented | Integration-tested | Operation | Intentional difference | Not yet verified | Enriches an existing model; does not construct the full beta1/beta2 branch |
| `reference.mass_balance` | Formula and mass-balance operations | Implemented | Unit-tested | Operation | Not assessed | Not yet verified | balance_equation now minimises integer coefficients with a MILP on the COBRA solver and returns a solution when several exist; the earlier atom10 vector comparison with legacy was not repeated. Legacy substring handling for overlapping element symbols and broader equation/mass-balance behavior remain unverified |
| `reference.gpr.lookup` | GPR lookup and rule construction | Implemented | Unit-tested | Operation | Intentional difference | Not yet verified | One deterministic page-parser fixture is compared; full get_gpr source precedence, complexes, transferred ECs, and stoichiometric parity remain unverified |
| `reference.gpr.location` | GPR location resolution | Implemented | Unit-tested | Operation | Intentional difference | Not yet verified | One basic Mitochondria branch is compared; the compatibility tuple intentionally keys its maintained gene map by the supplied identifier, while legacy rewrites that key to Ensembl; complex-rule preservation, unresolved-location semantics, and fallback behavior remain unverified. UniProt/GO compartment resolution used by the beta2 workflow is tracked under publication.reference_beta2 |
| `database.reconstruction.json` | Normalized-record model reconstruction | Implemented | Integration-tested | Orchestrated stage | Intentional difference | Not yet verified | Reconstructs normalized records and does not harvest live biological sources |
| `database.reconstruction.pickle` | Legacy-pickle model reconstruction | Implemented | Not yet verified | Operation | Intentional difference | Not yet verified | The recorded legacy commit contains no authentic pickle; ignored local 49 MB files are not reproducible fixtures, while a loader regression now prefers serialized subs/prods over generation-time methods |
| `database.harvesting` | Live Human Database harvesting | Implemented | Integration-tested | Orchestrated stage | Intentional difference | Not yet verified | A paper-specific pathway-list adapter is not bundled; live access is injected and credential-owned. Cached responses are keyed by adapter release and are not served after a refresh failure from an earlier release |
| `merge.identifier` | Identifier-based model merge | Implemented | Integration-tested | Orchestrated stage | Intentional difference | Not yet verified | Metabolites, reactions and genes with the same ID are the same object; when overlapping reaction stoichiometry differs the base reaction is kept and the difference is reported. Incoming metabolites that share an ID but not a species are renamed with the __incoming suffix. Annotation-based linking is tracked under merge.publication_compatible |
| `merge.publication_compatible` | Similarity-aware model merge (cross-identifier and chemistry matching) | Implemented | Unit-tested | Orchestrated stage | Intentional difference | Not yet verified | Reviewable merge plan: metabolites with different IDs are linked by shared KEGG, ChEBI, HMDB or InChIKey annotations in the same compartment and merged only when formula and charge are identical; other linked pairs are kept separate with a named decision. Reactions with different IDs merge only on a shared annotation and identical stoichiometry. Legacy also compared names and tested consistency while adding reactions in groups (network_reactions_merge_3 to 7); neither is ported, and the legacy merge was not run side by side |
| `analysis.consistency` | Structural network and consistency reports | Implemented | Integration-tested | Orchestrated stage | Intentional difference | N/A | Current reports are a smaller structural subset (components, orphan metabolites, formula balance) and are not scientific convergence; stoichiometric consistency, loop and leakage checks live in workflow.validation |
| `analysis.model_signature` | Semantic COBRA model signature and diff | Implemented | Unit-tested | Operation | No legacy target | N/A | Signature normalization is a maintained comparison contract, not proof of parity with the paper |
| `workflow.resumable` | Resumable registered engineering workflow DAG | Implemented | Integration-tested | Workflow-complete for documented scope | No legacy target | N/A | The DAG composes maintained operations; it does not execute the paper's complete construction |
| `workflow.memote` | MEMOTE validation stage | External integration | Integration-tested | Orchestrated stage | No legacy target | N/A | The executable and report semantics belong to the separately installed MEMOTE tool |
| `workflow.essential_tasks` | Essential metabolic tasks | Implemented | Integration-tested | Orchestrated stage | Intentional difference | Not yet verified | Versioned JSON task contract with RAVEN semantics (temporary source and sink reactions, closed medium by default) and an importer for RAVEN task tables, which includes the essential-task table. Validation and final-THG run a suite only when task_suite is configured. Legacy evaluation was not run side by side, and a release-level essential-task result for a THG model is not recorded |
| `publication.reference_beta1` | Complete THG beta1 construction | Implemented | Integration-tested | Workflow-complete for documented scope | Not assessed | Not yet verified | The maintained release is fixture-sanctioned and policy-scoped; it is not a claim of reproducing the 2023 publication artifact. Objective reactions are kept out of duplicate merging, and unbalanced reactions are fixed automatically only when adding water and protons balances them |
| `publication.reference_beta2` | Complete THG beta2 construction | Implemented | Integration-tested | Workflow-complete for documented scope | Not assessed | Not yet verified | Resolves GPR and location evidence (UniProt, GO, GOA, BioCyc and KEGG records), infers complex and isoenzyme locations, plans and applies compartment expansion, and gates the candidate (thg-run beta2). It consumes a verified beta1 artifact or a declared beta1-equivalent input and is research-supported. Its output has not been compared with legacy THG-beta2, and the archived HumanCyc/MetaCyc GPR comparison is incomplete because the BioCyc account lacks access (docs/protocol/live-beta2-gpr-comparison.md) |
| `publication.final_artifact` | Exact THG reconstruction from the paper | Not implemented | Not yet verified | N/A | Not assessed | Not yet verified | No frozen paper-stage input, artifact, or full workflow result is available; the reference workflow gapfills with sink-milp and has not been rerun end to end with it |
| `workflow.gapfill` | Gap-filling with putative transport reactions | Implemented | Integration-tested | Orchestrated stage | Intentional difference | Not yet verified | sink-milp (default in configs/reference.json) ports the legacy putative-transport method as four resumable stages and changes how sink-only targets are credited and which flux threshold is used (docs/workflows/gapfill-sink-milp.md). The legacy gapfill scripts cited there are not in the recorded legacy checkout, so the listed sources are the nearest putative-transport scripts. It has been run once on an earlier beta2 attempt; the reference run has not been repeated with it |
| `workflow.cell_specific.gimme` | Cell-specific model construction (GIMME) | Implemented | Unit-tested | Orchestrated stage | Intentional difference | Not yet verified | No Troppo or Cobamp dependency and the input model is not mutated. One frozen small GIMME reference (tests/fixtures/gimme_legacy_reference.json) is the only legacy-derived target. iMAT, FASTCORE, tINIT and multi-round PTR from the legacy cell-specific folder have no maintained equivalent. Expression input must be pre-normalized |
| `workflow.validation` | Reusable validation checks and release gates | Implemented | Integration-tested | Orchestrated stage | Not assessed | N/A | Mass and charge balance, stoichiometric consistency, identity and annotation conflicts, metabolite leakage, energy-generating cycles and loop detection, with a release-full profile that blocks on unevaluable balance and on energy cycles. Balance suggestions use a MILP in the model's own solver. Legacy checks were not compared |
| `analysis.conservation` | Unconserved-metabolite analysis and repair review | Implemented | Integration-tested | Orchestrated stage | No legacy target | N/A | Finds, reviews and proposes fixes for unconserved metabolites using MEMOTE's consistency support; a maintained workflow, not part of the paper's protocol |

## Publication validation update (2026-11-09)

The registry above retains its 2026-11-02 evidence baseline. Later checks are
recorded in `publication/`, without upgrading legacy parity or reproduction
claims. The offline suite passed 2,513 tests in 350.38 seconds, excluding the
MkDocs-dependent docs tests (`publication/ws2/pytest-offline.log`). The shared
task runner now records solver tolerances and primal residuals, and rejects
numerically unreliable optimal solves as unresolved errors (`ac56d01`).

Human-GEM 2.1.1 with MAR20193 blocked has refreshed results of VerifyModel
21/21, Essential 57/57, and Full 255 pass / 257 total with two invalid mappings
(`publication/ws0/numerical-refresh/`). That first refresh did not verify its
native Gurobi thread count and requires a corrected, thread-verified refresh
before a matched comparison; see its `limitations.json`. Archived real-model consolidation and
parent-balance proposal measurements are in `publication/ws2/correctness.json`.
The corrected WS1 build, final-model evaluation and independent replay remain
incomplete. No final THG model or 2023-artifact reproduction is claimed.

## Controlled vocabulary

| Axis | Allowed values |
| --- | --- |
| Implementation | `Implemented`, `External integration`, `Archived`, `Not implemented` |
| Verification | `Unit-tested`, `Integration-tested`, `Parity-tested`, `Artifact-reproduction-tested`, `Not yet verified` |
| Workflow coverage | `Operation`, `Orchestrated stage`, `Workflow-complete for documented scope`, `Published stage complete`, `N/A` |
| Legacy relationship | `Verified equivalent`, `Intentional difference`, `No replacement`, `No legacy target`, `Not assessed` |
| Published reproduction | `Verified`, `Not yet verified`, `N/A` |

`Parity-tested` requires an isolated run of both implementations on the same
fixture and a written comparison contract. `Artifact-reproduction-tested`
requires a declared artifact comparison using a semantic model signature and
documented counts. An ordinary maintained-package test, even when it consumes
an old fixture, does not satisfy either definition.

Rows marked `Not assessed` or `Intentional difference` must not be promoted to
historical equivalence without additional evidence.
