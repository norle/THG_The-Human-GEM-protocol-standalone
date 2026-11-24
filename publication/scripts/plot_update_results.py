"""Build draft structural table and figures from checked publication evidence."""

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path("publication")
FIG = ROOT / "figures"
COLORS = ("#547897", "#237463", "#713e87")


def load(path):
    return json.loads(path.read_text())


def read_csv(path):
    with path.open(newline="") as stream:
        return list(csv.DictReader(stream))


def save(fig, name):
    for extension in ("pdf", "svg"):
        fig.savefig(FIG / f"{name}.{extension}", bbox_inches="tight")
    plt.close(fig)


def compartments():
    data = load(ROOT / "ws2/compartment-resolution/summary.json")["variants"]
    labels = ("Both earlier rules", "Keep multi-location genes", "Current GO mapping")
    names = (
        "Cell membrane",
        "Cytosol",
        "Cilium",
        "Cytoskeleton",
        "Golgi",
        "Inner mitochondria",
        "Lysosome",
        "Mitochondria",
        "Nucleus",
        "ER",
        "Vesicle",
        "Peroxisome",
    )
    keys = ("a", "c", "ci", "ck", "g", "i", "l", "m", "n", "r", "v", "x")
    fig, ax = plt.subplots(figsize=(8.3, 5.6), layout="constrained")
    for n, (row, label, color) in enumerate(zip(data, labels, COLORS, strict=True)):
        ax.barh(
            [i + (n - 1) * 0.23 for i in range(len(keys))],
            [row["copies_by_compartment"].get(key, 0) for key in keys],
            height=0.2,
            color=color,
            label=(
                f"{label} ({row['copies']:,} copies, {row['genes_localised']:,} genes)"
            ),
        )
    ax.set_yticks(range(len(names)), names)
    ax.invert_yaxis()
    ax.set_xlabel("Proposed reaction copies")
    ax.legend(loc="upper left", bbox_to_anchor=(0, -0.12), frameon=False, fontsize=9)
    ax.spines[["top", "right"]].set_visible(False)
    save(fig, "figure2_compartment_ablation")


def tasks():
    stage_paths = (
        ROOT / "ws1/numerical-refresh/task_results_stage-b-beta1",
        ROOT / "ws1/numerical-refresh/task_results_stage-b-beta2",
        ROOT / "ws1/rebuild-b/gates/task_results_b-rebuilt-final-verify",
    )
    stage_ids = ("export-beta1", "export-beta2", "export-reference")
    steps = load(Path("runs/thg-ws1-b/manifest.json"))["steps"]
    passed = []
    for stage, path in zip(stage_ids, stage_paths, strict=True):
        expected = next(
            o["sha256"] for o in steps[stage]["outputs"] if o["role"] == "model"
        )
        assert load(path.with_suffix(".json"))["model_sha256"] == expected
        rows = read_csv(path.with_suffix(".csv"))
        verify = [r for r in rows if r["table"] == "VerifyModel"]
        assert len(verify) == 21
        passed.append(sum(r["status"] == "passed" for r in verify))
    paths = (
        ROOT / "ws2/historical-failure/task_results_archived-beta1.csv",
        ROOT / "ws0/unpatched-recheck/task_results_human211-unpatched.csv",
    )
    residuals = [
        float(
            next(
                r["max_bound_violation"] for r in read_csv(path) if r["task_id"] == "21"
            )
        )
        for path in paths
    ]
    fig, (left, right) = plt.subplots(1, 2, figsize=(8.3, 3.6), layout="constrained")
    bars = left.bar(["β1", "β2", "Final"], passed, color=COLORS[1], width=0.54)
    left.bar_label(bars, fmt="%d / 21", padding=3)
    left.set_ylim(0, 25)
    left.set_ylabel("VerifyModel tasks passed")
    right.scatter(residuals, [0, 1], s=60, color=COLORS[2], zorder=3)
    right.axvline(1e-7, color="0.35", linestyle="--", label="Reliability threshold")
    right.set_yticks([0, 1], ["Archived β1", "Unpatched 2.1.1"])
    right.set_xscale("log")
    right.set_xlim(6e-8, 1e-6)
    right.set_ylim(-0.5, 1.5)
    right.set_xlabel("Task 21 maximum bound violation")
    right.legend(frameon=False, loc="upper right", fontsize=8)
    for ax in (left, right):
        ax.spines[["top", "right"]].set_visible(False)
    save(fig, "figure3_expansion_safeguards")


def table():
    outputs = (
        ("THG-2023 (historical)", ROOT / "ws3/model_stats_thg-2023.csv", ()),
        (
            "Patched Human-GEM 2.1.1",
            ROOT / "ws0/model_stats_patched.csv",
            (ROOT / "ws0/pinned-refresh/task_results_human211-patched.csv",),
        ),
        (
            "Rebuilt THG",
            ROOT / "ws3/model_stats_rebuilt-b.csv",
            (
                ROOT / "ws1/rebuild-b/gates/task_results_b-rebuilt-final.csv",
                ROOT / "ws1/rebuild-b/gates/task_results_b-rebuilt-final-verify.csv",
            ),
        ),
    )
    stats = ("reactions", "metabolites", "genes", "compartments")
    tables = ("VerifyModel", "Essential", "Full")
    with (ROOT / "manuscript/table1.csv").open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(
            (
                "model",
                *stats,
                *(
                    f"{name}_{status}"
                    for name in tables
                    for status in ("passed", "total", "invalid", "error")
                ),
            )
        )
        for label, path, reports in outputs:
            (row,) = read_csv(path)
            counts = Counter(
                (task["table"], task["status"])
                for report in reports
                for task in read_csv(report)
            )
            outcomes = []
            for name in tables:
                total = sum(
                    count for (table, _), count in counts.items() if table == name
                )
                outcomes.extend(
                    (
                        counts[name, "passed"],
                        total,
                        counts[name, "invalid"],
                        counts[name, "error"],
                    )
                    if total
                    else ("",) * 4
                )
            writer.writerow((label, *(row[k] for k in stats), *outcomes))


