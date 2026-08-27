"""Registered, proposal-first gapfill workflow stages."""

from __future__ import annotations

import json
import platform
import shutil
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from thg_protocol.io.models import load_model as _load_cobra_model
from thg_protocol.runtime.hashing import sha256_file, verify_artifact
from thg_protocol.runtime.stage import (
    StageContext,
    StageResult,
)
from thg_protocol.runtime.stage import (
    dependency_path as _dependency_path,
)
from thg_protocol.runtime.stage import (
    dependency_records as _dependency_records,
)
from thg_protocol.runtime.stage import (
    dump_json as _dump,
)

from .registry import WorkflowDefinition


def _section(context: StageContext) -> Mapping[str, object]:
    value = context.config.sections.get("gapfill", {})
    return value if isinstance(value, Mapping) else {}


def _software() -> dict[str, str]:
    try:
        import cobra

        cobra_version = str(cobra.__version__)
    except Exception:
        cobra_version = "unknown"
    try:
        from thg_protocol import __version__

        package_version = str(__version__)
    except Exception:
        package_version = "unknown"
    return {
        "thg_protocol": package_version,
        "python": platform.python_version(),
        "cobra": cobra_version,
    }


def _hash(path: object) -> str | None:
    return (
        sha256_file(str(path))
        if isinstance(path, str) and Path(path).is_file()
        else None
    )


def _dependency_hashes(
    context: StageContext, dependencies: tuple[str, ...]
) -> dict[str, list[str]]:
    return {
        stage_id: [
            str(item.get("sha256")) for item in _dependency_records(context, stage_id)
        ]
        for stage_id in dependencies
    }


def _model_counts(model: Any) -> dict[str, int]:
    return {
        "reactions": len(model.reactions),
        "metabolites": len(model.metabolites),
        "genes": len(model.genes),
        "compartments": len(model.compartments),
    }


def _metrics(model: Any) -> dict[str, object]:
    from thg_protocol.analysis import consistency
    from thg_protocol.analysis.network import find_network_components

    result: dict[str, object] = _model_counts(model)
    result["blocked_reactions"] = sorted(consistency.blocked_reactions(model))
    result["dead_end_metabolites"] = sorted(consistency.dead_end_metabolites(model))
    network = find_network_components(model)
    result["network_components"] = len(network["components"])
    total = network["graph"].number_of_nodes()
    result["largest_component_fraction"] = (
        len(network["largest_component"]) / total if total else 0.0
    )
    solution = model.optimize()
    result["objective_feasibility"] = {
        "status": str(solution.status),
        "objective": float(solution.objective_value or 0.0),
    }
    return result


def _safe_metrics(model: Any) -> dict[str, object]:
    try:
        return _metrics(model)
    except Exception as error:
        return {"error": {"type": type(error).__name__, "message": str(error)}}


def _task_report(model: Any, section: Mapping[str, object]) -> dict[str, object]:
    task_suite = section.get("task_suite")
    if not isinstance(task_suite, str):
        return {"status": "not-requested", "tasks": [], "passed": None}
    from thg_protocol.tasks import load_task_suite, run_task_suite

    return run_task_suite(model, load_task_suite(task_suite))


def _as_error_status(value: object) -> object:
    if isinstance(value, dict):
        result = {key: _as_error_status(item) for key, item in value.items()}
        if result.get("status") == "infrastructure-error":
            result["status"] = "error"
        return result
    if isinstance(value, list):
        return [_as_error_status(item) for item in value]
    return value


def _plan_file(path: Path) -> dict[str, object]:
    lines = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if (
        not lines
        or not isinstance(lines[0], dict)
        or lines[0].get("record_type") != "header"
    ):
        raise ValueError("gapfill plan is missing its header")
    header = dict(lines[0])
    return {"header": header, "proposals": lines[1:]}


def _write_plan(path: Path, plan: Mapping[str, object]) -> None:
    header = dict(plan["header"])
    header["record_type"] = "header"
    records = [header, *plan.get("proposals", [])]
    path.write_text(
        "".join(
            json.dumps(item, sort_keys=True, default=str) + "\n" for item in records
        ),
        encoding="utf-8",
    )


def _model_diff_is_clean(diff: Mapping[str, object]) -> bool:
    return not diff.get("model", {}).get("changed", False) and not any(
        values
        for kind in ("removed", "changed")
        for values in (
            diff.get(kind, {}).values() if isinstance(diff.get(kind), Mapping) else ()
        )
    )


