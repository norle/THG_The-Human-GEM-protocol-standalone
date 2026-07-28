"""Figure-generation APIs for report-driven THG comparisons."""

from .comparison import (
    AnnotationGroupSummary,
    FigureGenerationResult,
    annotation_group_percentages,
    generate_annotation_comparison_figures,
    read_annotation_group_summary,
    summarize_annotation_rows,
)

__all__ = [
    "AnnotationGroupSummary",
    "FigureGenerationResult",
    "annotation_group_percentages",
    "generate_annotation_comparison_figures",
    "read_annotation_group_summary",
    "summarize_annotation_rows",
]
