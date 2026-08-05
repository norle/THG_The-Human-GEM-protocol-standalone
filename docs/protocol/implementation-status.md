# Capability and evidence status

!!! info "Evidence baseline"
    This matrix is keyed to [`capability-evidence.json`](capability-evidence.json).
    It reports implementation, evidence strength, callable scope, historical
    relationship, and published-artifact reproduction independently.

The maintained evidence baseline is commit `0c91fdec325df12f25ef13819525e830a4cec1e8`
on branch `refactoring-cleanup`. The legacy source commit is recorded in the
registry but lives in an adjacent dirty checkout, so no parity is claimed until
isolated cases run. A frozen publication artifact is not present. The registry
is authoritative for the controlled vocabulary and source/test paths behind
each row.

| Registry ID | Publication concept | Implementation | Verification | Workflow coverage | Legacy relationship | Published reproduction | Known difference or evidence boundary |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `reference.annotation.reactions` | Reference reaction identification | Implemented | Unit-tested | Operation | Not assessed | Not yet verified | One basic identify_reaction fixture is compared; Jaccard, duplicate, and full-file cases remain unverified |
| `reference.annotation.metabolites` | Reference metabolite identification | Implemented | Unit-tested | Operation | Not assessed | Not yet verified | One formula-valid hit fixture is compared; misses, service failures, synonym ties, and batch behavior remain unverified |
| `reference.model_build.annotation` | Reference model annotation enrichment | Implemented | Integration-tested | Operation | Intentional difference | Not yet verified | Enriches an existing model; does not construct the full beta1/beta2 branch |
| `reference.mass_balance` | Formula and mass-balance operations | Implemented | Unit-tested | Operation | Not assessed | Not yet verified | One atom10 vector fixture is compared; legacy substring handling for overlapping element symbols and broader equation/mass-balance behavior remain unverified |
| `reference.gpr.lookup` | GPR lookup and rule construction | Implemented | Unit-tested | Operation | Intentional difference | Not yet verified | One deterministic page-parser fixture is compared; full get_gpr source precedence, complexes, transferred ECs, and stoichiometric parity remain unverified |
| `reference.gpr.location` | GPR location resolution | Implemented | Unit-tested | Operation | Intentional difference | Not yet verified | One basic Mitochondria branch is compared; the compatibility tuple intentionally keys its maintained gene map by the supplied identifier, while legacy rewrites that key to Ensembl; complex-rule preservation, unresolved-location semantics, and fallback behavior remain unverified |
| `database.reconstruction.json` | Normalized-record model reconstruction | Implemented | Integration-tested | Orchestrated stage | Intentional difference | Not yet verified | Reconstructs normalized records and does not harvest live biological sources |
| `database.reconstruction.pickle` | Legacy-pickle model reconstruction | Implemented | Not yet verified | Operation | Intentional difference | Not yet verified | The recorded legacy commit contains no authentic pickle; ignored local 49 MB files are not reproducible fixtures, while a loader regression now prefers serialized subs/prods over generation-time methods |
| `database.harvesting` | Live Human Database harvesting | Not implemented | Not yet verified | N/A | No replacement | Not yet verified | No maintained pathway-list harvesting orchestrator exists |
| `merge.identifier` | Identifier-based model merge | Implemented | Integration-tested | Orchestrated stage | Intentional difference | Not yet verified | Matches identifiers and retains the base model's overlapping stoichiometry |
| `merge.publication_compatible` | Legacy similarity-aware model merge | Not implemented | Not yet verified | N/A | No replacement | Not yet verified | No maintained API ports legacy cross-identifier and chemistry matching |
| `analysis.consistency` | Structural network and consistency reports | Implemented | Integration-tested | Orchestrated stage | Intentional difference | N/A | Current reports are a smaller structural subset and are not scientific convergence |
| `analysis.model_signature` | Semantic COBRA model signature and diff | Implemented | Unit-tested | Operation | No legacy target | N/A | Signature normalization is a maintained comparison contract, not proof of publication parity |
| `workflow.resumable_v1` | Resumable v1 engineering workflow DAG | Implemented | Integration-tested | Workflow-complete for documented v1 scope | No legacy target | N/A | The DAG composes maintained operations; it does not execute complete publication construction |
| `workflow.memote` | MEMOTE validation stage | External integration | Integration-tested | Orchestrated stage | No legacy target | N/A | The executable and report semantics belong to the separately installed MEMOTE tool |
| `workflow.essential_tasks` | Essential metabolic tasks | Archived | Not yet verified | N/A | No replacement | Not yet verified | Ordinary MEMOTE and structural checks do not establish essential-task success |
| `publication.reference_beta1` | Complete THG beta1 construction | Not implemented | Not yet verified | Operation | Not assessed | Not yet verified | No complete maintained reference-branch constructor or frozen target artifact |
| `publication.reference_beta2` | Complete THG beta2 construction | Not implemented | Not yet verified | Operation | Not assessed | Not yet verified | No complete maintained GPR/location and isoenzyme-expansion workflow |
| `publication.final_artifact` | Exact published THG reconstruction | Not implemented | Not yet verified | N/A | Not assessed | Not yet verified | No frozen publication-stage input, artifact, or full workflow result is available |

## Controlled vocabulary

| Axis | Allowed values |
| --- | --- |
| Implementation | `Implemented`, `External integration`, `Archived`, `Not implemented` |
| Verification | `Unit-tested`, `Integration-tested`, `Parity-tested`, `Artifact-reproduction-tested`, `Not yet verified` |
| Workflow coverage | `Operation`, `Orchestrated stage`, `Workflow-complete for documented v1 scope`, `Published stage complete`, `N/A` |
| Legacy relationship | `Verified equivalent`, `Intentional difference`, `No replacement`, `No legacy target`, `Not assessed` |
| Published reproduction | `Verified`, `Not yet verified`, `N/A` |

`Parity-tested` requires an isolated run of both implementations on the same
fixture and a written comparison contract. `Artifact-reproduction-tested`
requires a declared artifact comparison using a semantic model signature and
documented counts. An ordinary maintained-package test, even when it consumes
an old fixture, does not satisfy either definition.

The [legacy API inventory](../legacy-api-inventory.md), [API contracts](../api-contracts.md),
and operation-specific parity contracts will provide the detailed migration
context as the parity harness is added. Until then, rows marked `Not assessed`
or `Intentional difference` must not be promoted to historical equivalence.