class Beta2GateStage:
    implementation_version = 1
    id = "gate-beta2"
    dependencies = ("export-beta2",)

    def enabled(self, config: Any) -> bool:
        del config
        return True

    def fingerprint_data(self, context: StageContext) -> Mapping[str, object]:
        records = _dependency_records(context, "export-beta2")
        return {
            "stage": self.id,
            "implementation_version": self.implementation_version,
            "model": [item for item in records if item.get("role") == "model"],
        }

    def run(self, context: StageContext, work_dir: Path) -> StageResult:
        from thg_protocol.curation.beta2 import beta2_release_gate

        records = _dependency_records(context, "export-beta2")
        model_records = [item for item in records if item.get("role") == "model"]
        if len(model_records) != 1:
            raise ValueError("export-beta2 must provide exactly one model artifact")
        record = model_records[0]
        if not verify_artifact(record, context.run_dir):
            raise ValueError("export-beta2 model artifact checksum verification failed")
        model_path = context.run_dir / str(record["path"])
        gate = beta2_release_gate(model_path.parent)
        result = {
            "schema_version": 1,
            "status": "passed" if gate.get("passed") else "blocked",
            "passed": bool(gate.get("passed")),
            "reasons": gate.get("reasons", []),
            "artifact": {
                "workflow": "beta2",
                "run": context.config.run.name,
                "run_dir": str(context.run_dir),
                "stage": "export-beta2",
                "stage_id": "export-beta2",
                "role": "model",
                "artifact_checksum": record.get("sha256"),
                "validation_result": gate.get("validation", {}),
            },
            "software": _software(),
        }
        path = _dump(work_dir / "beta2-gate.json", result)
        return StageResult((("gate", path),), result)

    def validate(self, result: StageResult) -> None:
        if not result.outputs or any(not path.is_file() for _, path in result.outputs):
            raise ValueError("gate-beta2 did not produce its report")
        if result.summary.get("status") != "passed":
            raise ValueError("β2 release gate did not pass")


