# Legacy API inventory and removal scope

Reviewed: 2026-07-31  
Inventory count: 82 Python files outside `src/` and the maintained `tests/`
tree.

This is the executable inventory for the maintained package compatibility
boundary.
Status is assigned from contract and evidence, not filename similarity.
Models, datasets, reports, and research artifacts are outside the deletion
scope.

## Status and evidence keys

| Status | Meaning | Removal condition |
| --- | --- | --- |
| `Equivalent` | Compatibility entry point delegates to the package with the same supported contract. | Remove after all callers migrate and evidence tests remain green. |
| `Intentional difference` | Package replacement exists, but a historical default, mutation, return shape, or output convention changed. | Remove after callers migrate from the documented adapter contract. |
| `Archived` | Historical source-checkout workflow or test; not an installed-release interface. | Remove only with an explicit owner/replacement or unsupported-workflow decision. |
| `No replacement` | Research or credentialed helper with no promised package contract. | Separate maintainer/artifact decision required. |

Evidence keys:

- `C1`: config, pathway, GPR wrapper, and pure re-export parity tests in
  `tests/unit/`.
- `C2`: mass-balance and compatibility-boundary tests.
- `C3`: merge, consistency, network, and compatibility tests.
- `C4`: annotation and metabolite-reaction tests.
- `C5`: database/model-build tests and the batch boundary integration test.
- `C6`: comparison, figures, compaction, and cell-specific tests.
- `C7`: gapfill/pathway/comparison/workflow CLI, legacy CLI contract, and
  installed-style CLI tests. The maintained installed command set is
  `thg-gapfill`, `thg-pathway`, `thg-compare`, and `thg-run`.
- `C8`: `tests/integration/test_legacy_algorithm_apis.py`; selected fixture
  characterization through package APIs, not release evidence for old code.
- `C9`: static service-client/GPR tests and the opt-in online fixture.

The detailed input/output/mutation/side-effect contracts referenced here are
in [`docs/api-contracts.md`](api-contracts.md).

## Compatibility symbols

The table preserves the complete pre-removal supported symbol list. The
compatibility modules themselves are now removed; names not listed here were
never supported legacy imports.

