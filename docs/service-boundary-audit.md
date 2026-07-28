# External-service boundary audit

Reviewed 2026-07-28 as part of the deferred-workflow refactoring checkpoint.
The audit covers the workflows listed in the refactoring plan, including
legacy helpers they import. A direct URL in an orchestrator is not considered a
boundary violation when it is passed to an injected package client; the client
owns the request, retry, timeout, cache, and response normalization behavior.

| Workflow | Package-client path | Remaining legacy fallback |
| --- | --- | --- |
| Batch model builder | `build_model_batch.py` injects BioCyc, KEGG, and Ensembl clients into prefetch, GPR, location, and annotation paths. | `functions/function_bm_gdb.py` can still use `urllib` when its compatibility helper is called without a KEGG client. |
| Single-model builder | `build_model.py` constructs and passes BioCyc, KEGG, and Ensembl clients through GPR and location annotation. Unused direct `requests`, PubChemPy, and `urllib` imports were removed. | `functions/gpr/get_location_def.py` retains direct HTTP fallback for callers that omit its client/cache. |
| Database builder | `generate_db.py` injects KEGG, BioCyc, and Ensembl clients through pathway, reaction, compound, GPR, and reconstruction operations. | Legacy database classes and equation helpers retain direct `urllib` fallbacks when invoked without a client. |
| Metabolite/reaction identification | `thg_protocol.annotation.metabolite_reactions` uses the injectable PubChem client and explicit model/database/report paths. | `metabolite_reac_identification_with_retry.py` is an uncharacterized legacy script that calls the compatibility annotation helper without an injected client. |
| Figure generation | Figure APIs receive models and report paths explicitly and perform no network access. | None identified. |

The remaining fallbacks are intentionally retained for old checkout scripts,
but they are not evidence that Phase 5 is complete. The next service-boundary
change should characterize and migrate the retry annotation script and the
legacy database/location fallback helpers, with static-client tests before any
fallback is removed.
