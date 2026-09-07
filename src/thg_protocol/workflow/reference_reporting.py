"""Reference construction report and release bundle stages."""

from __future__ import annotations

import shutil
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from thg_protocol.analysis.compare import compare_semantic_models
from thg_protocol.io.models import load_model, save_json, save_sbml
from thg_protocol.runtime.hashing import sha256_file
from thg_protocol.runtime.stage import (
    StageContext,
    StageResult,
    dependency_path,
    dump_json,
)


def _counts(model: Any) -> dict[str, int]:
    return {
        "reactions": len(model.reactions),
        "metabolites": len(model.metabolites),
        "genes": len(model.genes),
    }


def _changes(diff: Mapping[str, object]) -> dict[str, dict[str, int]]:
    raw = diff.get("diff", diff)
    return {
        kind: {
            change: (
                len(raw.get(change, {}).get(kind, []))
                if isinstance(raw, Mapping)
                else 0
            )
            for change in ("added", "removed", "changed")
        }
        for kind in ("reactions", "metabolites", "genes")
    }


def _markdown(report: Mapping[str, object]) -> str:
    lines = [
        "# THG Reference Model Construction Report",
        "",
        "## Input",
        "",
        "| Metric | Count |",
        "|---|---:|",
    ]
    for key, value in report["input"]["counts"].items():
        lines.append(f"| {key.title()} | {value} |")
    for stage in report["stages"]:
        lines.extend(("", f"## {stage['id']}", "", "| Change | Count |", "|---|---:|"))
        for kind, values in stage["changes"].items():
            for change, value in values.items():
                lines.append(f"| {kind.title()} {change} | {value} |")
    lines.extend(
        (
            "",
            "## Overall",
            "",
            "| Metric | Input | Final | Net |",
            "|---|---:|---:|---:|",
        )
    )
    overall = report["overall"]
    for key, before in overall["counts_before"].items():
        after = overall["counts_after"][key]
        lines.append(f"| {key.title()} | {before} | {after} | {after - before:+d} |")
    return "\n".join(lines) + "\n"