| Exact legacy path/import path | Symbols | Package replacement | Status | Evidence / consumers | Removal condition |
| --- | --- | --- | --- | --- | --- |
| `functions/__init__.py` (`functions`) | `get_model_paths`, `load_config`, `resolve_all_compartments`, and all names in `_PATHWAY_BUILDER_EXPORTS` | `thg_protocol.config`, `thg_protocol.pathway` | Equivalent | C1; compatibility tests | Migrate `functions.*` callers. |
| `functions/config.py` (`functions.config`) | `get_compartments`, `get_model_paths`, `get_project_root`, `load_config`, `resolve_all_compartments`, `resolve_compartment_abbreviation` | `thg_protocol.config` | Equivalent | C1 | Migrate imports. |
| `functions/pathway_builder.py` (`functions.pathway_builder`) | `add_compartment`, `build_reaction_from_config`, `check_pathway_exists`, `create_compartment_metabolites`, `create_compartment_reactions`, `create_metabolite_in_new_compartment`, `find_metabolite_by_annotation`, `find_metabolite_by_formula_in_model`, `find_metabolite_robust`, `get_metabolite_id_base`, `get_next_metabolite_id`, `get_next_reaction_id`, `parse_reaction_equation`, `parse_universal_reaction`, `select_pathway_metabolites`, `substitute_compartment_abbreviations` | `thg_protocol.pathway.core` | Equivalent | C1 | Migrate imports. |
| `functions/function_annotate_cobra_model.py` | `annotate_cobra_model` | `thg_protocol.annotation.model.annotate_cobra_model` | Intentional difference | C4 | Migrate to explicit output paths. |
| `functions/function_reac_identification.py` | `process_reac`, `gather_kegg_metabolites`, `replace_met_id_by_met_kegg`, `execute_jaccard`, `process_jaccard`, `identify_reaction`, `jaccard` | `thg_protocol.annotation.reactions` | Equivalent | C4/C8 | Migrate imports. |
| `functions/function_metabolite_identification.py` | `generate_met_annotation`, `process_annotation` | `thg_protocol.annotation.metabolites` | Intentional difference | C4; explicit-path test | Migrate from historical default path. |
| `functions/functions_mass_balance.py`, `functions/equations_bm_gdb.py` | `Glycan`, `Reformulation`, `AddMissingAtom`, `CountAtom`, `RxnBalance2`, `RxnParam2Eq`, `WrapRxnSubsProdParam`, `UnwrapRxnSubsProdParam`, `Proton`, `Water`, `add_extra_compound`, and aliases `RxnCompare`, `atom10`, `formula_atoms`, `missing_atoms`, `MissingAtom`, `gcd`, `reaction_compare` | `thg_protocol.model_build.mass_balance`, `thg_protocol.glycan` | Intentional difference | C2 | Migrate formula callers. |
| `functions/functions_merge_metabolic_networks.py` | cleanup helpers; `network_metabolites_merge`/`_2`/`_3`, `network_genes_merge`/`_2`, `network_reactions_merge`/`_2`–`_7`, `MergeReport`, `merge_models`, `merge_models_from_paths` | `thg_protocol.merge` | Intentional difference | C3; merge compatibility test | Migrate from positional overlap lists. |
| `functions/functions_network_consistency.py` | all `test_*` checks, `imbalance_test`, `reaction_balance`, and imported package checks listed in `__all__` | `thg_protocol.analysis.consistency` | Intentional difference | C3 | Migrate consistency callers. |
| `functions/gpr/ast_gpr.py` | `divide_gpr_in_ors`, `compare_ast`, `deduplicate_gpr`, `reduce_gpr`, `sanitize_gpr` | `thg_protocol.gpr.ast_gpr` | Equivalent | C1 | Migrate imports. |
| `functions/gpr/auth_gpr.py`, `functions/gpr/gpr_def.py` | `read_env_biocyc`, `setup_biocyc_session`, `get_ecnumber_biocyc_html`, `get_html`, `getGPR`, `pattern_match_org`, `match_biocyc_page`, `_fetch_kegg_from_ec_html`, `parse_gene_pairs` | package service clients and `thg_protocol.gpr.lookup` | Intentional difference | C9 | Migrate to injected clients. |
| `functions/gpr/get_location_def.py` | `get_html`, `create_dict`, `multiple_replace_new`, `getLocationnew`, `getLocation` | `thg_protocol.gpr.location` and service clients | Intentional difference | C9 | Migrate location callers. |
| `functions/ensembl_client.py` | `fetch_ensembl_annotations` | `thg_protocol.services.ensembl.EnsemblClient` | Intentional difference | C9 | Migrate to client protocol. |
| `functions/analyze_annotations.py` | `build_parser`, `main`, `analyze_model_annotations`, `extract_metabolite_annotations` | `thg_protocol.annotation.model_annotations` | Equivalent | C4 | Migrate CLI callers. |
| `functions/build_id_database.py` | `build_database_from_annotations`, `save_database`, `build_database_from_model`, `build_parser`, `main` | annotation/database package APIs | Intentional difference | C4/C5 | Migrate database callers. |
| `build_model/build_model.py`, `build_model/build_model_batch.py` | `build_parser`, `main` | `thg_protocol.model_build` | Intentional difference | C5/C7 | Migrate scripts. |
| `build_model/print_biocyc_compartments.py` | `build_parser`, `main` | `thg_protocol.database.summarize_biocyc_compartments` | Equivalent | C5 | Migrate report callers. |
| `compare_models/compare_compartements.py`, `compare_models/compare_models.py` | `normalize_stoichiometry`, `comp_compare`, `print_comparison`, `save_csv`, `build_parser`, `main` | `thg_protocol.analysis.compare`, `thg-compare` | Intentional difference | C6/C7 | Migrate CLI callers. |
| `gapfill/gapfill.py` | `build_parser`, `main` | `thg_protocol.gapfill.cli`, `thg-gapfill` | Intentional difference | C7 | Migrate command callers. |
| `generate_data-base/generate_db.py`, `make_model_from_pkl.py`, `resume_db_gen.py` | `build_parser`, `main` | `thg_protocol.database`, `thg_protocol.model_build` | Intentional difference | C5/C7 | Migrate pickle/output callers. |
| `generate_figures/create_figure.py` | `build_parser`, `main` | `thg_protocol.figures` | Intentional difference | C6/C7 | Migrate figure callers. |
| `implement_pathway/pathway_implementation.py` | `build_parser`, `main` | `thg_protocol.pathway`, `thg-pathway` | Intentional difference | C7 | Migrate command callers. |
| `cell_type_specific_model/match_exch_rxns.py` | `match_exch_rxns` | `thg_protocol.cell_specific.match_exchange_reactions` | Equivalent | C6 | Migrate imports. |
| `cell_type_specific_model/model_reduce.py` | `model_reduce`, `build_parser`, `main` | `thg_protocol.cell_specific.reduce_model_by_activity` | Intentional difference | C6/C7 | Migrate to explicit output paths. |
| `network_analysis/compaction.py` | `are_reactions_proportional`, `combine_identical_reactions`, `full_compaction` | `thg_protocol.analysis.compaction` | Equivalent | C6 | Migrate imports. |
| `network_analysis/find_components.py` | `find_network_components` | `thg_protocol.analysis.network` | Intentional difference | C3 | Migrate explicit cleanup/report callers. |
| `metabolite_reac_identification/metabolite_reac_identification.py`, `_with_retry.py` | `build_parser`, `main` | `thg_protocol.annotation.metabolite_reactions` | Intentional difference | C4/C7 | Migrate to result object and explicit paths. |
| `merge_metabolic_netowrks_and_network_consistency/merge_metabolic_networks.py` | `build_parser`, `main` | `thg_protocol.merge`, `thg_protocol.analysis.consistency` | Intentional difference | C3/C7 | Migrate report callers. |
| `tools/list_pathway_reactions.py` | `main` | `thg_protocol.pathway.kegg_listing.list_pathway_reactions` | Equivalent | C7 | Migrate imports. |
| `utils/json_to_sbml.py` | `main` | `thg_protocol.io.convert_json_to_sbml` | Equivalent | C3 | Migrate imports. |

