import importlib

from thg_protocol.figures import (
    AnnotationGroupSummary,
    annotation_group_percentages,
    summarize_annotation_rows,
)


def test_figures_package_import_is_safe_without_plotting_dependencies():
    figures = importlib.import_module("thg_protocol.figures.comparison")

    assert callable(figures.generate_annotation_comparison_figures)


def test_annotation_group_percentages_preserve_legacy_cumulative_groups():
    assert annotation_group_percentages([1.0, 2.0, 3.0, 4.0]) == AnnotationGroupSummary(
        added=75.0, replaced=50.0, unchanged=25.0
    )
    assert annotation_group_percentages([]) == AnnotationGroupSummary(0.0, 0.0, 0.0)


def test_summarize_annotation_rows_handles_missing_values_as_unmatched():
    rows = [{"a": 1.0, "b": 2.0}, {"a": 3.0}, {"a": 4.0, "b": 1.0}]

    result = summarize_annotation_rows(rows, ("a", "b"))

    assert result["a"] == AnnotationGroupSummary(
        added=2 / 3 * 100, replaced=1 / 3 * 100, unchanged=1 / 3 * 100
    )
    assert result["b"] == AnnotationGroupSummary(
        added=2 / 3 * 100, replaced=2 / 3 * 100, unchanged=1 / 3 * 100
    )