class ReferenceReportStage:
    implementation_version = 1

    def __init__(self, stage_id: str, dependencies: tuple[str, ...]) -> None:
        self.id, self.dependencies = stage_id, dependencies
        self.output_role, self.kind = "artifact", "analysis"

    def enabled(self, config: Any) -> bool:
        return True

    def fingerprint_data(self, context: StageContext) -> Mapping[str, object]:
        return {
            "stage": self.id,
            "version": self.implementation_version,
            "dependencies": list(self.dependencies),
        }

    def run(self, context: StageContext, work_dir: Path) -> StageResult:
        if self.id == "summarize-reference":
            input_path = Path(str(context.config.sections["beta1"]["input_model"]))
            paths = [
                (
                    "beta1",
                    input_path,
                    dependency_path(context, "export-beta1", "model"),
                ),
                (
                    "beta2",
                    dependency_path(context, "export-beta1", "model"),
                    dependency_path(context, "export-beta2", "model"),
                ),
            ]
            integrated = context.manifest.get("steps", {}).get(
                "integrate-human-database", {}
            )
            if (
                isinstance(integrated, Mapping)
                and integrated.get("status") == "completed"
            ):
                paths.append(
                    (
                        "human-database",
                        dependency_path(context, "export-beta2", "model"),
                        dependency_path(context, "integrate-human-database", "model"),
                    )
                )
            pre_gapfill = paths[-1][2]
            final = dependency_path(context, "export-gapfilled-reference", "model")
            paths.append(("gapfill", pre_gapfill, final))
            stages = []
            artifacts: dict[str, str] = {}
            semantic_paths: list[Path] = []
            for stage_id in (
                "export-beta1",
                "export-beta2",
                "integrate-human-database",
                "export-gapfilled-reference",
            ):
                entry = context.manifest.get("steps", {}).get(stage_id, {})
                if isinstance(entry, Mapping):
                    for output in entry.get("outputs", []):
                        if isinstance(output, Mapping) and output.get("role") in {
                            "ledger",
                            "merge-report",
                            "model-diff",
                            "gapfill-change-ledger",
                        }:
                            artifacts[f"{stage_id}-{output['role']}"] = str(
                                output.get("path")
                            )
            for name, before_path, after_path in paths:
                before, after = load_model(before_path), load_model(after_path)
                semantic = compare_semantic_models(before, after)
                diff_path = dump_json(work_dir / f"{name}-semantic-diff.json", semantic)
                semantic_paths.append(diff_path)
                artifacts[f"{name}-semantic-diff"] = diff_path.name
                source_stage = {
                    "beta1": "export-beta1",
                    "beta2": "export-beta2",
                    "human-database": "integrate-human-database",
                    "gapfill": "apply-gapfill",
                }[name]
                entry = context.manifest.get("steps", {}).get(source_stage, {})
                metrics = entry.get("summary", {}) if isinstance(entry, Mapping) else {}
                stages.append(
                    {
                        "id": name,
                        "enabled": True,
                        "input_sha256": sha256_file(before_path),
                        "output_sha256": sha256_file(after_path),
                        "counts_before": _counts(before),
                        "counts_after": _counts(after),
                        "changes": _changes(semantic),
                        "metrics": metrics,
                    }
                )
            source, result = load_model(input_path), load_model(final)
            overall = compare_semantic_models(source, result)
            overall_path = dump_json(
                work_dir / "input-to-reference-semantic-diff.json", overall
            )
            semantic_paths.append(overall_path)
            artifacts["input-to-reference-semantic-diff"] = overall_path.name
            report = {
                "schema_version": 1,
                "workflow": "reference",
                "run": context.config.run.name,
                "input": {
                    "model_id": str(source.id),
                    "sha256": sha256_file(input_path),
                    "counts": _counts(source),
                },
                "stages": stages,
                "overall": {
                    "counts_before": _counts(source),
                    "counts_after": _counts(result),
                    "changes": _changes(overall),
                },
                "artifacts": artifacts,
                "construction_status": "complete",
                "validation_status": "not-run",
            }
            report_path = dump_json(work_dir / "reference-report.json", report)
            md_path = work_dir / "reference-report.md"
            md_path.write_text(_markdown(report), encoding="utf-8")
            return StageResult(
                (
                    ("report", report_path),
                    ("report-markdown", md_path),
                    ("overall-diff", overall_path),
                    *tuple(
                        ("semantic-diff", path)
                        for path in semantic_paths
                        if path != overall_path
                    ),
                ),
                report,
            )
        model = load_model(
            dependency_path(context, "export-gapfilled-reference", "model")
        )
        model.annotation["thg.construction_status"] = "complete"
        model.annotation["thg.validation_status"] = "not-run"
        model_path, sbml_path = (
            work_dir / "thg-reference.json",
            work_dir / "thg-reference.xml",
        )
        save_json(model, model_path)
        save_sbml(model, sbml_path)
        checksums = {
            stage: [item.get("sha256") for item in entry.get("outputs", [])]
            for stage, entry in context.manifest.get("steps", {}).items()
            if isinstance(entry, Mapping) and entry.get("status") == "completed"
        }
        checksums[self.id] = [sha256_file(model_path), sha256_file(sbml_path)]
        report = dependency_path(context, "summarize-reference", "report")
        markdown = dependency_path(context, "summarize-reference", "report-markdown")
        outputs = [("model", model_path), ("sbml", sbml_path)]
        for role, source, name in (
            ("report", report, "reference-report.json"),
            ("report-markdown", markdown, "reference-report.md"),
        ):
            target = work_dir / name
            shutil.copy2(source, target)
            outputs.append((role, target))
        for artifact in context.manifest["steps"]["summarize-reference"]["outputs"]:
            if artifact.get("role") in {"semantic-diff", "overall-diff"}:
                source = context.run_dir / str(artifact["path"])
                target = work_dir / source.name
                shutil.copy2(source, target)
                outputs.append((str(artifact["role"]), target))
        outputs.extend(
            (
                (
                    "checksums",
                    dump_json(work_dir / "reference-checksums.json", checksums),
                ),
                (
                    "provenance",
                    dump_json(
                        work_dir / "reference-provenance.json",
                        {
                            "configuration_checksum": context.manifest.get(
                                "config_sha256"
                            ),
                            "checksums": checksums,
                            "construction_status": "complete",
                            "validation_status": "not-run",
                        },
                    ),
                ),
            )
        )
        return StageResult(
            tuple(outputs),
            {"construction_status": "complete", "validation_status": "not-run"},
        )

    def validate(self, result: StageResult) -> None:
        if not result.outputs or any(not path.is_file() for _, path in result.outputs):
            raise ValueError(f"stage '{self.id}' did not produce complete artifacts")