`cell_type_specific_model/transcriptomics.py` is mixed: overlapping parser
helpers are characterized by `thg_protocol.cell_specific.transcriptomics`, but
the model-specific `CustomExpression` and `main` workflow remain archived.
This is not a whole-workflow parity claim.

## Archived and no-replacement files

For every path in this section, all top-level functions, classes, aliases, and
CLI entry points are classified as archived/no replacement; none is an
installed package symbol. The rows preserve the historical ownership and
retirement decision; the source files were removed in the final manifest.

| Exact checkout path(s) | Symbol classification | Status | Evidence / consumers | Removal condition |
| --- | --- | --- | --- | --- |
| `build_model/test_biovelo_query.py` | all query/XML helpers and `main` | No replacement | online BioVelo diagnostic | online-workflow decision |
| `cell_type_specific_model/gimme_parallel.py` | all GIMME workers/orchestration and `main` | Archived | solver/pathos workflow | solver-owner decision |
| `cell_type_specific_model/ptr_one_round.py`, `ptr_multi_round.py` | all PTR transport/sink/dead-end/round definitions | Archived | historical solver workflow | solver-owner decision |
| `cell_type_specific_model/transcriptomics.py` | `biomass_fix`, `sgpr_rules`, `ensemble`, `index_to_ensembl`, `sgpr_to_ensembl`, `CustomExpression`, `main` | Archived except selected helpers above | full model-specific workflow | cell-specific owner decision |
| `functions/add_reaction.py` | `add_reaction_interactive`, `add_reaction_from_args` | Archived | interactive workflow | workflow-owner decision |
| `functions/class_generate_database.py` | `pathway`, `reaction`, `gpr`, `gene`, `compound` | No replacement | historical pickle object model | retire old pickles or approve adapter |
| `functions/function_bm_gdb.py` | all database harvesting/parsing/cache/reaction definitions | Archived | credentialed historical orchestrator | online/data-owner decision |
| `functions/functions_compare_models.py` | balance check and workbook writer helpers | Archived | historical Excel workflow | report/artifact decision |
| `functions/functions_create_figure.py` | `pie`, `pie2`, `pie5` | Archived | historical plotting helper | figure-recipe decision |
| `functions/pattern_generate_database.py` | all database pattern/generator definitions | Archived | historical generator | online/data-owner decision |
| `gapfill/phase1_connect_components.py` | `generate_phase1_outputs` | Archived | historical CSV/COBRA convention | gapfill migration decision |
| `gapfill/phase2_minimal_connector.py`, `phase2_prioritized_connector.py` | `UnionFind`, loaders/selectors, `run_phase2` | Archived | historical candidate selection | gapfill-owner decision |
| `gapfill/phase3_blocked_optimizer.py`, `phase3_component_milp.py`, `phase3_greedy_optimizer.py`, `phase3_milp_optimizer.py`, `phase3_sink_milp_original.py`, `phase3_tiered_milp.py` | all candidate, coverage, cache, solver, and phase-runner definitions | Archived | solver-heavy workflows | solver/model-owner decision |
| `implement_pathway/examples/run_example.py` | `main` | Archived | historical data/config example | replace inputs first |
| `implement_pathway/validate.py` | all `validate_*`, `print_usage`, `main` | Archived | full-model validation suite | MEMOTE/task ownership decision |
| `implement_pathway/visualize.py` | config, reaction-ID, renderer, usage, and `main` definitions | Archived | HTML/plotly/graphviz workflow | figure-recipe decision |
| `memote_and_task_analysis/metabolic_tasks/__init__.py`, `evaluation.py`, `task.py` | `TaskResult`, `MetabolicTask`, task helpers | Archived | optional MEMOTE/task workflow | owner and opt-in command |
| `memote_and_task_analysis/tests_extra/metabolic_tasks/__init__.py`, `evaluation.py`, `task.py`, `tests_extra/test_metabolic_tasks.py` | all task helpers/classes/tests | Archived | additional MEMOTE suite | migrate marked cases or archive command |
| `test_algorithms/gpr_prediction/functions_ast_gpr.py`, `functions_auth_gpr.py`, `gpr_prediction.py`, `test_gpr_prediction.py` | all helpers, CLI, and online tests | Archived | C8 and online fixture | migrate representative cases or archive command |
| `test_algorithms/mass_balance/equations_mass_balance.py`, `mass_balance.py` | `mass_balance`, `main` | Archived | C2 package characterization | fixture-owner decision |
| `test_algorithms/metabolite_identification/functions_metabolite_identification.py`, `metabolite_identification.py`, `test_metabolite_identification.py` | all helpers, CLI, and tests | Archived | C8 static PubChem characterization | fixture-owner decision |
| `test_algorithms/reac_identification/files/conftest.py`, `functions_reac_identification.py`, `reac_identification.py`, `test_reac_identification.py` | all fixtures, helpers, CLI, and tests | Archived | C8 deterministic SBML characterization | fixture-owner decision |

