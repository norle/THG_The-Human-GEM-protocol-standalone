# Figure and report APIs

Summary functions are dependency-light. Rendering functions require the
optional `figures` extra and write only to explicit output paths.

## Recommended entry points

Start with [`summarize_model_components`][thg_protocol.figures.models.summarize_model_components]
for dependency-light summaries and add
[`generate_model_comparison_figures`][thg_protocol.figures.models.generate_model_comparison_figures]
when SVG output is required.

## Model figures

::: thg_protocol.figures.models
    options:
      members:
        - NamedModel
        - ModelComponentSummary
        - ModelFigureGenerationResult
        - generate_model_comparison_figures
        - model_component_summary
        - new_reaction_annotation_group_sizes
        - summarize_model_components
        - unannotated_metabolite_percentage

## Comparison figures

::: thg_protocol.figures.comparison
    options:
      members:
        - AnnotationGroupSummary
        - FigureGenerationResult
        - annotation_group_percentages
        - generate_annotation_comparison_figures
        - read_annotation_group_summary
        - summarize_annotation_rows
