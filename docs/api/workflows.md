# Workflow APIs

Workflow functions describe their mutation and file ownership in generated
docstrings. CLI modules expose `build_parser` and `main`; installed entry
points are documented on the [CLI page](cli.md).

## Recommended entry points

Use [`run_pipeline`][thg_protocol.gapfill.core.run_pipeline],
[`implement_pathway_files`][thg_protocol.pathway.workflow.implement_pathway_files],
[`merge_models`][thg_protocol.merge.merge_models], or
[`reduce_model_by_activity`][thg_protocol.cell_specific.reduce_model_by_activity]
for complete user-facing operations. Use [`start`][thg_protocol.workflow.runner.start]
and [`resume`][thg_protocol.workflow.runner.resume] for the documented
restartable engineering DAG.

## β1 curation

::: thg_protocol.curation.beta1
    options:
      members:
        - BalanceAudit
        - GPRExpression
        - InventoryReport
        - MetaboliteCandidate
        - ReactionIdentity
        - apply_model_proposals
        - audit_model
        - audit_reaction
        - beta1_release_gate
        - canonicalize_gpr
        - classify_reaction
        - compare_reaction_identity
        - consolidate_model
        - duplicate_reaction_groups
        - formula_class
        - generate_balance_proposals
        - generate_curation_proposals
        - inventory_model
        - normalize_gene_mapping
        - normalize_namespace
        - normalized_stoichiometry
        - parse_gpr
        - release_beta1
        - resolve_metabolite_identity
        - rewrite_gpr
        - reaction_identity_key
        - score_metabolite_candidate
        - serialize_s_gpr
        - protonation_relation
        - run_beta1
        - serialize_gpr
        - with_subunit_stoichiometry

## β2 compartment expansion

::: thg_protocol.curation.beta2
    options:
      members:
        - LocationResolution
        - apply_expansion_plan
        - beta2_release_gate
        - generate_expansion_plan
        - normalize_compartment_registry
        - normalize_location
        - reaction_policy
        - release_beta2
        - resolve_gpr_locations
        - validate_beta2

## Resumable workflow

::: thg_protocol.workflow.config
    options:
      members:
        - ConfigError
        - RunSettings
        - ReferenceSettings
        - DatabaseSettings
        - MergeSettings
        - ValidationSettings
        - RunConfig
        - load_start_config
        - config_to_dict
        - write_snapshot
        - load_snapshot

::: thg_protocol.workflow.hashing
    options:
      members:
        - sha256_file
        - sha256_json
        - artifact_record
        - verify_artifact

::: thg_protocol.workflow.manifest
    options:
      members:
        - ManifestError
        - utc_now
        - new_manifest
        - validate_manifest
        - load_manifest
        - write_manifest_atomic

::: thg_protocol.workflow.runner
    options:
      members:
        - WorkflowError
        - StageFailedError
        - start
        - resume
        - get_status

::: thg_protocol.workflow.stages
    options:
      members:
        - StageContext
        - StageResult
        - Stage
        - ReferenceStage
        - DatabaseStage
        - MergeStage
        - ValidationStage
        - MemoteStage
        - validate_stage_order

::: thg_protocol.workflow.lock
    options:
      members:
        - RunLockedError
        - acquire_run_lock
        - unlock_run

## Gapfill

::: thg_protocol.gapfill.core
    options:
      members:
        - generate_candidates
        - run_phase1
        - run_phase2
        - run_phase3
        - run_pipeline

## Pathway

::: thg_protocol.pathway.core
    options:
      members:
        - add_compartment
        - build_reaction_from_config
        - check_pathway_exists
        - create_compartment_metabolites
        - create_compartment_reactions
        - create_metabolite_in_new_compartment
        - find_metabolite_by_annotation
        - find_metabolite_by_formula_in_model
        - find_metabolite_robust
        - get_metabolite_id_base
        - get_next_metabolite_id
        - get_next_reaction_id
        - parse_reaction_equation
        - parse_universal_reaction
        - select_pathway_metabolites
        - substitute_compartment_abbreviations

::: thg_protocol.pathway.workflow
    options:
      members:
        - implement_pathway
        - implement_pathway_files

::: thg_protocol.pathway.kegg_listing
    options:
      members:
        - list_pathway_reactions

## Merge

::: thg_protocol.merge
    options:
      members:
        - MergeDecision
        - MergePlan
        - MergePolicy
        - MergeReport
        - RepairReport
        - apply_merge_plan
        - bounded_repair
        - generate_merge_plan
        - merge_models
        - merge_models_from_paths
        - validate_merged_model

## Cell-specific models

::: thg_protocol.cell_specific
    options:
      members:
        - ActivityReductionReport
        - reduce_model_by_activity

::: thg_protocol.cell_specific.exchange
    options:
      members:
        - match_exchange_reactions

::: thg_protocol.cell_specific.transcriptomics
    options:
      members:
        - extract_ensembl_ids
        - extract_gene_annotation_pairs
        - extract_sgpr_rules
        - replace_gene_symbols
        - replace_index_tokens