## Complete exact-file manifest

The grouped tables above expand to the following exact 82 checkout paths.
This list is intentionally plain text so an inventory test or review can
compare it directly with repository search results.

This historical inventory is not a parity result. Same-fixture differential
evidence is tracked separately in the [capability registry](protocol/capability-evidence.json)
and [parity contracts](parity/contracts/index.md).

```text
build_model/build_model.py
build_model/build_model_batch.py
build_model/print_biocyc_compartments.py
build_model/test_biovelo_query.py
cell_type_specific_model/gimme_parallel.py
cell_type_specific_model/match_exch_rxns.py
cell_type_specific_model/model_reduce.py
cell_type_specific_model/ptr_multi_round.py
cell_type_specific_model/ptr_one_round.py
cell_type_specific_model/transcriptomics.py
compare_models/compare_compartements.py
compare_models/compare_models.py
functions/__init__.py
functions/add_reaction.py
functions/analyze_annotations.py
functions/build_id_database.py
functions/class_generate_database.py
functions/config.py
functions/ensembl_client.py
functions/equations_bm_gdb.py
functions/function_annotate_cobra_model.py
functions/function_bm_gdb.py
functions/function_metabolite_identification.py
functions/function_reac_identification.py
functions/functions_compare_models.py
functions/functions_create_figure.py
functions/functions_mass_balance.py
functions/functions_merge_metabolic_networks.py
functions/functions_network_consistency.py
functions/gpr/__init__.py
functions/gpr/ast_gpr.py
functions/gpr/auth_gpr.py
functions/gpr/get_location_def.py
functions/gpr/gpr_def.py
functions/pathway_builder.py
functions/pattern_generate_database.py
gapfill/gapfill.py
gapfill/phase1_connect_components.py
gapfill/phase2_minimal_connector.py
gapfill/phase2_prioritized_connector.py
gapfill/phase3_blocked_optimizer.py
gapfill/phase3_component_milp.py
gapfill/phase3_greedy_optimizer.py
gapfill/phase3_milp_optimizer.py
gapfill/phase3_sink_milp_original.py
gapfill/phase3_tiered_milp.py
generate_data-base/generate_db.py
generate_data-base/make_model_from_pkl.py
generate_data-base/resume_db_gen.py
generate_figures/create_figure.py
implement_pathway/examples/run_example.py
implement_pathway/pathway_implementation.py
implement_pathway/validate.py
implement_pathway/visualize.py
memote_and_task_analysis/metabolic_tasks/__init__.py
memote_and_task_analysis/metabolic_tasks/evaluation.py
memote_and_task_analysis/metabolic_tasks/task.py
memote_and_task_analysis/tests_extra/metabolic_tasks/__init__.py
memote_and_task_analysis/tests_extra/metabolic_tasks/evaluation.py
memote_and_task_analysis/tests_extra/metabolic_tasks/task.py
memote_and_task_analysis/tests_extra/test_metabolic_tasks.py
merge_metabolic_netowrks_and_network_consistency/merge_metabolic_networks.py
metabolite_reac_identification/metabolite_reac_identification.py
metabolite_reac_identification/metabolite_reac_identification_with_retry.py
network_analysis/compaction.py
network_analysis/find_components.py
network_analysis/loop_removal.py
test_algorithms/gpr_prediction/functions_ast_gpr.py
test_algorithms/gpr_prediction/functions_auth_gpr.py
test_algorithms/gpr_prediction/gpr_prediction.py
test_algorithms/gpr_prediction/test_gpr_prediction.py
test_algorithms/mass_balance/equations_mass_balance.py
test_algorithms/mass_balance/mass_balance.py
test_algorithms/metabolite_identification/functions_metabolite_identification.py
test_algorithms/metabolite_identification/metabolite_identification.py
test_algorithms/metabolite_identification/test_metabolite_identification.py
test_algorithms/reac_identification/files/conftest.py
test_algorithms/reac_identification/functions_reac_identification.py
test_algorithms/reac_identification/reac_identification.py
test_algorithms/reac_identification/test_reac_identification.py
tools/list_pathway_reactions.py
utils/json_to_sbml.py
```

