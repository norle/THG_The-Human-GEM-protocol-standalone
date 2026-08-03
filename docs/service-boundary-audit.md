# External-service boundary audit

Reviewed 2026-07-29 as part of the workflow refactoring checkpoint. A direct
URL in an orchestrator is not considered a
boundary violation when it is passed to an injected package client; the client
owns the request, retry, timeout, cache, and response normalization behavior.

| Workflow | Package-client path | Remaining legacy fallback |
| --- | --- | --- |
| Batch model builder | `thg_protocol.model_build.build_model_batch` injects BioCyc, KEGG, and Ensembl clients through prefetch, GPR, location, and annotation paths. | None identified in the supported read/request paths. |
| Single-model builder | `thg_protocol.model_build.build_model` constructs and passes BioCyc, KEGG, and Ensembl clients through model annotation. | None identified. |
| Database builder | `thg_protocol.database` injects KEGG, BioCyc, and Ensembl clients through normalized reconstruction operations. | None identified. |
| Package database reconstruction | `thg_protocol.database.reconstruct_model_with_services` enriches normalized records through injected KEGG, BioCyc, and Ensembl clients before delegating to the deterministic reconstruction core. | None identified. |
| Package model-file builder | `thg_protocol.model_build.build_model` uses injected clients, explicit JSON caches, explicit output/error paths, and a structured report. | None identified. |
| Metabolite/reaction identification | `thg_protocol.annotation.metabolite_reactions` uses the injectable PubChem client and explicit model/database/report paths. The retry API now uses that same client for every retry round. | None for the characterized retry workflow. |
| Figure generation | Figure APIs receive models and report paths explicitly and perform no network access. | None identified. |

No active raw request branch was identified in the audited production helpers.
Historical characterization inputs are owned by `tests/fixtures` and exercised
through package APIs.
