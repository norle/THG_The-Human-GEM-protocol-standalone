# Python API contracts

The installed package is the supported interface. Workflow functions accept
models or input paths explicitly, return structured results, and write only to
paths supplied by the caller.

| API | Input | Result and side effects |
| --- | --- | --- |
| `thg_protocol.pathway.implement_pathway` | JSON model mapping, pathway config, identifier mapping | Mutates and returns the supplied mapping in a result dictionary with added-object counts; no network or file I/O. |
| `thg_protocol.pathway.implement_pathway_files` | Model, config, database, and output paths | Returns the same count dictionary and writes one JSON model to the explicit output path. |
| `thg_protocol.gapfill.run_pipeline` | JSON model path and output directory | Returns output paths/counts and writes phase CSVs plus the final JSON model under the explicit directory. |
| `thg_protocol.analysis.compare.compare_models_from_files` | Two model paths | Returns a comparison mapping; it does not mutate inputs. CSV output is opt-in through `save_comparison_csv`. |
| `thg_protocol.merge.merge_models` | Two COBRA models | Returns a copied model and `MergeReport`; inputs are not mutated. Optional serialization uses `output_path`. |
| `thg_protocol.cell_specific.reduce_model_by_activity` | COBRA model and CSV/MAT/matrix activity data | Returns a copied model and `ActivityReductionReport`; optional serialization uses `output_path`. |
| `thg_protocol.model_build.build_model` | Input/output model paths and optional service clients | Returns `ModelBuildReport`; caches and error reports are written only under explicit or output-relative paths. |

Service-backed APIs accept a `*ClientProtocol` implementation. Production
clients own timeout, retry, pacing, cache, authentication, and response
normalization; static clients in `thg_protocol.services` provide offline test
adapters. Core package imports do not construct clients or make requests.

## Package data decision

No repository model, database, credential, or workflow configuration is
required for package import or CLI help, so no configuration templates or
schemas are shipped as package data in the first release. Configurations,
models, caches, and generated reports remain caller-owned paths. This avoids
embedding large or environment-specific inputs in the wheel; Git LFS and the
artifact inventory document canonical reference files separately.
