# External-service boundary audit

Reviewed 2026-07-29 as part of the deferred-workflow refactoring checkpoint.
The audit covers the workflows listed in the refactoring plan, including
legacy helpers they import. A direct URL in an orchestrator is not considered a
boundary violation when it is passed to an injected package client; the client
owns the request, retry, timeout, cache, and response normalization behavior.

| Workflow | Package-client path | Remaining legacy fallback |
| --- | --- | --- |
| Batch model builder | `build_model_batch.py` injects BioCyc, KEGG, and Ensembl clients into prefetch, GPR, location, and annotation paths. The batch compatibility helper, legacy auth GPR paths, and generic page helpers now default to package clients. | None identified in the supported read/request paths. |
| Single-model builder | `build_model.py` constructs and passes BioCyc, KEGG, and Ensembl clients through GPR and location annotation. The location helper, equation glycan path, legacy auth-GPR page path, and generic upload helper now use package clients. | None identified. |
| Database builder | `generate_db.py` injects KEGG, BioCyc, and Ensembl clients through pathway, reaction, compound, GPR, and reconstruction operations. Legacy pathway/reaction/compound/gene helpers, GPR entry points, generic page helpers, equation glycan lookups, pathway-link fallbacks, primary-compound resolution, UniProt compatibility lookups, and uploads now use injectable package clients. | None identified. |
| Package database reconstruction | `thg_protocol.database.reconstruct_model_with_services` enriches normalized records through injected KEGG, BioCyc, and Ensembl clients before delegating to the deterministic reconstruction core. | None identified. |
| Package model-file builder | `thg_protocol.model_build.build_model` uses injected clients, explicit JSON caches, explicit output/error paths, and a structured report. | None identified. |
| Metabolite/reaction identification | `thg_protocol.annotation.metabolite_reactions` uses the injectable PubChem client and explicit model/database/report paths. The retry API now uses that same client for every retry round. | None for the characterized retry workflow. |
| Figure generation | Figure APIs receive models and report paths explicitly and perform no network access. | None identified. |

No active raw request branch was identified in the audited production helpers.
Historical `test_algorithms/` scripts are outside the supported package test
path and remain a separate Phase 4 migration task.
