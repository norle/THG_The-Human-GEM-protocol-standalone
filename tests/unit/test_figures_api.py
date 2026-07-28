import importlib

import pytest

from thg_protocol.figures import (
    AnnotationGroupSummary,
    NamedModel,
    annotation_group_percentages,
    generate_model_comparison_figures,
    new_reaction_annotation_group_sizes,
    summarize_annotation_rows,
    summarize_model_components,
    unannotated_metabolite_percentage,
)


class FakeMetabolite:
    def __init__(self, annotation):
        self.annotation = annotation


class FakeReaction:
    def __init__(self, identifier, *, gene_rule="", annotation=None):
        self.id = identifier
        self.gene_reaction_rule = gene_rule
        self.annotation = annotation or {}


class FakeModel:
    def __init__(self, metabolites, reactions, genes):
        self.metabolites = metabolites
        self.reactions = reactions
        self.genes = genes


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


def test_model_summaries_preserve_legacy_component_statistics():
    reference = FakeModel(
        [FakeMetabolite({"bigg.metabolite": "a", "sbo": "b", "vmhmetabolite": "c"})],
        [FakeReaction("R1", gene_rule="g1")],
        ["g1"],
    )
    comparison = FakeModel(
        [
            FakeMetabolite({"bigg.metabolite": "a", "sbo": "b", "vmhmetabolite": "c"}),
            FakeMetabolite({"bigg.metabolite": "a", "kegg.compound": "C00001"}),
        ],
        [
            FakeReaction("R1"),
            FakeReaction("R2", gene_rule="g2", annotation={"kegg.reaction": "R1"}),
            FakeReaction("R3", annotation={"kegg.reaction": "R1"}),
            FakeReaction("R4", annotation={"ec-code": "1.1.1.1"}),
        ],
        ["g1", "g2"],
    )

    summaries = summarize_model_components(
        [NamedModel("reference", reference), NamedModel("comparison", comparison)]
    )

    assert summaries["comparison"].gene_associated_reactions == 1
    assert summaries["comparison"].reactions == 4
    assert unannotated_metabolite_percentage(reference) == 100.0
    assert unannotated_metabolite_percentage(comparison) == 50.0
    assert new_reaction_annotation_group_sizes(reference, comparison) == {1: 1, 2: 1}


def test_model_figures_use_explicit_inputs_and_output_directory(tmp_path):
    pytest.importorskip("matplotlib")
    model = FakeModel([FakeMetabolite({})], [FakeReaction("R1")], ["g1"])

    result = generate_model_comparison_figures(
        {"reference": model},
        tmp_path,
        memote_scores={"Total": {"reference": 80.0}},
    )

    assert {path.name for path in result.output_paths} == {
        "non_annotated_metabolites.svg",
        "model_components.svg",
        "memote_categories.svg",
    }
    assert all(path.exists() for path in result.output_paths)
