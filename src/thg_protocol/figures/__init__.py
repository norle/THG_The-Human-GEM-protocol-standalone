"""Figure-generation APIs for report-driven THG comparisons."""

from .comparison import (
    AnnotationGroupSummary,
    FigureGenerationResult,
    annotation_group_percentages,
    generate_annotation_comparison_figures,
    read_annotation_group_summary,
    summarize_annotation_rows,
)
from .models import (
    ModelComponentSummary,
    ModelFigureGenerationResult,
    NamedModel,
    generate_model_comparison_figures,
    model_component_summary,
    new_reaction_annotation_group_sizes,
    summarize_model_components,
    unannotated_metabolite_percentage,
)

__all__ = [
    "AnnotationGroupSummary",
    "ModelComponentSummary",
    "ModelFigureGenerationResult",
    "NamedModel",
    "FigureGenerationResult",
    "annotation_group_percentages",
    "generate_annotation_comparison_figures",
    "generate_model_comparison_figures",
    "model_component_summary",
    "new_reaction_annotation_group_sizes",
    "read_annotation_group_summary",
    "summarize_model_components",
    "summarize_annotation_rows",
    "unannotated_metabolite_percentage",
]
