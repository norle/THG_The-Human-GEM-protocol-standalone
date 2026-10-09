"""Registered, proposal-first gapfill workflow stages."""

from __future__ import annotations

import json
import platform
import shutil
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from thg_protocol.io.models import load_model as _load_cobra_model
from thg_protocol.runtime.hashing import sha256_file, sha256_json, verify_artifact
from thg_protocol.runtime.stage import (
    StageContext,
    StageResult,
    dependency_hashes,
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
    from thg_protocol.raven_tasks import load_task_input
    from thg_protocol.tasks import run_task_suite

    suite = load_task_input(task_suite, model, mapping=section.get("task_mapping"))
    return run_task_suite(model, suite)


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


def _model_diff_is_clean(
    diff: Mapping[str, object], removed_reactions: set[str] | None = None
) -> bool:
    allowed = removed_reactions or set()
    if diff.get("model", {}).get("changed", False):
        return False
    for kind in ("removed", "changed"):
        for collection, values in diff.get(kind, {}).items():
            if kind == "removed" and collection == "reactions":
                if set(values) != allowed:
                    return False
            elif kind == "changed" and collection == "groups":
                for item in values:
                    expected = dict(item["a"])
                    expected["members"] = [
                        x for x in expected["members"] if x not in allowed
                    ]
                    if expected != item["b"]:
                        return False
            elif values:
                return False
    return True


class Beta2GateStage:
    implementation_version = 3
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
        gate = beta2_release_gate(
            model_path.parent,
            # Reference construction passes a β1 candidate internally; the
            # public β1 release gate belongs at the promotion boundary.
            require_beta1_release=context.config.workflow != "reference",
        )
        reasons = list(gate.get("reasons", []))
        locations = model_path.parent / "gene-location-evidence.jsonl"
        if context.config.workflow == "reference" and (
            not locations.is_file() or not locations.read_text(encoding="utf-8").strip()
        ):
            # Without gene locations β2 cannot localize anything, so a passing
            # gate would hand gapfill an unchanged β1 model.
            reasons.append("β2 found no gene-location evidence")
        passed = bool(gate.get("passed")) and not reasons
        result = {
            "schema_version": 1,
            "status": "passed" if passed else "blocked",
            "passed": passed,
            "reasons": reasons,
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


# Sink-MILP phases, each its own resumable stage; skipped for other methods.
_PTR_STAGES = {
    "generate-gapfill-candidates",
    "select-gapfill-connectors",
    "compute-gapfill-coverage",
}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _write_jsonl(path: Path, items: list[Mapping[str, object]]) -> Path:
    path.write_text(
        "".join(json.dumps(item, sort_keys=True) + "\n" for item in items),
        encoding="utf-8",
    )
    return path


def _ptr_candidates(context: StageContext) -> list[Any]:
    from thg_protocol.gapfill.ptr import PtrCandidate

    path = _dependency_path(context, "generate-gapfill-candidates", "candidates")
    return [PtrCandidate.from_dict(item) for item in _read_jsonl(path)]


def _ptr_connectors(context: StageContext) -> list[Any]:
    from thg_protocol.gapfill.ptr import PtrCandidate

    path = _dependency_path(context, "select-gapfill-connectors", "connectors")
    return [PtrCandidate.from_dict(item) for item in _read_jsonl(path)]


def _coverage_lines(path: Path) -> tuple[str | None, list[dict[str, Any]]]:
    """Header fingerprint and component lines; a torn last line is dropped."""
    fingerprint = None
    lines = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if "fingerprint" in item:
            fingerprint = item["fingerprint"]
        else:
            lines.append(item)
    return fingerprint, lines


def _parameters(section: Mapping[str, object]) -> dict[str, Any]:
    """Algorithm parameters: the gapfill section without workflow-only keys."""
    return {
        key: value
        for key, value in section.items()
        if key
        not in {
            "method",
            "validation_profile",
            "task_suite",
            "task_mapping",
            "candidate_universe",
            "external_input",
            "input_model",
            "run_loop_detection",
            "remove_infeasible_loops",
        }
    }


class GapfillStage:
    implementation_version = 3

    def __init__(self, stage_id: str, dependencies: tuple[str, ...] = ()) -> None:
        self.id = stage_id
        self.dependencies = dependencies
        if stage_id == "characterize-gapfill-baseline":
            self.implementation_version = 4
        elif stage_id == "validate-gapfill":
            self.implementation_version = 6
        elif stage_id == "gate-gapfill":
            self.implementation_version = 3
        elif stage_id == "generate-gapfill-plan":
            self.implementation_version = 5
        elif stage_id in _PTR_STAGES:
            self.implementation_version = 2

    def enabled(self, config: Any) -> bool:
        if self.id not in _PTR_STAGES:
            return True
        section = config.sections.get("gapfill", {})
        return isinstance(section, Mapping) and section.get("method") == "sink-milp"

    def fingerprint_data(self, context: StageContext) -> Mapping[str, object]:
        section = _section(context)
        data: dict[str, object] = {
            "stage": self.id,
            "implementation_version": self.implementation_version,
            "dependencies": (
                dependency_hashes(context, self.dependencies)
                if self.dependencies
                else {}
            ),
        }
        if self.id == "load-gapfill-source":
            data["workflow"] = context.config.workflow
            data["input_sha256"] = _hash(section.get("input_model"))
            data["external_input"] = section.get("external_input")
        elif self.id == "generate-gapfill-plan":
            data["algorithm"] = {
                key: value
                for key, value in section.items()
                if key not in {"validation_profile", "task_suite", "task_mapping"}
            }
            data["candidate_universe_sha256"] = _hash(section.get("candidate_universe"))
            data["universal_model_sha256"] = _hash(section.get("universal_model"))
        elif self.id == "generate-gapfill-candidates":
            data["allowed_connections"] = section.get("allowed_connections")
            data["candidate_types"] = section.get("candidate_types")
        elif self.id == "compute-gapfill-coverage":
            data["min_component_size"] = section.get("min_component_size")
        elif self.id == "characterize-gapfill-baseline":
            data["validation_profile"] = section.get("validation_profile")
            data["run_loop_detection"] = section.get("run_loop_detection", True)
            data["task_suite_sha256"] = _hash(section.get("task_suite"))
            data["task_mapping_sha256"] = _hash(section.get("task_mapping"))
        elif self.id in {
            "apply-gapfill",
            "validate-gapfill",
            "gate-gapfill",
            "export-gapfilled-reference",
        }:
            data["validation_profile"] = section.get("validation_profile")
            data["run_loop_detection"] = section.get("run_loop_detection", True)
            data["remove_infeasible_loops"] = section.get(
                "remove_infeasible_loops", False
            )
            data["task_suite_sha256"] = _hash(section.get("task_suite"))
            data["task_mapping_sha256"] = _hash(section.get("task_mapping"))
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
                source_stage = "integrate-human-database"
                integrated = context.manifest.get("steps", {}).get(source_stage, {})
                if (
                    not isinstance(integrated, Mapping)
                    or integrated.get("status") != "completed"
                ):
                    source_stage = "export-beta2"
                source = _dependency_path(context, source_stage, "model")
                upstream = {
                    "workflow": "beta2",
                    "run": context.config.run.name,
                    "stage": source_stage,
                    "role": "model",
                    "run_dir": str(context.run_dir),
                    "stage_id": source_stage,
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
            validation = validate_model(
                model,
                profile,
                run_loop_detection=section.get("run_loop_detection", True),
            )
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

        if self.id == "generate-gapfill-candidates":
            from thg_protocol.gapfill.core import _resolved_parameters
            from thg_protocol.gapfill.ptr import (
                generate_ptr_candidates,
                network_components,
            )

            parameters = _resolved_parameters("sink-milp", _parameters(section))
            model = _load_cobra_model(
                _dependency_path(context, "load-gapfill-source", "model")
            )
            components = network_components(model)
            candidates = generate_ptr_candidates(
                model,
                parameters["allowed_connections"],
                parameters["candidate_types"],
                components,
            )
            return StageResult(
                (
                    (
                        "candidates",
                        _write_jsonl(
                            work_dir / "ptr-candidates.jsonl",
                            [item.to_dict() for item in candidates],
                        ),
                    ),
                    (
                        "components",
                        _dump(
                            work_dir / "ptr-components.json",
                            {
                                "schema_version": 1,
                                "of": components.of,
                                "sizes": {
                                    str(key): value
                                    for key, value in components.sizes.items()
                                },
                            },
                        ),
                    ),
                ),
                {
                    "candidates": len(candidates),
                    "already_present": sum(item.present for item in candidates),
                    "components": len(components.sizes),
                },
            )

        if self.id == "select-gapfill-connectors":
            from thg_protocol.gapfill.ptr import select_connectors

            connectors = select_connectors(_ptr_candidates(context))
            return StageResult(
                (
                    (
                        "connectors",
                        _write_jsonl(
                            work_dir / "ptr-connectors.jsonl",
                            [item.to_dict() for item in connectors],
                        ),
                    ),
                ),
                {"connectors": len(connectors)},
            )

        if self.id == "compute-gapfill-coverage":
            from thg_protocol.gapfill import ptr
            from thg_protocol.gapfill.core import _add_candidate, _resolved_parameters

            parameters = _resolved_parameters("sink-milp", _parameters(section))
            model = _load_cobra_model(
                _dependency_path(context, "load-gapfill-source", "model")
            )
            candidates = _ptr_candidates(context)
            fingerprint = sha256_json(self.fingerprint_data(context))
            path = work_dir / "ptr-coverage.jsonl"
            if ptr.ptr_collisions(model, candidates):
                # Coverage on a model whose connectors cannot all be added is
                # wasted; generate-gapfill-plan reports the collision as failed.
                path.write_text(
                    json.dumps({"fingerprint": fingerprint}) + "\n", encoding="utf-8"
                )
                return StageResult(
                    (("coverage", path),),
                    {"components": 0, "skipped": "reaction-id-collision"},
                )
            for connector in _ptr_connectors(context):
                _add_candidate(model, connector.as_gapfill_candidate(phase=2))
            stored = json.loads(
                _dependency_path(
                    context, "generate-gapfill-candidates", "components"
                ).read_text(encoding="utf-8")
            )
            components = ptr.Components(
                stored["of"],
                {int(key): value for key, value in stored["sizes"].items()},
            )
            done = {}
            # A failed or interrupted attempt keeps its finished components: in
            # failed/ after an exception, still in .tmp/ after a hard kill.
            previous_attempts = [
                *(context.run_dir / "failed" / self.id).glob(
                    "attempt-*/ptr-coverage.jsonl"
                ),
                *(context.run_dir / ".tmp").glob(
                    f"{self.id}-attempt-*/ptr-coverage.jsonl"
                ),
            ]
            for attempt in sorted(
                (item for item in previous_attempts if item.parent != work_dir),
                key=lambda item: item.parent.name[-4:],
            ):
                previous, lines = _coverage_lines(attempt)
                if previous == fingerprint:
                    for line in lines:
                        entry = ptr.ComponentCoverage.from_dict(line)
                        done[entry.component] = entry
            with path.open("w", encoding="utf-8") as handle:
                handle.write(json.dumps({"fingerprint": fingerprint}) + "\n")
                for entry in done.values():
                    handle.write(json.dumps(entry.to_dict(), sort_keys=True) + "\n")
                handle.flush()

                def checkpoint(entry: Any) -> None:
                    handle.write(json.dumps(entry.to_dict(), sort_keys=True) + "\n")
                    handle.flush()

                coverage = ptr.compute_coverage(
                    model,
                    candidates,
                    components,
                    min_component_size=parameters["min_component_size"],
                    done=done,
                    on_component=checkpoint,
                )
            return StageResult(
                (("coverage", path),),
                {
                    "components": len(coverage),
                    "reused_components": len(done),
                    "targets": sum(len(item.targets) for item in coverage),
                    "sink_only": sum(len(item.sink_only) for item in coverage),
                },
            )

        if self.id == "generate-gapfill-plan":
            from thg_protocol.gapfill import generate_gapfill_plan

            source = _dependency_path(context, "load-gapfill-source", "model")
            method = str(section["method"])
            parameters = _parameters(section)
            model = _load_cobra_model(source)
            result = None
            if method == "sink-milp":
                from thg_protocol.gapfill.core import _error_result
                from thg_protocol.gapfill.ptr import ComponentCoverage, run_sink_milp

                _, lines = _coverage_lines(
                    _dependency_path(context, "compute-gapfill-coverage", "coverage")
                )
                try:
                    result = run_sink_milp(
                        model,
                        parameters,
                        candidates=_ptr_candidates(context),
                        connectors=_ptr_connectors(context),
                        coverage=[ComponentCoverage.from_dict(line) for line in lines],
                    )
                except Exception as error:
                    # As gapfill_model: a solver error becomes a failed plan.
                    result = _error_result(model, method, parameters, error)
            plan = generate_gapfill_plan(
                model,
                method=method,
                parameters=parameters,
                source_model_checksum=sha256_file(source),
                result=result,
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
            loop_report = {"status": "not-requested", "reactions": []}
            if section.get("remove_infeasible_loops", False):
                from thg_protocol.analysis.compaction import remove_infeasible_loops

                applied, loop_report, loop_ledger = remove_infeasible_loops(
                    applied, stage=self.id
                )
                for item in loop_ledger:
                    item["reaction_id"] = item["object_id"]
                    item["source_model_checksum"] = source_checksum
                ledger.extend(loop_ledger)
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
                    (
                        "loop-removal",
                        _dump(work_dir / "loop-removal.json", loop_report),
                    ),
                ),
                {
                    "added_reactions": len(diff["added"].get("reactions", [])),
                    "clean_diff": _model_diff_is_clean(
                        diff,
                        set(loop_report["reactions"])
                        & {rxn.id for rxn in source.reactions},
                    ),
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
                run_loop_detection=section.get("run_loop_detection", True),
                propose_fixes=True,
                ledger_diff={
                    "passed": _model_diff_is_clean(
                        json.loads(
                            _dependency_path(
                                context, "apply-gapfill", "diff"
                            ).read_text(encoding="utf-8")
                        ),
                        {
                            item["object_id"]
                            for item in map(
                                json.loads,
                                _dependency_path(context, "apply-gapfill", "ledger")
                                .read_text(encoding="utf-8")
                                .splitlines(),
                            )
                            if item.get("operation") == "remove-reaction"
                            and source.reactions.has_id(item["object_id"])
                        },
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
                "loop_removal": json.loads(
                    _dependency_path(
                        context, "apply-gapfill", "loop-removal"
                    ).read_text()
                ),
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
            from thg_protocol.validation_report import (
                render_validation_html,
                render_validation_summary,
            )

            html = work_dir / "validation-report.html"
            html.write_text(
                render_validation_html(payload),
                encoding="utf-8",
            )
            summary = work_dir / "validation-summary.md"
            summary.write_text(
                render_validation_summary(payload),
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
            before_metrics = report.get("before_metrics")
            if (
                context.config.workflow == "reference"
                and not report.get("candidate_coverage")
                and isinstance(before_metrics, Mapping)
                and before_metrics.get("dead_ends", 0) > 0
            ):
                blocking.append(
                    "no candidate reactions were available for the remaining "
                    "dead ends; check allowed_connections"
                )
            validation_warnings = validation.get("warnings", [])
            if isinstance(validation_warnings, list):
                warnings.extend(str(item) for item in validation_warnings)
            proposals = {str(item.get("reaction_id")) for item in plan["proposals"]}
            ledger_ids = {
                str(item.get("reaction_id"))
                for item in ledger
                if item.get("operation") == "add-reaction"
            }
            removed = {
                str(item.get("object_id"))
                for item in ledger
                if item.get("operation") == "remove-reaction"
            }
            loop_report = json.loads(
                _dependency_path(context, "apply-gapfill", "loop-removal").read_text()
            )
            if removed != set(loop_report["reactions"]) or (
                removed and not section.get("remove_infeasible_loops", False)
            ):
                blocking.append("loop removals do not match the requested analysis")
            if proposals != ledger_ids:
                blocking.append(
                    "plan and change ledger do not contain the same reactions"
                )
            if (
                not _model_diff_is_clean(diff, removed - proposals)
                or set(diff.get("added", {}).get("reactions", []))
                != proposals - removed
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
                "loop-removal": (
                    _dependency_path(context, "apply-gapfill", "loop-removal"),
                    "loop-removal.json",
                ),
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
        GapfillStage(
            "load-gapfill-source",
            ("gate-beta2", "integrate-human-database") if reference else (),
        ),
        GapfillStage("characterize-gapfill-baseline", ("load-gapfill-source",)),
        GapfillStage("generate-gapfill-candidates", ("load-gapfill-source",)),
        GapfillStage("select-gapfill-connectors", ("generate-gapfill-candidates",)),
        GapfillStage(
            "compute-gapfill-coverage",
            (
                "load-gapfill-source",
                "generate-gapfill-candidates",
                "select-gapfill-connectors",
            ),
        ),
        GapfillStage(
            "generate-gapfill-plan",
            (
                "load-gapfill-source",
                "characterize-gapfill-baseline",
                "generate-gapfill-candidates",
                "select-gapfill-connectors",
                "compute-gapfill-coverage",
            ),
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

__all__ = ["Beta2GateStage", "GapfillStage", "GAPFILL_WORKFLOW", "gapfill_stages"]
