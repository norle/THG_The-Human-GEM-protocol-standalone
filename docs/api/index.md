# API reference

The reference is generated from the maintained package with
`mkdocstrings[python]`. Public functions and classes are the supported Python
surface; names beginning with `_` are intentionally filtered from the site.

Common contracts:

- Functions accept explicit model, input, output, cache, and report paths.
- Network-capable operations accept injectable clients. Static clients are the
  offline test and documentation boundary.
- Analysis functions generally do not mutate models. The generated signatures
  and docstrings call out exceptions and ownership for transformation APIs.
- Solver, MEMOTE, plotting, and historical pickle support are optional extras.

See the [workflow guides](../usage.md) for end-to-end context and the
[architecture page](../architecture.md) for data flow and service ownership.

## Coverage matrix

| Area | Generated page | Main modules |
| --- | --- | --- |
| Core and I/O | [Core and I/O](core.md) | `config`, `glycan`, `reaction_config`, `io` |
| Construction | [Construction](construction.md) | `database`, `database_parsing`, `model_build` |
| Annotation and GPR | [Annotation](annotation.md) | `annotation`, `gpr` |
| Services | [Services](services.md) | BioCyc, KEGG, Ensembl, PubChem, Location |
| Workflows | [Workflows](workflows.md) | gapfill, pathway, merge, cell-specific, resumable run |
| Analysis | [Analysis](analysis.md) | consistency, comparison, compaction, network |
| Figures | [Figures](figures.md) | comparison and model reports |
| Commands | [CLI commands](cli.md) | `thg-gapfill`, `thg-pathway`, `thg-compare`, `thg-run` |

## Recommended entry points

- Construction: [`reconstruct_model`][thg_protocol.database.reconstruct_model],
  [`reconstruct_model_from_json`][thg_protocol.database.reconstruct_model_from_json],
  and [`reconstruct_model_with_services`][thg_protocol.database.reconstruct_model_with_services].
- Annotation: [`analyze_model_annotations`][thg_protocol.annotation.model_annotations.analyze_model_annotations]
  and [`get_gpr`][thg_protocol.gpr.lookup.get_gpr].
- Model changes: [`implement_pathway_files`][thg_protocol.pathway.workflow.implement_pathway_files],
  [`gapfill_model`][thg_protocol.gapfill.core.gapfill_model], and
  [`merge_models`][thg_protocol.merge.merge_models].
- Analysis: [`find_network_components`][thg_protocol.analysis.network.find_network_components],
  [`compare_models_from_files`][thg_protocol.analysis.compare.compare_models_from_files],
  and [`full_compaction`][thg_protocol.analysis.compaction.full_compaction].

The checked-in [canonical API inventory](api-inventory.json) is the source of
truth for generated members. Re-exported package facades remain supported
import paths, but each symbol is rendered once at its defining module.
