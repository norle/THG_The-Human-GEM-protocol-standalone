"""Generate publication Figure 1 and its stage/dependency source table.

Regenerate: python publication/scripts/plot_workflow.py
This is a workflow diagram, not evidence of successful model construction.
"""

import csv
from pathlib import Path

from thg_protocol.workflow.beta2._stages import Beta2Stage
from thg_protocol.workflow.reference import REFERENCE_STAGES

ROOT = Path(__file__).resolve().parents[2]
GROUP_ENDS = {
    "export-beta1": "Curate reference\n(beta1)",
    "gate-beta2": "Expand compartments\n(beta2)",
    "integrate-human-database": "Integrate database\n(optional)",
    "export-gapfilled-reference": "Gapfill",
    "export-reference": "Export",
}


def workflow_rows():
    if not set(GROUP_ENDS).issubset(stage.id for stage in REFERENCE_STAGES):
        raise ValueError("Reference workflow changed; review figure grouping")
    groups = iter(GROUP_ENDS.items())
    end, group = next(groups)
    rows = []
    for stage in REFERENCE_STAGES:
        rows.append(
            {
                "stage": stage.id,
                "group": group.replace("\n", " "),
                "dependencies": ";".join(stage.dependencies),
                "implicit_reference_upstream": "export-beta1"
                if isinstance(stage, Beta2Stage)
                else "",
            }
        )
        if stage.id == end and stage.id != "export-reference":
            end, group = next(groups)
    if rows[-1]["stage"] != "export-reference":
        raise ValueError("Reference workflow changed; review figure grouping")
    return rows


def main():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch

    rows = workflow_rows()
    data = ROOT / "publication/ws1/figure1_workflow.csv"
    with data.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0], lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    fig, ax = plt.subplots(figsize=(13, 4.7))
    ax.set(xlim=(-0.15, 5.15), ylim=(-0.9, 2.6))
    ax.axis("off")
    ink, accent = "#243746", "#176B7A"
    for index, label in enumerate(GROUP_ENDS.values()):
        count = sum(row["group"] == label.replace("\n", " ") for row in rows)
        box = FancyBboxPatch(
            (index, 1.45),
            0.83,
            0.72,
            boxstyle="round,pad=0.035",
            facecolor="#EDF3F5",
            edgecolor=accent,
            linewidth=1.2,
        )
        ax.add_patch(box)
        ax.text(
            index + 0.415, 1.93, label, ha="center", va="center", fontsize=10, color=ink
        )
        ax.text(
            index + 0.415,
            1.57,
            f"{count} registered stages",
            ha="center",
            fontsize=8,
            color=ink,
        )
        if index < 4:
            ax.annotate(
                "",
                xy=(index + 0.96, 1.8),
                xytext=(index + 0.88, 1.8),
                arrowprops={"arrowstyle": "->", "color": accent},
            )
    for x, text in (
        (0.415, "Beta1 validation\nand release gate"),
        (1.415, "Beta2 evidence and\nadded-chemistry gate"),
        (3.415, "Gapfill validation\nand release gate"),
    ):
        ax.plot([x, x], [1.4, 1.1], color=accent, linewidth=1)
        ax.text(x, 0.96, text, ha="center", va="center", fontsize=9, color=ink)
    ax.text(
        2.4,
        0.2,
        "Publication evaluation: VerifyModel first → matched quality, "
        "coverage and functional tasks",
        ha="center",
        fontsize=10,
        color=ink,
    )
    ax.annotate(
        "",
        xy=(4.7, 0.38),
        xytext=(4.7, 1.38),
        arrowprops={"arrowstyle": "->", "color": accent},
    )
    ax.text(
        2.4,
        -0.35,
        "Across stages: pinned inputs/config • attempt history • change ledgers • "
        "artifact checksums • service evidence",
        ha="center",
        fontsize=9,
        color=ink,
    )
    ax.set_title(
        "THG protocol: construction, scientific gates and provenance",
        fontsize=14,
        loc="left",
        color=ink,
        pad=12,
    )
    fig.tight_layout()
    out = ROOT / "publication/figures"
    out.mkdir(parents=True, exist_ok=True)
    for suffix in ("svg", "pdf", "png"):
        fig.savefig(out / f"figure1_workflow.{suffix}", dpi=180, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    main()
