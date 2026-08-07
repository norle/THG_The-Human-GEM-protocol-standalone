"""Model-derived and explicitly supplied score figures.

The legacy figure script loaded four repository models and rendered charts as a
side effect of import.  This module accepts already-loaded model-like objects
instead.  COBRA is therefore needed only by a caller that chooses to load SBML
files; the pure summaries and package import remain dependency-light.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

__all__ = [
    "NamedModel",
    "ModelComponentSummary",
    "ModelFigureGenerationResult",
    "generate_model_comparison_figures",
    "model_component_summary",
    "new_reaction_annotation_group_sizes",
    "summarize_model_components",
    "unannotated_metabolite_percentage",
]


@dataclass(frozen=True)
class NamedModel:
    """A model and the label used in generated figures."""

    name: str
    model: Any


@dataclass(frozen=True)
class ModelComponentSummary:
    """Counts corresponding to the legacy model-components chart."""

    genes: int
    gene_associated_reactions: int
    metabolites: int
    reactions: int


@dataclass(frozen=True)
class ModelFigureGenerationResult:
    """Paths created by
    [`generate_model_comparison_figures`][thg_protocol.figures.models.generate_model_comparison_figures]."""

    output_paths: tuple[Path, ...]


def _named_models(
    models: Mapping[str, Any] | Sequence[NamedModel],
) -> tuple[NamedModel, ...]:
    if isinstance(models, Mapping):
        return tuple(NamedModel(str(name), model) for name, model in models.items())
    return tuple(models)


def model_component_summary(model: Any) -> ModelComponentSummary:
    """Summarize one model without importing COBRA."""
    reactions = tuple(model.reactions)
    return ModelComponentSummary(
        genes=len(model.genes),
        gene_associated_reactions=sum(
            bool(getattr(reaction, "gene_reaction_rule", "")) for reaction in reactions
        ),
        metabolites=len(model.metabolites),
        reactions=len(reactions),
    )


def summarize_model_components(
    models: Mapping[str, Any] | Sequence[NamedModel],
) -> dict[str, ModelComponentSummary]:
    """Return component counts keyed by the supplied model labels."""
    return {
        item.name: model_component_summary(item.model) for item in _named_models(models)
    }


def unannotated_metabolite_percentage(model: Any) -> float:
    """Return the legacy percentage of metabolites with no external IDs."""
    metabolites = tuple(model.metabolites)
    if not metabolites:
        return 0.0
    annotation_keys = {"bigg.metabolite", "sbo", "vmhmetabolite"}
    unannotated = sum(
        sorted(getattr(metabolite, "annotation", {})) == sorted(annotation_keys)
        for metabolite in metabolites
    )
    return unannotated / len(metabolites) * 100


def new_reaction_annotation_group_sizes(
    reference_model: Any, comparison_model: Any
) -> dict[int, int]:
    """Count groups of new reactions by their annotation mapping.

    The legacy chart grouped reactions absent from ``reference_model`` by the
    string representation of their annotation mapping, then plotted the size
    of each group.  This function preserves that statistic while returning a
    deterministic, serializable mapping from group size to group count.
    """
    reference_ids = {reaction.id for reaction in reference_model.reactions}
    groups: Counter[str] = Counter(
        str(getattr(reaction, "annotation", {}))
        for reaction in comparison_model.reactions
        if reaction.id not in reference_ids
    )
    return dict(sorted(Counter(groups.values()).items()))


def _pyplot() -> Any:
    """Import matplotlib only when rendering is requested."""
    try:
        import matplotlib.pyplot as plt
    except ImportError as error:  # pragma: no cover - environment dependent
        raise RuntimeError(
            "Figure rendering requires the 'figures' optional dependency"
        ) from error
    return plt


def _bar_chart(
    labels: Sequence[str],
    series: Sequence[tuple[str, Sequence[float]]],
    output_path: Path,
    *,
    title: str,
    ylabel: str = "",
) -> None:
    plt = _pyplot()
    figure, axis = plt.subplots(figsize=(20, 9))
    positions = list(range(len(labels)))
    width = 0.8 / max(len(series), 1)
    for index, (label, values) in enumerate(series):
        offsets = [position - 0.4 + width / 2 + index * width for position in positions]
        axis.bar(offsets, values, width=width, label=label)
    axis.set_xticks(positions, labels)
    axis.set_title(title)
    axis.set_ylabel(ylabel)
    if series:
        axis.legend(title="Model")
    figure.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_path, format="svg")
    plt.close(figure)


def _pie_chart(values: Mapping[str, float], output_path: Path, *, title: str) -> None:
    plt = _pyplot()
    figure, axis = plt.subplots(figsize=(8, 6))
    axis.pie(list(values.values()), labels=list(values), autopct="%1.1f%%")
    axis.set_title(title)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.tight_layout()
    figure.savefig(output_path, format="svg")
    plt.close(figure)


def generate_model_comparison_figures(
    models: Mapping[str, Any] | Sequence[NamedModel],
    output_dir: str | Path,
    *,
    reference_model: Any | None = None,
    new_reaction_model: Any | None = None,
    memote_scores: Mapping[str, Mapping[str, float]] | None = None,
    algorithm_results: Mapping[str, Mapping[str, float]] | None = None,
) -> ModelFigureGenerationResult:
    """Render figures from explicit models and optional score datasets.

    ``models`` supplies the inputs for the non-annotated-metabolite and model
    component charts.  ``reference_model`` and ``new_reaction_model`` enable
    the new-reaction annotation chart.  Score charts are generated only when
    their data is passed explicitly; no historical hard-coded scores are
    embedded in the package.
    """
    named_models = _named_models(models)
    if not named_models:
        raise ValueError("At least one named model is required")
    output_dir = Path(output_dir).expanduser()
    outputs: list[Path] = []

    labels = [item.name for item in named_models]
    unannotated_path = output_dir / "non_annotated_metabolites.svg"
    unannotated = [
        unannotated_metabolite_percentage(item.model) for item in named_models
    ]
    _bar_chart(
        labels,
        [("unannotated", unannotated)],
        unannotated_path,
        title="Metabolites with no metabolic database annotation",
        ylabel="Percentage",
    )
    outputs.append(unannotated_path)

    components = summarize_model_components(named_models)
    component_labels = (
        "Genes",
        "Gene reaction associations",
        "Metabolites",
        "Reactions",
    )
    component_path = output_dir / "model_components.svg"
    _bar_chart(
        component_labels,
        [
            (
                name,
                [
                    summary.genes,
                    summary.gene_associated_reactions,
                    summary.metabolites,
                    summary.reactions,
                ],
            )
            for name, summary in components.items()
        ],
        component_path,
        title="Model components",
    )
    outputs.append(component_path)

    if reference_model is not None and new_reaction_model is not None:
        group_sizes = new_reaction_annotation_group_sizes(
            reference_model, new_reaction_model
        )
        reaction_path = output_dir / "new_reaction_annotation_groups.svg"
        _bar_chart(
            [str(size) for size in group_sizes],
            [("Groups", list(group_sizes.values()))],
            reaction_path,
            title="New reaction annotation groups",
            ylabel="Unique reactions",
        )
        outputs.append(reaction_path)

    if memote_scores:
        score_labels = list(memote_scores)
        score_models = sorted(
            {model_name for scores in memote_scores.values() for model_name in scores}
        )
        memote_path = output_dir / "memote_categories.svg"
        _bar_chart(
            score_labels,
            [
                (
                    model_name,
                    [
                        memote_scores[label].get(model_name, 0.0)
                        for label in score_labels
                    ],
                )
                for model_name in score_models
            ],
            memote_path,
            title="MEMOTE categories",
            ylabel="Percentage",
        )
        outputs.append(memote_path)

    for name, values in (algorithm_results or {}).items():
        algorithm_path = output_dir / f"algorithm_{name.lower().replace(' ', '_')}.svg"
        _pie_chart(values, algorithm_path, title=name)
        outputs.append(algorithm_path)

    return ModelFigureGenerationResult(tuple(outputs))
