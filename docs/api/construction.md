# Database and model construction

Construction APIs create models from normalized records, JSON bundles,
historical pickle bundles, or explicit reference-model inputs. Pickle support
is compatibility support and requires the `database` extra when a checkpoint
needs `dill`.

## Recommended entry points

Use [`reconstruct_model`][thg_protocol.database.reconstruct_model] for records,
[`reconstruct_model_from_json`][thg_protocol.database.reconstruct_model_from_json]
for saved bundles, and [`build_model`][thg_protocol.model_build.build_model] to
enrich an existing model.

## Database reconstruction

::: thg_protocol.database
    options:
      members:
        - BiocycCompartmentSummary
        - GeneRecord
        - MetaboliteRecord
        - ReactionRecord
        - reconstruct_model
        - reconstruct_model_from_json
        - reconstruct_model_from_pickle
        - reconstruct_model_with_services
        - summarize_biocyc_compartments

## Database parsing

::: thg_protocol.database_parsing
    options:
      members:
        - parse_kegg_compound_entry
        - parse_kegg_compound_entry_fields
        - parse_pathway_links

## Model build

::: thg_protocol.model_build
    options:
      members:
        - ModelBuildReport
        - build_model

::: thg_protocol.model_build.batch
    options:
      members:
        - build_model_batch

## Formula and mass balance

::: thg_protocol.model_build.mass_balance
    options:
      members:
        - atom10
        - formula_atoms
        - gcd
        - missing_atoms
        - reaction_compare
        - reformulate_glycan_equation
        - inarray
        - equation_matrix
        - balance_equation
        - count_atoms
        - balance_reaction
        - eq2mat
        - nullity
        - inv
        - maximum_gcd
        - maximumGCD
