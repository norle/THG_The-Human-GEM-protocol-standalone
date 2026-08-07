# Analysis APIs

Analysis functions accept caller-owned models and return reports, mappings, or
copies. Solver-backed checks are optional and are not required by the default
documentation test suite.

## Recommended entry points

Use [`find_network_components`][thg_protocol.analysis.network.find_network_components]
for connectivity, [`compare_models_from_files`][thg_protocol.analysis.compare.compare_models_from_files]
for file comparisons, and [`full_compaction`][thg_protocol.analysis.compaction.full_compaction]
for duplicate-reaction cleanup.

Use [`model_signature`][thg_protocol.analysis.model_signature.model_signature]
and [`diff_model_signatures`][thg_protocol.analysis.model_signature.diff_model_signatures]
for semantic model parity and artifact comparisons.

## Semantic model signatures

::: thg_protocol.analysis.model_signature
    options:
      members:
        - model_signature
        - diff_model_signatures

## Consistency

::: thg_protocol.analysis.consistency
    options:
      members:
        - dead_end_metabolites
        - orphan_metabolites
        - reaction_balance
        - charge_balance
        - unbalanced_reactions_by_charge
        - blocked_reactions
        - stoichiometrically_balanced_cycles
        - metabolites_not_produced
        - metabolites_not_consumed
        - unbounded_reactions
        - unbalanced_reactions

## Comparison

::: thg_protocol.analysis.compare
    options:
      members:
        - compare_models
        - compare_models_from_files
        - compare_reactions
        - reactions_by_compartment
        - remove_blocked_reactions
        - save_comparison_csv
        - compare_semantic_models
        - compare_model_files_semantically
        - compare_workflow_runs
        - save_semantic_comparison

## Compaction

::: thg_protocol.analysis.compaction
    options:
      members:
        - are_reactions_proportional
        - combine_identical_reactions
        - full_compaction

## Network analysis

::: thg_protocol.analysis.network
    options:
      members:
        - find_network_components
        - write_component_report