def flux_coverage():
    run = Path("runs/thg-ws1-b")
    steps = load(run / "manifest.json")["steps"]

    def artifact(stage, role):
        row = next(o for o in steps[stage]["outputs"] if o["role"] == role)
        path = run / row["path"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == row["sha256"]
        return path, row["sha256"]

    gate, gate_hash = artifact("validate-gapfill", "validation")
    applied, applied_hash = artifact("apply-gapfill", "model")
    final, final_hash = artifact("export-reference", "model")
    plan, plan_hash = artifact("generate-gapfill-plan", "plan")
    result = load(gate)
    assert result["result_model_checksum"] == applied_hash
    applied_model, final_model = load(applied), load(final)
    assert {k: v for k, v in applied_model.items() if k != "annotation"} == {
        k: v for k, v in final_model.items() if k != "annotation"
    }, "Construction-stage flux classification cannot be applied to final export"
    before = set(result["before"]["blocked_reactions"])
    after = set(result["after"]["blocked_reactions"])
    reaction_ids = {r["id"] for r in final_model["reactions"]}
    plan_rows = [json.loads(line) for line in plan.read_text().splitlines()[1:]]
    groups = {
        "β2 copies": {rid for rid in reaction_ids if rid.startswith("THG_")},
        "Gapfill connectors": {r["reaction_id"] for r in plan_rows if r["phase"] == 2},
        "Selected transports": {r["reaction_id"] for r in plan_rows if r["phase"] == 3},
    }
    assert after <= reaction_ids and set.union(*groups.values()) <= reaction_ids
    counts = {
        label: {"flux_capable": len(ids - after), "blocked": len(ids & after)}
        for label, ids in groups.items()
    }
    summary = {
        "sources": {
            str(path): checksum
            for path, checksum in (
                (gate, gate_hash),
                (applied, applied_hash),
                (final, final_hash),
                (plan, plan_hash),
            )
        },
        "method": "COBRApy blocked reaction check with model exchange bounds",
        "model_scope": "Applied model and final JSON differ only in model annotation",
        "blocked_before_gapfill": len(before),
        "blocked_after_gapfill": len(after),
        "previously_blocked_now_flux_capable": len(before - after),
        "previously_blocked_copies_now_flux_capable": len(
            (before - after) & groups["β2 copies"]
        ),
        "newly_blocked_preexisting_reactions": len(
            (after - before)
            - groups["Selected transports"]
            - groups["Gapfill connectors"]
        ),
        "additions": counts,
    }
    (ROOT / "ws4/coverage-rebuilt-b/flux_coverage.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n"
    )
    fig, (ax, quality) = plt.subplots(1, 2, figsize=(11.5, 3.35), layout="constrained")
    labels = list(counts)
    capable = [counts[label]["flux_capable"] for label in labels]
    blocked = [counts[label]["blocked"] for label in labels]
    totals = [yes + no for yes, no in zip(capable, blocked, strict=True)]
    fractions = [100 * yes / total for yes, total in zip(capable, totals, strict=True)]
    ax.barh(labels, fractions, color=COLORS[1], label="Flux-capable")
    ax.barh(
        labels,
        [100 - f for f in fractions],
        left=fractions,
        color="#b5bac0",
        label="Blocked",
    )
    for index, (yes, total) in enumerate(zip(capable, totals, strict=True)):
        ax.text(103, index, f"{yes:,} / {total:,}", va="center", fontsize=10)
    ax.invert_yaxis()
    ax.set_xlim(0, 120)
    ax.set_xticks(range(0, 101, 20))
    ax.set_xlabel("Share of each group (%)")
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1), frameon=False, ncols=2)
    metrics = {
        row["metric"]: row
        for row in read_csv(ROOT / "ws4/matched-refresh/quality_table.csv")
    }
    keys = ("blocked_reactions", "dead_end_metabolites")
    for offset, (column, label, color) in enumerate(
        (
            ("patched", "Patched baseline", COLORS[0]),
            ("rebuilt-b", "Rebuilt THG", COLORS[2]),
        )
    ):
        bars = quality.barh(
            [i + (offset - 0.5) * 0.28 for i in range(len(keys))],
            [int(metrics[key][column]) for key in keys],
            height=0.24,
            label=label,
            color=color,
        )
        quality.bar_label(bars, fmt="{:,.0f}", padding=3, fontsize=9)
    quality.set_yticks([0, 1], ["Blocked reactions", "Dead-end metabolites"])
    quality.invert_yaxis()
    quality.set_xlim(0, 4350)
    quality.set_xlabel("Count in matched validation")
    quality.legend(loc="lower center", bbox_to_anchor=(0.5, 1), frameon=False, ncols=2)
    for axis in (ax, quality):
        axis.spines[["top", "right"]].set_visible(False)
    save(fig, "figure4_flux_coverage")


if __name__ == "__main__":
    compartments()
    tasks()
    table()
    flux_coverage()