class GapfillStage:
    implementation_version = 1

    def __init__(self, stage_id: str, dependencies: tuple[str, ...] = ()) -> None:
        self.id = stage_id
        self.dependencies = dependencies

    def enabled(self, config: Any) -> bool:
        del config
        return True

    def fingerprint_data(self, context: StageContext) -> Mapping[str, object]:
        section = _section(context)
        data: dict[str, object] = {
            "stage": self.id,
            "implementation_version": self.implementation_version,
            "dependencies": _dependency_hashes(context, self.dependencies)
            if self.dependencies
            else {},
        }
        if self.id == "load-gapfill-source":
            data["workflow"] = context.config.workflow
            data["input_sha256"] = _hash(section.get("input_model"))
            data["external_input"] = section.get("external_input")
        elif self.id == "generate-gapfill-plan":
            data["algorithm"] = {
                key: value
                for key, value in section.items()
                if key not in {"validation_profile", "task_suite"}
            }
            data["candidate_universe_sha256"] = _hash(section.get("candidate_universe"))
            data["universal_model_sha256"] = _hash(section.get("universal_model"))
        elif self.id == "characterize-gapfill-baseline":
            data["validation_profile"] = section.get("validation_profile")
            data["task_suite_sha256"] = _hash(section.get("task_suite"))
        elif self.id in {
            "validate-gapfill",
            "gate-gapfill",
            "export-gapfilled-reference",
        }:
            data["validation_profile"] = section.get("validation_profile")
            data["task_suite_sha256"] = _hash(section.get("task_suite"))
        return data

    def run(self, context: StageContext, work_dir: Path) -> StageResult:
        section = _section(context)
        if self.id == "load-gapfill-source":
            if context.config.workflow == "reference":
                gate = json.loads(
                    _dependency_path(context, "gate-beta2", "gate").read_text(
                        encoding="utf-8"
                    )
                )
                if gate.get("status") not in {"passed", "warning"}:
                    raise ValueError("β2 gate did not pass")
                source = _dependency_path(context, "export-beta2", "model")
                upstream = {
                    "workflow": "beta2",
                    "run": context.config.run.name,
                    "stage": "export-beta2",
                    "role": "model",
                    "run_dir": str(context.run_dir),
                    "stage_id": "export-beta2",
                    "artifact_checksum": sha256_file(source),
                    "beta2_gate": gate,
                }
            else:
                source = Path(str(section["input_model"]))
                upstream = {
                    "workflow": "gapfill",
                    "run": context.config.run.name,
                    "stage": "external-input",
                    "role": "external-model",
                    "path": str(source),
                    "external_input": True,
                }
            copied = work_dir / f"source{source.suffix.lower()}"
            shutil.copy2(source, copied)
            checksum = sha256_file(copied)
            provenance = {
                "schema_version": 1,
                "workflow": context.config.workflow,
                "source_model_checksum": checksum,
                "source_path": str(source),
                "external_input": context.config.workflow == "gapfill",
                "upstream": upstream,
                "software": _software(),
            }
            return StageResult(
                (
                    ("model", copied),
                    (
                        "provenance",
                        _dump(work_dir / "gapfill-source-provenance.json", provenance),
                    ),
                ),
                {
                    "source_model_checksum": checksum,
                    "external_input": provenance["external_input"],
                },
            )

        if self.id == "characterize-gapfill-baseline":
            model_path = _dependency_path(context, "load-gapfill-source", "model")
            model = _load_cobra_model(model_path)
            from thg_protocol.validation import validate_model

            profile = str(section["validation_profile"])
            validation = validate_model(model, profile)
            payload = {
                "schema_version": 1,
                "source_model_checksum": sha256_file(model_path),
                "validation_profile": profile,
                "validation_profile_version": 1,
                "software": _software(),
                "metrics": _safe_metrics(model),
                "validation": _as_error_status(validation),
                "tasks": _task_report(model, section),
            }
            return StageResult(
                (("baseline", _dump(work_dir / "gapfill-baseline.json", payload)),),
                payload["metrics"] if isinstance(payload["metrics"], Mapping) else {},
            )

        if self.id == "generate-gapfill-plan":
            from thg_protocol.gapfill import generate_gapfill_plan

            source = _dependency_path(context, "load-gapfill-source", "model")
            method = str(section["method"])
            parameters = {
                key: value
                for key, value in section.items()
                if key
                not in {
                    "method",
                    "validation_profile",
                    "task_suite",
                    "candidate_universe",
                    "external_input",
                    "input_model",
                }
            }
            plan = generate_gapfill_plan(
                _load_cobra_model(source),
                method=method,
                parameters=parameters,
                source_model_checksum=sha256_file(source),
            )
            external_checksums = {
                key: sha256_file(str(section[key]))
                for key in ("candidate_universe", "universal_model")
                if isinstance(section.get(key), str)
                and Path(str(section[key])).is_file()
            }
            plan["header"]["external_input_checksums"] = external_checksums
            plan_path = work_dir / "gapfill-plan.jsonl"
            _write_plan(plan_path, plan)
            report = _dump(
                work_dir / "gapfill-report.json",
                {
                    **(
                        plan.get("result", {})
                        if isinstance(plan.get("result"), Mapping)
                        else {}
                    ),
                    "source_model_checksum": plan["header"].get(
                        "source_model_checksum"
                    ),
                    "plan_header": plan["header"],
                },
            )
            summary = plan.get("header", {})
            if not isinstance(summary, Mapping):
                summary = {}
            return StageResult(
                (("plan", plan_path), ("report", report)),
                {
                    "status": summary.get("status"),
                    "proposals": summary.get("proposal_count", 0),
                },
            )

        if self.id == "apply-gapfill":
            from thg_protocol.analysis.model_signature import (
                diff_model_signatures,
                model_signature,
            )
            from thg_protocol.gapfill import apply_gapfill_plan
            from thg_protocol.io.models import save_json

            source_path = _dependency_path(context, "load-gapfill-source", "model")
            source = _load_cobra_model(source_path)
            plan = _plan_file(
                _dependency_path(context, "generate-gapfill-plan", "plan")
            )
            source_checksum = sha256_file(source_path)
            applied, ledger = apply_gapfill_plan(
                source, plan, source_model_checksum=source_checksum
            )
            before = model_signature(source)
            after = model_signature(applied)
            diff = diff_model_signatures(before, after)
            model_path = work_dir / "gapfilled-candidate.json"
            save_json(applied, model_path)
            result_checksum = sha256_file(model_path)
            for item in ledger:
                item["result_model_checksum"] = result_checksum
            ledger_path = work_dir / "gapfill-change-ledger.jsonl"
            ledger_path.write_text(
                "".join(json.dumps(item, sort_keys=True) + "\n" for item in ledger),
                encoding="utf-8",
            )
            return StageResult(
                (
                    ("model", model_path),
                    ("ledger", ledger_path),
                    ("diff", _dump(work_dir / "model-diff.json", diff)),
                    ("signature", _dump(work_dir / "model-signature.json", after)),
                ),
                {
                    "added_reactions": len(diff["added"].get("reactions", [])),
                    "clean_diff": _model_diff_is_clean(diff),
                },
            )

        if self.id == "validate-gapfill":
            from thg_protocol.validation import validate_model

            source_path = _dependency_path(context, "load-gapfill-source", "model")
            result_path = _dependency_path(context, "apply-gapfill", "model")
            source = _load_cobra_model(source_path)
            result = _load_cobra_model(result_path)
            profile = str(section["validation_profile"])
            validation = validate_model(
                result,
                profile,
                ledger_diff={
                    "passed": _model_diff_is_clean(
                        json.loads(
                            _dependency_path(
                                context, "apply-gapfill", "diff"
                            ).read_text(encoding="utf-8")
                        )
                    )
                },
            )
            before = _safe_metrics(source)
            after = _safe_metrics(result)
            deltas = {}
            if isinstance(before, Mapping) and isinstance(after, Mapping):
                for key in (
                    "reactions",
                    "metabolites",
                    "genes",
                    "blocked_reactions",
                    "dead_end_metabolites",
                    "network_components",
                    "largest_component_fraction",
                ):
                    old, new = before.get(key), after.get(key)
                    if isinstance(old, (int, float)) and isinstance(new, (int, float)):
                        deltas[key] = new - old
                    elif isinstance(old, list) and isinstance(new, list):
                        deltas[key] = {
                            "before": len(old),
                            "after": len(new),
                            "delta": len(new) - len(old),
                        }
            payload = {
                "schema": "thg.validation.report/v1",
                "schema_version": 1,
                "source_model_checksum": sha256_file(source_path),
                "result_model_checksum": sha256_file(result_path),
                "validation_profile": profile,
                "validation_profile_version": 1,
                "software": _software(),
                "before": before,
                "after": after,
                "metric_deltas": deltas,
                "validation": _as_error_status(validation),
                "tasks": _task_report(result, section),
                "solver": validation.get("solver", {}),
            }
            warnings = [
                str(item.get("id"))
                for item in validation.get("checks", [])
                if isinstance(item, Mapping)
                and item.get("passed") is False
                and item.get("release_blocking") is False
            ]
            if profile == "post-gapfill" and not section.get("task_suite"):
                warnings.append("metabolic-task-suite-not-requested")
            for metric in ("blocked_reactions", "dead_end_metabolites"):
                delta = payload["metric_deltas"].get(metric)
                if isinstance(delta, Mapping) and delta.get("delta", 0) > 0:
                    warnings.append(f"worsening-{metric}")
            payload["warnings"] = sorted(set(warnings))
            report = _dump(work_dir / "validation-report.json", payload)
            html = work_dir / "validation-report.html"
            html.write_text(
                "<html><body><pre>"
                + json.dumps(payload, indent=2, sort_keys=True, default=str)
                + "</pre></body></html>\n",
                encoding="utf-8",
            )
            summary = work_dir / "validation-summary.md"
            summary.write_text(
                "# Gapfill validation\n\n"
                + "\n".join(
                    f"- {key}: {value}"
                    for key, value in payload["metric_deltas"].items()
                )
                + "\n",
                encoding="utf-8",
            )
            return StageResult(
                (
                    ("validation", report),
                    ("validation-html", html),
                    ("validation-summary", summary),
                ),
                {"validation": payload},
            )

        if self.id == "gate-gapfill":
            plan = _plan_file(
                _dependency_path(context, "generate-gapfill-plan", "plan")
            )
            report = json.loads(
                _dependency_path(context, "generate-gapfill-plan", "report").read_text(
                    encoding="utf-8"
                )
            )
            validation = json.loads(
                _dependency_path(context, "validate-gapfill", "validation").read_text(
                    encoding="utf-8"
                )
            )
            diff = json.loads(
                _dependency_path(context, "apply-gapfill", "diff").read_text(
                    encoding="utf-8"
                )
            )
            ledger = [
                json.loads(line)
                for line in _dependency_path(context, "apply-gapfill", "ledger")
                .read_text(encoding="utf-8")
                .splitlines()
                if line.strip()
            ]
            blocking: list[str] = []
            warnings: list[str] = []
            status = str(report.get("status", "error"))
            if status == "partial":
                blocking.append("gapfill algorithm returned a partial result")
                warnings.append("partial result preserved as candidate")
            elif status != "solved":
                blocking.append("gapfill algorithm did not complete")
            validation_warnings = validation.get("warnings", [])
            if isinstance(validation_warnings, list):
                warnings.extend(str(item) for item in validation_warnings)
            proposals = {str(item.get("reaction_id")) for item in plan["proposals"]}
            ledger_ids = {str(item.get("reaction_id")) for item in ledger}
            if proposals != ledger_ids:
                blocking.append(
                    "plan and change ledger do not contain the same reactions"
                )
            if (
                not _model_diff_is_clean(diff)
                or set(diff.get("added", {}).get("reactions", [])) != proposals
            ):
                blocking.append("output model contains undeclared or changed objects")
            raw_validation = validation.get("validation", {})
            checks = (
                raw_validation.get("checks", [])
                if isinstance(raw_validation, Mapping)
                else []
            )
            if (
                not isinstance(raw_validation, Mapping)
                or raw_validation.get("passed") is False
            ):
                blocking.append("release-blocking validation failed")
            if any(
                isinstance(item, Mapping)
                and item.get("status") == "error"
                and item.get("release_blocking", True)
                for item in checks
            ):
                blocking.append("validation infrastructure error")
            tasks = validation.get("tasks", {})
            if (
                isinstance(tasks, Mapping)
                and section.get("task_suite")
                and tasks.get("passed") is not True
            ):
                blocking.append("configured metabolic tasks failed")
            if str(section.get("method")) == "milp" and not report.get("solver"):
                blocking.append("MILP solver metadata is missing")
            if str(section.get("method")) == "milp" and not {
                "strategy",
                "solver",
                "cobra_version",
            } <= set(report.get("solver", {})):
                blocking.append("MILP solver metadata is incomplete")
            external_checksums = plan["header"].get("external_input_checksums", {})
            if not isinstance(external_checksums, Mapping):
                blocking.append("external input checksums are missing")
            else:
                for key in ("candidate_universe", "universal_model"):
                    if isinstance(section.get(key), str) and not isinstance(
                        external_checksums.get(key), str
                    ):
                        blocking.append(f"{key} provenance is missing")
            for label in ("before", "after"):
                if isinstance(validation.get(label), Mapping) and validation[label].get(
                    "error"
                ):
                    blocking.append(f"{label} validation metrics errored")
            if blocking:
                gate_status = "blocked" if status in {"solved", "partial"} else "error"
            else:
                gate_status = "warning" if warnings else "passed"
            gate = {
                "schema_version": 1,
                "status": gate_status,
                "blocking_findings": blocking,
                "warnings": warnings,
                "source_model_checksum": plan["header"].get("source_model_checksum"),
                "method": section.get("method"),
                "software": _software(),
            }
            path = _dump(work_dir / "gapfill-gate.json", gate)
            return StageResult((("gate", path),), gate)

        if self.id == "export-gapfilled-reference":
            gate = json.loads(
                _dependency_path(context, "gate-gapfill", "gate").read_text(
                    encoding="utf-8"
                )
            )
            if gate.get("status") not in {"passed", "warning"} or gate.get(
                "blocking_findings"
            ):
                raise ValueError("gapfill gate does not allow release")
            from thg_protocol.io.models import save_json, save_sbml

            model = _load_cobra_model(
                _dependency_path(context, "apply-gapfill", "model")
            )
            json_model = work_dir / "thg-reference-gapfilled.json"
            save_json(model, json_model)
            xml_model = work_dir / "thg-reference-gapfilled.xml"
            save_sbml(model, xml_model)
            copies = {
                "gapfill-plan": (
                    _dependency_path(context, "generate-gapfill-plan", "plan"),
                    "gapfill-plan.jsonl",
                ),
                "gapfill-change-ledger": (
                    _dependency_path(context, "apply-gapfill", "ledger"),
                    "gapfill-change-ledger.jsonl",
                ),
                "gapfill-report": (
                    _dependency_path(context, "generate-gapfill-plan", "report"),
                    "gapfill-report.json",
                ),
                "gapfill-gate": (
                    _dependency_path(context, "gate-gapfill", "gate"),
                    "gapfill-gate.json",
                ),
                "validation-report": (
                    _dependency_path(context, "validate-gapfill", "validation"),
                    "validation-report.json",
                ),
                "validation-report-html": (
                    _dependency_path(context, "validate-gapfill", "validation-html"),
                    "validation-report.html",
                ),
                "validation-summary": (
                    _dependency_path(context, "validate-gapfill", "validation-summary"),
                    "validation-summary.md",
                ),
                "model-diff": (
                    _dependency_path(context, "apply-gapfill", "diff"),
                    "model-diff.json",
                ),
                "model-signature": (
                    _dependency_path(context, "apply-gapfill", "signature"),
                    "model-signature.json",
                ),
            }
            outputs: list[tuple[str, Path]] = [
                ("model", json_model),
                ("sbml", xml_model),
            ]
            for role, (source, name) in copies.items():
                destination = work_dir / name
                shutil.copy2(source, destination)
                outputs.append((role, destination))
            source_provenance = json.loads(
                _dependency_path(
                    context, "load-gapfill-source", "provenance"
                ).read_text(encoding="utf-8")
            )
            provenance = _dump(
                work_dir / "provenance.json",
                {
                    **source_provenance,
                    "release_gate": gate,
                    "result_model_checksum": sha256_file(json_model),
                    "source_model_checksum": gate.get("source_model_checksum"),
                },
            )
            summary = _dump(
                work_dir / "summary.json",
                {
                    "status": gate["status"],
                    "model": "thg-reference-gapfilled",
                    "source_model_checksum": gate.get("source_model_checksum"),
                    "result_model_checksum": sha256_file(json_model),
                    "proposals": len(
                        _plan_file(
                            _dependency_path(context, "generate-gapfill-plan", "plan")
                        )["proposals"]
                    ),
                },
            )
            outputs.extend((("provenance", provenance), ("summary", summary)))
            return StageResult(
                tuple(outputs), {"status": gate["status"], "model": str(json_model)}
            )

        raise ValueError(f"unknown gapfill stage: {self.id}")

    def validate(self, result: StageResult) -> None:
        if not result.outputs or any(not path.is_file() for _, path in result.outputs):
            raise ValueError(f"stage '{self.id}' produced incomplete artifacts")
        if self.id == "generate-gapfill-plan" and result.summary.get("status") not in {
            "solved",
            "partial",
        }:
            raise ValueError("gapfill algorithm failed")
        if self.id == "gate-gapfill" and result.summary.get("status") in {
            "blocked",
            "error",
        }:
            raise ValueError("gapfill release gate did not pass")