## Final removal manifest

The historical rows above describe the pre-removal compatibility decisions.
This manifest is authoritative after the closeout: every listed source file
was removed from its checkout directory, and maintained behavior is owned by
`src/thg_protocol` or `tests/`.

```text
build_model/build_model.py | Removed | Batch 2
build_model/build_model_batch.py | Removed | Batch 2
build_model/print_biocyc_compartments.py | Removed | Batch 1
build_model/test_biovelo_query.py | Removed | Batch 3
cell_type_specific_model/gimme_parallel.py | Removed | Batch 3
cell_type_specific_model/match_exch_rxns.py | Removed | Batch 1
cell_type_specific_model/model_reduce.py | Removed | Batch 2
cell_type_specific_model/ptr_multi_round.py | Removed | Batch 3
cell_type_specific_model/ptr_one_round.py | Removed | Batch 3
cell_type_specific_model/transcriptomics.py | Removed | Batch 3
compare_models/compare_compartements.py | Removed | Batch 2
compare_models/compare_models.py | Removed | Batch 2
functions/__init__.py | Removed | Batch 1
functions/add_reaction.py | Removed | Batch 3
functions/analyze_annotations.py | Removed | Batch 1
functions/build_id_database.py | Removed | Batch 2
functions/class_generate_database.py | Removed | Batch 3
functions/config.py | Removed | Batch 1
functions/ensembl_client.py | Removed | Batch 2
functions/equations_bm_gdb.py | Removed | Batch 2
functions/function_annotate_cobra_model.py | Removed | Batch 2
functions/function_bm_gdb.py | Removed | Batch 3
functions/function_metabolite_identification.py | Removed | Batch 2
functions/function_reac_identification.py | Removed | Batch 1
functions/functions_compare_models.py | Removed | Batch 3
functions/functions_create_figure.py | Removed | Batch 3
functions/functions_mass_balance.py | Removed | Batch 2
functions/functions_merge_metabolic_networks.py | Removed | Batch 2
functions/functions_network_consistency.py | Removed | Batch 2
functions/gpr/__init__.py | Removed | Batch 1
functions/gpr/ast_gpr.py | Removed | Batch 1
functions/gpr/auth_gpr.py | Removed | Batch 2
functions/gpr/get_location_def.py | Removed | Batch 2
functions/gpr/gpr_def.py | Removed | Batch 2
functions/pathway_builder.py | Removed | Batch 1
functions/pattern_generate_database.py | Removed | Batch 3
gapfill/gapfill.py | Removed | Batch 2
gapfill/phase1_connect_components.py | Removed | Batch 3
gapfill/phase2_minimal_connector.py | Removed | Batch 3
gapfill/phase2_prioritized_connector.py | Removed | Batch 3
gapfill/phase3_blocked_optimizer.py | Removed | Batch 3
gapfill/phase3_component_milp.py | Removed | Batch 3
gapfill/phase3_greedy_optimizer.py | Removed | Batch 3
gapfill/phase3_milp_optimizer.py | Removed | Batch 3
gapfill/phase3_sink_milp_original.py | Removed | Batch 3
gapfill/phase3_tiered_milp.py | Removed | Batch 3
generate_data-base/generate_db.py | Removed | Batch 2
generate_data-base/make_model_from_pkl.py | Removed | Batch 2
generate_data-base/resume_db_gen.py | Removed | Batch 2
generate_figures/create_figure.py | Removed | Batch 2
implement_pathway/examples/run_example.py | Removed | Batch 3
implement_pathway/pathway_implementation.py | Removed | Batch 2
implement_pathway/validate.py | Removed | Batch 3
implement_pathway/visualize.py | Removed | Batch 3
memote_and_task_analysis/metabolic_tasks/__init__.py | Removed | Batch 3
memote_and_task_analysis/metabolic_tasks/evaluation.py | Removed | Batch 3
memote_and_task_analysis/metabolic_tasks/task.py | Removed | Batch 3
memote_and_task_analysis/tests_extra/metabolic_tasks/__init__.py | Removed | Batch 4
memote_and_task_analysis/tests_extra/metabolic_tasks/evaluation.py | Removed | Batch 4
memote_and_task_analysis/tests_extra/metabolic_tasks/task.py | Removed | Batch 4
memote_and_task_analysis/tests_extra/test_metabolic_tasks.py | Removed | Batch 4
merge_metabolic_netowrks_and_network_consistency/merge_metabolic_networks.py | Removed | Batch 2
metabolite_reac_identification/metabolite_reac_identification.py | Removed | Batch 2
metabolite_reac_identification/metabolite_reac_identification_with_retry.py | Removed | Batch 2
network_analysis/compaction.py | Removed | Batch 1
network_analysis/find_components.py | Removed | Batch 2
network_analysis/loop_removal.py | Removed | Batch 3
test_algorithms/gpr_prediction/functions_ast_gpr.py | Removed | Batch 4
test_algorithms/gpr_prediction/functions_auth_gpr.py | Removed | Batch 4
test_algorithms/gpr_prediction/gpr_prediction.py | Removed | Batch 4
test_algorithms/gpr_prediction/test_gpr_prediction.py | Removed | Batch 4
test_algorithms/mass_balance/equations_mass_balance.py | Removed | Batch 4
test_algorithms/mass_balance/mass_balance.py | Removed | Batch 4
test_algorithms/metabolite_identification/functions_metabolite_identification.py | Removed | Batch 4
test_algorithms/metabolite_identification/metabolite_identification.py | Removed | Batch 4
test_algorithms/metabolite_identification/test_metabolite_identification.py | Removed | Batch 4
test_algorithms/reac_identification/files/conftest.py | Removed | Batch 4
test_algorithms/reac_identification/functions_reac_identification.py | Removed | Batch 4
test_algorithms/reac_identification/reac_identification.py | Removed | Batch 4
test_algorithms/reac_identification/test_reac_identification.py | Removed | Batch 4
tools/list_pathway_reactions.py | Removed | Batch 1
utils/json_to_sbml.py | Removed | Batch 1
```

