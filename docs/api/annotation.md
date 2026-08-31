# Annotation and GPR

Annotation functions operate on explicit model data and may use injected
service clients. Network access, credentials, rate limits, and response
caching are caller-visible concerns; static clients are preferred in tests.

## Recommended entry points

Start with [`analyze_model_annotations`][thg_protocol.annotation.model_annotations.analyze_model_annotations],
[`extract_metabolite_annotations`][thg_protocol.annotation.model_annotations.extract_metabolite_annotations],
and [`get_gpr`][thg_protocol.gpr.lookup.get_gpr].

## Annotation package

::: thg_protocol.annotation.metabolites
    options:
      members:
        - atom
        - formula_similarity
        - gather_metabolites
        - generate_met_annotation
        - global_met_annotation_file
        - identify_metabolite
        - process_annotation
        - remove_null_value

::: thg_protocol.annotation.reactions
    options:
      members:
        - execute_jaccard
        - gather_kegg_metabolites
        - identify_reaction
        - jaccard
        - process_jaccard
        - process_reac
        - replace_met_id_by_met_kegg

::: thg_protocol.annotation.metabolite_reactions
    options:
      members:
        - MetaboliteReactionResult
        - MetaboliteRetryResult
        - retry_metabolite_annotations
        - run_metabolite_reaction_identification

::: thg_protocol.annotation.model
    options:
      members:
        - annotate_cobra_model

::: thg_protocol.annotation.model_annotations
    options:
      members:
        - analyze_model_annotations
        - extract_metabolite_annotations

## GPR parsing and lookup

::: thg_protocol.gpr.ast_gpr
    options:
      members:
        - compare_ast
        - deduplicate_gpr
        - divide_gpr_in_ors
        - reduce_gpr
        - sanitize_gpr

::: thg_protocol.gpr.lookup
    options:
      members:
        - get_gpr
        - parse_gene_pairs

::: thg_protocol.gpr.location
    options:
      members:
        - resolve_locations