def gapfill_stages(*, reference: bool = False) -> tuple[GapfillStage, ...]:
    return (
        GapfillStage("load-gapfill-source", ("gate-beta2",) if reference else ()),
        GapfillStage("characterize-gapfill-baseline", ("load-gapfill-source",)),
        GapfillStage(
            "generate-gapfill-plan",
            ("load-gapfill-source", "characterize-gapfill-baseline"),
        ),
        GapfillStage("apply-gapfill", ("load-gapfill-source", "generate-gapfill-plan")),
        GapfillStage(
            "validate-gapfill",
            ("load-gapfill-source", "apply-gapfill", "characterize-gapfill-baseline"),
        ),
        GapfillStage(
            "gate-gapfill",
            ("generate-gapfill-plan", "apply-gapfill", "validate-gapfill"),
        ),
        GapfillStage(
            "export-gapfilled-reference",
            (
                "load-gapfill-source",
                "generate-gapfill-plan",
                "apply-gapfill",
                "validate-gapfill",
                "gate-gapfill",
            ),
        ),
    )

GAPFILL_WORKFLOW = WorkflowDefinition(
    "gapfill",
    gapfill_stages(),
    frozenset({"gapfill"}),
    "First-class standalone THG gapfill",
)

__all__ = [
    "Beta2GateStage", "GapfillStage", "GAPFILL_WORKFLOW", "gapfill_stages"
]
