"""Import-safe report-driven comparison figures.

The legacy figure script reads annotation comparison tables from an Excel
workbook and writes three annotation-group charts.  This module makes that
contract explicit.  Reading Excel files and rendering charts are deferred
until the corresponding functions are called, so importing the package does
not require a plotting backend or load models.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

__all__ = [
    "AnnotationGroupSummary",
    "FigureGenerationResult",
    "annotation_group_percentages",
    "generate_annotation_comparison_figures",
    "read_annotation_group_summary",
    "summarize_annotation_rows",
]


@dataclass(frozen=True)
class AnnotationGroupSummary:
    """Percentages for unchanged, replaced, and added annotations.

    The values retain the legacy workflow's cumulative interpretation: group
    ``3`` includes rows marked 1, 2, or 3; group ``2`` includes 1 or 2; and
    group ``1`` includes only 1.
    """

    added: float
    replaced: float
    unchanged: float


@dataclass(frozen=True)
class FigureGenerationResult:
    """Files produced by
    [`generate_annotation_comparison_figures`][thg_protocol.figures.comparison.generate_annotation_comparison_figures]."""

    report_path: Path
    output_paths: tuple[Path, ...]


def annotation_group_percentages(values: Iterable[Any]) -> AnnotationGroupSummary:
    """Calculate legacy annotation-group percentages from cell values."""
    values = list(values)
    denominator = len(values)
    if denominator == 0:
        return AnnotationGroupSummary(0.0, 0.0, 0.0)

    def percentage(allowed: set[float]) -> float:
        return sum(value in allowed for value in values) / denominator * 100

    return AnnotationGroupSummary(
        added=percentage({1.0, 2.0, 3.0}),
        replaced=percentage({1.0, 2.0}),
        unchanged=percentage({1.0}),
    )


def summarize_annotation_rows(
    rows: Iterable[Mapping[str, Any]], columns: Sequence[str]
) -> dict[str, AnnotationGroupSummary]:
    """Summarize named columns without requiring pandas."""
    rows = list(rows)
    return {
        column: annotation_group_percentages(row.get(column) for row in rows)
        for column in columns
    }


def read_annotation_group_summary(
    report_path: str | Path,
    *,
    sheet_name: int | str,
    columns: Sequence[str],
) -> dict[str, AnnotationGroupSummary]:
    """Read one annotation sheet from an Excel report and summarize it.

    Pandas and its Excel engine are imported only when this file-oriented API
    is called.  A ``ValueError`` identifies missing columns before rendering
    begins, which makes malformed report inputs straightforward to diagnose.
    """
    import pandas as pd

    frame = pd.read_excel(report_path, sheet_name=sheet_name)
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise ValueError(
            f"Report sheet {sheet_name!r} is missing columns: {', '.join(missing)}"
        )
    return summarize_annotation_rows(
        frame.loc[:, list(columns)].to_dict(orient="records"), columns
    )


def _render_annotation_chart(
    summary: Mapping[str, AnnotationGroupSummary], output_path: Path
) -> None:
    """Render one summary chart using optional plotting dependencies."""
    import matplotlib.pyplot as plt

    labels = list(summary)
    values = [summary[label] for label in labels]
    positions = list(range(len(labels)))
    width = 0.24

    figure, axis = plt.subplots(figsize=(20, 9))
    axis.bar(
        [position - width for position in positions],
        [value.added for value in values],
        width=width,
        color="#4A708B",
        label="add",
    )
    axis.bar(
        positions,
        [value.replaced for value in values],
        width=width,
        color="#8470FF",
        label="replace",
    )
    axis.bar(
        [position + width for position in positions],
        [value.unchanged for value in values],
        width=width,
        color="#7A378B",
        label="no change",
    )
    axis.set_xticks(positions, labels)
    axis.set_ylabel("Percentage")
    axis.legend(title="Group")
    figure.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_path, format="svg")
    plt.close(figure)


def generate_annotation_comparison_figures(
    report_path: str | Path, output_dir: str | Path
) -> FigureGenerationResult:
    """Generate the three workbook-backed annotation comparison figures.

    The report uses the historical zero-based sheet positions 4, 5, and 6.
    The returned paths are deterministic and are created below ``output_dir``.
    Plotting dependencies are required only when this function is executed.
    """
    report_path = Path(report_path).expanduser()
    output_dir = Path(output_dir).expanduser()
    specifications = (
        (
            4,
            (
                "KEGG.COMPOUND",
                "CHEBI",
                "LIPIDMAPS",
                "PUBCHEM.COMPOUND",
                "INCHIKEY",
                "INCHIKEY.1",
            ),
            "metabolites_annot_group-THG-beta-1_vs_Human1.svg",
        ),
        (
            5,
            (
                "MASS_BALANCE GROUP [1,2]",
                "KEGG.REACTION GROUP [1,2,3]",
                "GENE ASSOCIATION GROUP [1,2,3]",
            ),
            "reaction_annot_group-THG-beta-1_vs_Human1.svg",
        ),
        (6, ("ENSEMBLE GROUP [1,2,3]",), "genes_annot_group.svg"),
    )
    outputs: list[Path] = []
    for sheet_name, columns, filename in specifications:
        summary = read_annotation_group_summary(
            report_path, sheet_name=sheet_name, columns=columns
        )
        destination = output_dir / filename
        _render_annotation_chart(summary, destination)
        outputs.append(destination)
    return FigureGenerationResult(report_path, tuple(outputs))
