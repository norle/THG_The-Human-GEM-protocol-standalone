# Workflow APIs

Workflow functions describe their mutation and file ownership in generated
docstrings. CLI modules expose `build_parser` and `main`; installed entry
points are documented on the [CLI page](cli.md).

## Recommended entry points

Use [`run_pipeline`][thg_protocol.gapfill.core.run_pipeline],
[`implement_pathway_files`][thg_protocol.pathway.workflow.implement_pathway_files],
[`merge_models`][thg_protocol.merge.merge_models], or
[`reduce_model_by_activity`][thg_protocol.cell_specific.reduce_model_by_activity]
for complete user-facing workflows.

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
        - MergeReport
        - merge_models
        - merge_models_from_paths

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
