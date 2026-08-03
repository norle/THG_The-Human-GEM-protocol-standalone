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
| `thg_protocol.annotation.metabolites.generate_met_annotation` | Metabolite records, an explicit annotation output path, and an optional PubChem client | Returns annotated and unresolved records; writes the annotation and failure reports beside the supplied output path. |
| `thg_protocol.annotation.metabolites.process_annotation` | An explicit tab-separated annotation path | Returns a normalized annotation mapping; reads only the supplied file and does not write output. |
| `thg_protocol.annotation.metabolite_reactions.run_metabolite_reaction_identification` | Model path, database path, output directory, and optional PubChem client | Returns `MetaboliteReactionResult`; writes model, annotation, and failure files only under the supplied output locations. |

Service-backed APIs accept a `*ClientProtocol` implementation. Production
clients own timeout, retry, pacing, cache, authentication, and response
normalization; static clients in `thg_protocol.services` provide offline test
adapters. Core package imports do not construct clients or make requests.

The former source-checkout annotation wrapper was retired. New package callers
must provide paths explicitly; package APIs do not silently write into
repository directories.

## Contract groups used by the legacy inventory

Every mapped legacy symbol is assigned to one of these groups in
[`legacy-api-inventory.md`](legacy-api-inventory.md). The group descriptions
make the parity comparison explicit instead of treating matching function
names as evidence.

| Group | Inputs and defaults | Result and ownership | Side effects and errors | Evidence |
| --- | --- | --- | --- | --- |
| `C1` configuration, pathway core, and GPR AST | JSON-like mappings, strings, AST/GPR expressions, and explicit optional config paths; no repository-relative default is used by package APIs. | Pathway helpers mutate only the mapping explicitly supplied to the mutating API; pure parsers return new values. | No network or file writes for pure helpers. Invalid equations, identifiers, or expressions raise the documented `ValueError`/parser errors. | `tests/unit/test_config_api.py`, `test_pathway_api.py`, `test_gpr_api.py`, `test_gpr_wrapper.py`. |
| `C2` formula and mass balance | Formula/equation strings and optional reaction identifiers; numeric helpers accept the same coefficient-compatible values as the package functions. | Returns normalized atom mappings, coefficient lists, or structured imbalance data; inputs are not mutated. | No solver or network is required. Unsupported formulas and unsatisfiable equations raise `ValueError`. | `tests/unit/test_mass_balance_api.py` and compatibility boundaries. |
| `C3` model operations | COBRA models, with optional explicit output paths. | Merge and cleanup return copies; analysis returns stable IDs/reports. `MergeReport` replaces legacy positional overlap lists. | Inputs are not mutated. Serialization occurs only at `output_path`; solver-backed checks are optional and never implicit in structural APIs. | `test_merge_api.py`, `test_consistency_api.py`, `test_network_analysis_api.py`, compatibility boundaries. |
| `C4` annotation and reaction workflows | Records, model/input paths, explicit output paths, and injected service clients. | Returns normalized mappings or `MetaboliteReactionResult`; model annotation writes only caller-selected files. | Default tests use static clients. Network errors are client errors; unresolved records are returned in the failure/unresolved schema rather than silently dropped. | Annotation and metabolite-reaction unit tests. |
| `C5` database and model build | JSON/XML/pickle input paths, explicit model/output/error/cache paths, normalized records, and optional service clients. | Returns `ModelBuildReport`, model objects, or database records; caller owns input models and output paths. | Cache and error reports are output-relative or explicit. Credentialed harvesting is not performed during import or pure reconstruction. | Database/model-build unit tests and batch boundary integration test. |
| `C6` comparison, figures, and cell-specific helpers | Models plus explicit report/figure/output paths; activity data may be CSV, MAT, or matrix-like input. | Comparison and figure APIs return report/result objects; cell-specific reduction returns a copied model and `ActivityReductionReport`. | No input mutation. Plotting is optional and lazy; output directories are created only when requested. | Comparison, figures, compaction, and cell-specific unit tests. |
| `C7` installed and compatibility CLIs | Explicit positional/input options, `--help`, and output-directory arguments. | Success is exit code `0`; help performs no model/network work. Workflow commands return structured output artifacts under the selected path. | Invalid options use argparse's non-zero exit; optional dependencies are loaded after parsing. Installed commands are `thg-gapfill`, `thg-pathway`, and `thg-compare`. The legacy comparison CLI requires `--output-dir`; the package CLI makes CSV output opt-in. | `tests/unit/test_legacy_cli_contracts.py`, CLI unit tests, and subprocess smoke tests. |
| `C8` archived characterization fixtures | Small deterministic fixtures are passed through package functions; timestamps, temporary paths, object identities, and unordered mappings are normalized. | Tests compare only documented values, schemas, IDs, and counts. They do not establish archived scripts as supported APIs. | Historical fixture trees remain outside default pytest collection. | `tests/integration/test_legacy_algorithm_apis.py`. |
| `C9` external services | Service protocol implementations are injected; production clients own timeout, retry, pacing, cache, authentication, and normalization. | Static clients provide deterministic records; package functions return normalized results. | No live requests in the default suite. Credential-gated BioCyc remains opt-in and is not a release blocker. | Service-client tests and opt-in online fixture. |

### Intentional migration differences

The following differences are part of the supported migration path and are
tested rather than accidental:

- package annotation and model-building APIs require explicit output paths;
  the retired source-checkout wrappers are not supported;
- package merge returns a copied model and `MergeReport` instead of legacy
  positional overlap lists;
- package cleanup and visualization require explicit report/model paths;
- service-backed APIs use injected protocol clients and do not mutate global
  proxy/session state;
- archived solver-heavy workflows and full-model MEMOTE/task checks are not
  represented as installed commands or offline release evidence.

## Package data decision

No repository model, database, credential, or workflow configuration is
required for package import or CLI help, so no configuration templates or
schemas are shipped as package data in the first release. Configurations,
models, caches, and generated reports remain caller-owned paths. This avoids
embedding large or environment-specific inputs in the wheel; Git LFS and the
artifact inventory document canonical reference files separately.