## Caller policy and removal checklist

Intentional adapter imports are isolated in explicitly named compatibility
tests, including `tests/unit/test_legacy_compatibility_exports.py`, and legacy
characterization integrations. The executable maintained-code policy is
`tests/unit/test_legacy_import_policy.py`; package code may not add imports
from legacy namespaces.

Before deleting an adapter, search imports, direct execution, docs, and CI;
run evidence tests plus the offline suite; update this inventory,
`docs/api-contracts.md`, and `docs/legacy-workflows.md`; confirm no model,
dataset, report, fixture, or LFS object is in the deletion group; then run
Ruff, wheel/outside-checkout checks, and installed CLI help checks.

## Exact top-level symbol enumeration

The following generated-style appendix records every public top-level function
and class found in each inventoried Python file. A file with no public
top-level definition is still classified by its import aliases and status
above.

```text
+build_model/build_model.py: build_parser, main
build_model/build_model_batch.py: build_parser, main
build_model/print_biocyc_compartments.py: build_parser, main
build_model/test_biovelo_query.py: build_protein_query, build_protein_getxml_url, run_query, extract_strings_from_xml, extract_genes_from_xml, find_cco_resources, extract_locations_from_xml, get_compartment_name, extract_proteins_from_xml, fetch_resource_and_extract, main
cell_type_specific_model/gimme_parallel.py: gimme_batch_worker, build_expression_dict_from_original, get_extended_scores, split_reversible_exchanges, update_irreversible_exchanges, recombine_solution, gimme_worker, gimme_parallel, main
cell_type_specific_model/match_exch_rxns.py: match_exch_rxns
cell_type_specific_model/model_reduce.py: model_reduce, build_parser, main
cell_type_specific_model/ptr_multi_round.py: ident_final_dead_end_metabolites, modify_reaction_bounds, search_metabolite_locations, identify_connected_species, product_transport_metabolite_to, substrate_transport_metabolite_to, wrapped_gapfill, jaccard, add_transport_and_sink_reactions, add_transport_and_sink_reactions_futile_cycles, process_reaction, identify_transport_reaction_to_dead_end_metabolite, test_stoichiometric_consistency, putative_tr
cell_type_specific_model/ptr_one_round.py: ident_final_dead_end_metabolites, modify_reaction_bounds, search_metabolite_locations, identify_connected_species, product_transport_metabolite_to, substrate_transport_metabolite_to, wrapped_gapfill, jaccard, add_transport_and_sink_reactions, add_transport_and_sink_reactions_futile_cycles, process_reaction, identify_transport_reaction_to_dead_end_metabolite, test_stoichiometric_consistency, putative_tr
cell_type_specific_model/transcriptomics.py: biomass_fix, sgpr_rules, ensemble, index_to_ensembl, extract_pairs, sgpr_to_ensembl, CustomExpression, preprocess_rule, process_expression_data, main
compare_models/compare_compartements.py: normalize_stoichiometry, comp_compare, print_comparison, save_csv, build_parser, main
compare_models/compare_models.py: build_parser, main
functions/__init__.py: (no public top-level definitions)
functions/add_reaction.py: add_reaction_interactive, add_reaction_from_args
functions/analyze_annotations.py: build_parser, main
functions/build_id_database.py: build_database_from_annotations, save_database, build_database_from_model, build_parser, main
functions/class_generate_database.py: pathway, reaction, gpr, gene, compound
functions/config.py: (no public top-level definitions)
functions/ensembl_client.py: fetch_ensembl_annotations
functions/equations_bm_gdb.py: (no public top-level definitions)
functions/function_annotate_cobra_model.py: annotate_cobra_model
functions/function_bm_gdb.py: parse_kegg_flat_file_to_html, batch_fetch_kegg_entries, compartment_file_to_dict_bm, create_comp_abbreviations_dict_bm, update_comp_names_bm, create_compartments_dict_bm, compartment_file_to_dict, recondict, DefEnsblDB, getGPR22, getGPR_old, getHtml, getHtmlS, multiple_replace, ParseNestedParen, getLinkPath, getReacParam, getRxncons, meltGene, meltGeneList, getLocation_old, create_dict, getFormula, parse_kegg_flat_file, getCompParamFromRestAPI, getCompParam
functions/function_metabolite_identification.py: generate_met_annotation, process_annotation
functions/function_reac_identification.py: (no public top-level definitions)
functions/functions_compare_models.py: test_reaction_balance, umbalance_test, defmodel, defgroup, compartment, metabolite, metabolite_2, reaction, gene, metabolite2, metabolite2_2
functions/functions_create_figure.py: pie, pie2, pie5
functions/functions_mass_balance.py: Glycan, Reformulation, AddMissingAtom, CountAtom, RxnBalance2, RxnParam2Eq, WrapRxnSubsProdParam, UnwrapRxnSubsProdParam, Proton, Water, add_extra_compound
functions/functions_merge_metabolic_networks.py: delete_isolated_metabolites, delete_not_used_reactions, delete_not_used_genes, network_metabolites_merge, network_genes_merge, network_genes_merge_2
functions/functions_network_consistency.py: test_reaction_balance, imbalance_test, test_stoichiometric_consistency, test_unconserved_metabolites, test_find_orphans, test_find_deadends, test_inconsistent_min_stoichiometry, test_detect_energy_generating_cycles, test_reaction_charge_balance, test_reaction_mass_balance, test_blocked_reactions, test_find_stoichiometrically_balanced_cycles, test_find_disconnected, test_find_metabolites_not_produced_with_open_bounds, test_find_metabolites_not_consumed_with_open_bounds, test_find_reactions_unbounded_flux_default_condition
functions/gpr/__init__.py: (no public top-level definitions)
functions/gpr/ast_gpr.py: (no public top-level definitions)
functions/gpr/auth_gpr.py: read_env_biocyc, setup_biocyc_session, get_ecnumber_biocyc_html, get_html, getGPR, pattern_match_org, match_biocyc_page
functions/gpr/get_location_def.py: get_html, create_dict, multiple_replace_new, getLocationnew
functions/gpr/gpr_def.py: get_html, getGPR, pattern_match_org, match_biocyc_page
functions/pathway_builder.py: (no public top-level definitions)
functions/pattern_generate_database.py: mar_number, create_dict, create_dict2, mam_number, Head, DefCompart, DefComp, DefDefRxn, listOfParameters, DefRxn, objective, DefMod, DefGrp, rxnSubcel, DefHead
gapfill/gapfill.py: build_parser, main
gapfill/phase1_connect_components.py: generate_phase1_outputs
gapfill/phase2_minimal_connector.py: UnionFind, load_candidates, representative, run_phase2
gapfill/phase2_prioritized_connector.py: UnionFind, load_candidates, group_by_component_pair, pick_representative, run_phase2
gapfill/phase3_blocked_optimizer.py: load_candidates, add_transport, run_phase3
gapfill/phase3_component_milp.py: load_candidates, load_components_summary, build_metabolite_to_component_map, get_reactions_in_component, get_candidates_for_component, find_blocked_reactions_in_set, add_transport, test_candidate_unblocks, compute_coverage_for_component, solve_component_milp, run_phase3_component_wise
gapfill/phase3_greedy_optimizer.py: load_candidates, compute_deadend_sets, benefit_of_candidate, add_transport_to_model, run_phase3
gapfill/phase3_milp_optimizer.py: load_candidates, add_transport, find_blocked_reactions, find_blocked_reactions_fast, test_candidate_coverage, compute_coverage_matrix, solve_coverage_milp, run_phase3
gapfill/phase3_sink_milp_original.py: set_lp_solver, compute_model_hash, get_coverage_cache_path, load_coverage_from_cache, save_coverage_to_cache, add_transport, load_candidates, load_components_summary, build_original_component_map, get_deadend_info, find_blocked_reactions_in_set, add_temp_sink_source, test_candidate_with_temp_sinks, test_candidate_batch, test_candidate_batch_parallel, prepare_model_with_temp_sinks, build_component_graph, get_reachable_reactions, precompute_candidate_reachability, compute_coverage_with_temp_sinks, solve_greedy, solve_milp, get_candidates_for_original_component, run_test_on_original_component, process_small_component, run_phase3_all_components
gapfill/phase3_tiered_milp.py: load_candidates, load_components_summary, build_metabolite_to_component_map, get_reactions_in_component, filter_candidates_by_type, get_candidates_for_component, find_blocked_reactions_in_set, add_transport, test_candidate_unblocks, compute_coverage_for_component, solve_milp, process_tier_for_component, run_phase3_tiered
generate_data-base/generate_db.py: build_parser, main
generate_data-base/make_model_from_pkl.py: build_parser, main
generate_data-base/resume_db_gen.py: build_parser, main
generate_figures/create_figure.py: build_parser, main
implement_pathway/examples/run_example.py: main
implement_pathway/pathway_implementation.py: build_parser, main
implement_pathway/validate.py: build_compartment_mapping, validate_quick, validate_unit_tests, validate_reproducibility, validate_integration, validate_mass_balance, validate_network_topology, validate_database_consistency, validate_synthesis_balance, validate_demand_reactions, print_usage, main
implement_pathway/visualize.py: load_pathway_config, get_pathway_reaction_ids, visualize_d3js, visualize_plotly, visualize_graphviz, print_usage, main
memote_and_task_analysis/metabolic_tasks/__init__.py: (no public top-level definitions)
memote_and_task_analysis/metabolic_tasks/evaluation.py: gather_mets_from_reaction_str, read_metabolic_task, apply_metabolic_task, iterate_over_tasks
memote_and_task_analysis/metabolic_tasks/task.py: TaskResult, MetabolicTask
memote_and_task_analysis/tests_extra/metabolic_tasks/__init__.py: (no public top-level definitions)
memote_and_task_analysis/tests_extra/metabolic_tasks/evaluation.py: gather_mets_from_reaction_str, read_metabolic_task, apply_metabolic_task, iterate_over_tasks
memote_and_task_analysis/tests_extra/metabolic_tasks/task.py: TaskResult, MetabolicTask
memote_and_task_analysis/tests_extra/test_metabolic_tasks.py: test_essential_metabolic_tasks
merge_metabolic_netowrks_and_network_consistency/merge_metabolic_networks.py: build_parser, main
metabolite_reac_identification/metabolite_reac_identification.py: build_parser, main
metabolite_reac_identification/metabolite_reac_identification_with_retry.py: build_parser, main
network_analysis/compaction.py: (no public top-level definitions)
network_analysis/find_components.py: find_network_components
network_analysis/loop_removal.py: remove_loops, main
test_algorithms/gpr_prediction/functions_ast_gpr.py: (no public top-level definitions)
test_algorithms/gpr_prediction/functions_auth_gpr.py: read_env_biocyc, setup_biocyc_session, get_ecnumber_biocyc_html, get_html, pattern_match_org, match_biocyc_page, getGPR, fetch_kegg_rest, parseGPR, multiple_replace, ParseNestedParen
test_algorithms/gpr_prediction/gpr_prediction.py: summarize_results, main
test_algorithms/gpr_prediction/test_gpr_prediction.py: test_gprs_ec1, test_gprs_ec2, test_gprs_ec3, test_gprs_ec4, test_gprs_ec5, test_gprs_ec6, test_gprs_ec8, test_gprs_ec9
test_algorithms/mass_balance/equations_mass_balance.py: mass_balance
test_algorithms/mass_balance/mass_balance.py: main
test_algorithms/metabolite_identification/functions_metabolite_identification.py: (no public top-level definitions)
test_algorithms/metabolite_identification/metabolite_identification.py: process_met_file, write_report, main
test_algorithms/metabolite_identification/test_metabolite_identification.py: test_all_metabolites_can_be_identified
test_algorithms/reac_identification/files/conftest.py: human_path, lipids_path, ground_truth_reacs_small, processed_jaccard, human_model
test_algorithms/reac_identification/functions_reac_identification.py: (no public top-level definitions)
test_algorithms/reac_identification/reac_identification.py: write_report, main
test_algorithms/reac_identification/test_reac_identification.py: test_all_reactions_return_right_ecnumber, test_reaction_jaccard_works, test_reactions_are_the_same
tools/list_pathway_reactions.py: main
utils/json_to_sbml.py: main
```
