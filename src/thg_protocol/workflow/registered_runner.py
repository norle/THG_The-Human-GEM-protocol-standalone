"""Runner for dynamically registered format-2 workflow DAGs."""

from __future__ import annotations

import os
import shutil
import traceback
from collections.abc import Mapping
from pathlib import Path

from .config import (
    ConfigError,
    WorkflowConfig,
    load_snapshot,
    load_workflow_config,
    workflow_config_to_dict,
    write_workflow_snapshot,
)
from .hashing import artifact_record, sha256_json, verify_artifact
from .lock import acquire_run_lock
from .manifest import (
    new_workflow_manifest,
    utc_now,
    write_manifest_atomic,
)
from .registry import WorkflowRegistryError, get_workflow
from .stages import Stage, StageContext


class RegisteredWorkflowError(RuntimeError):
    """Raised when a format-2 workflow cannot be executed."""


def _descendants(stages: tuple[Stage, ...], stage_id: str) -> set[str]:
    result: set[str] = set()
    changed = True
    while changed:
        changed = False
        for stage in stages:
            if (
                stage.id != stage_id
                and stage.id not in result
                and any(
                    dependency == stage_id or dependency in result
                    for dependency in stage.dependencies
                )
            ):
                result.add(stage.id)
                changed = True
    return result


def _entry(manifest: dict[str, object], stage_id: str) -> dict[str, object]:
    steps = manifest.get("steps")
    if not isinstance(steps, dict) or not isinstance(steps.get(stage_id), dict):
        raise RegisteredWorkflowError(f"manifest has no step '{stage_id}'")
    return steps[stage_id]


def _write(run_dir: Path, manifest: dict[str, object]) -> None:
    manifest["updated_at"] = utc_now()
    write_manifest_atomic(run_dir, manifest)


def _invalidate(
    manifest: dict[str, object], stages: tuple[Stage, ...], stage_id: str
) -> None:
    for affected in {stage_id} | _descendants(stages, stage_id):
        _entry(manifest, affected).update(
            status="pending",
            fingerprint=None,
            started_at=None,
            finished_at=None,
            outputs=[],
            error=None,
            summary={},
        )


def _artifacts_valid(entry: Mapping[str, object], run_dir: Path) -> bool:
    outputs = entry.get("outputs")
    return (
        isinstance(outputs, list)
        and bool(outputs)
        and all(
            isinstance(item, Mapping) and verify_artifact(item, run_dir)
            for item in outputs
        )
    )


def _next_attempt(run_dir: Path, stage_id: str, entry: Mapping[str, object]) -> int:
    attempt = entry.get("attempt", 0)
    number = int(attempt) + 1 if isinstance(attempt, int) else 1
    for parent in (run_dir / "artifacts" / stage_id, run_dir / "failed" / stage_id):
        if parent.is_dir():
            for candidate in parent.iterdir():
                if candidate.name.startswith("attempt-"):
                    try:
                        number = max(number, int(candidate.name[8:]) + 1)
                    except ValueError:
                        pass
    return number


def _error(error: BaseException) -> str:
    return f"{type(error).__name__}: {str(error).strip().replace(chr(10), ' ')}"[:1000]


def _execute(
    config: WorkflowConfig,
    run_dir: Path,
    manifest: dict[str, object],
    stages: tuple[Stage, ...],
    *,
    force_step: str | None = None,
) -> Path:
    if force_step is not None:
        if force_step not in {stage.id for stage in stages}:
            raise RegisteredWorkflowError(f"unknown stage: {force_step}")
        _invalidate(manifest, stages, force_step)
    for stage in stages:
        entry = _entry(manifest, stage.id)
        if entry["status"] == "running":
            entry.update(
                status="interrupted",
                finished_at=utc_now(),
                outputs=[],
                error="process stopped while stage was running",
            )
    manifest["overall_status"] = "running"
    _write(run_dir, manifest)
    for stage in stages:
        entry = _entry(manifest, stage.id)
        if not stage.enabled(config):
            entry.update(
                status="skipped",
                fingerprint=None,
                started_at=None,
                finished_at=utc_now(),
                outputs=[],
                error=None,
                summary={},
            )
            _write(run_dir, manifest)
            continue
        context = StageContext(config, run_dir, manifest)
        fingerprint = sha256_json(stage.fingerprint_data(context))
        if (
            entry["status"] == "completed"
            and entry.get("fingerprint") == fingerprint
            and _artifacts_valid(entry, run_dir)
        ):
            continue
        _invalidate(manifest, stages, stage.id)
        entry = _entry(manifest, stage.id)
        attempt = _next_attempt(run_dir, stage.id, entry)
        temporary = run_dir / ".tmp" / f"{stage.id}-attempt-{attempt:04d}"
        final = run_dir / "artifacts" / stage.id / f"attempt-{attempt:04d}"
        log_path = run_dir / "logs" / f"{stage.id}-attempt-{attempt:04d}.log"
        shutil.rmtree(temporary, ignore_errors=True)
        temporary.mkdir(parents=True, exist_ok=True)
        entry.update(
            status="running",
            attempt=attempt,
            fingerprint=fingerprint,
            started_at=utc_now(),
            finished_at=None,
            outputs=[],
            error=None,
            summary={},
        )
        _write(run_dir, manifest)
        try:
            result = stage.run(
                StageContext(config, run_dir, manifest, log_path), temporary
            )
            stage.validate(result)
            relative_paths = []
            for _, path in result.outputs:
                resolved = path.resolve()
                try:
                    relative_paths.append(resolved.relative_to(temporary.resolve()))
                except ValueError as error:
                    raise RegisteredWorkflowError(
                        f"stage '{stage.id}' returned an output outside its "
                        "work directory"
                    ) from error
                if not resolved.is_file():
                    raise RegisteredWorkflowError(
                        f"stage '{stage.id}' returned a non-file output"
                    )
            if final.exists():
                raise RegisteredWorkflowError(
                    f"refusing to overwrite existing attempt directory: {final}"
                )
            final.parent.mkdir(parents=True, exist_ok=True)
            os.replace(temporary, final)
            outputs = [
                artifact_record(role, final / relative, run_dir)
                for (role, _), relative in zip(
                    result.outputs, relative_paths, strict=True
                )
            ]
            entry.update(
                status="completed",
                finished_at=utc_now(),
                outputs=outputs,
                error=None,
                summary=dict(result.summary),
            )
            _write(run_dir, manifest)
        except KeyboardInterrupt:
            if temporary.exists():
                failed = run_dir / "failed" / stage.id / f"attempt-{attempt:04d}"
                failed.parent.mkdir(parents=True, exist_ok=True)
                os.replace(temporary, failed)
            entry.update(
                status="interrupted",
                finished_at=utc_now(),
                outputs=[],
                error="interrupted by user",
            )
            (log_path.parent).mkdir(parents=True, exist_ok=True)
            log_path.write_text(traceback.format_exc(), encoding="utf-8")
            manifest["overall_status"] = "interrupted"
            _write(run_dir, manifest)
            raise
        except Exception as error:
            if temporary.exists():
                failed = run_dir / "failed" / stage.id / f"attempt-{attempt:04d}"
                failed.parent.mkdir(parents=True, exist_ok=True)
                os.replace(temporary, failed)
            entry.update(
                status="failed", finished_at=utc_now(), outputs=[], error=_error(error)
            )
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_path.write_text(traceback.format_exc(), encoding="utf-8")
            manifest["overall_status"] = "failed"
            _write(run_dir, manifest)
            raise RegisteredWorkflowError(
                f"stage '{stage.id}' failed: {_error(error)}"
            ) from error
    manifest["overall_status"] = "completed"
    _write(run_dir, manifest)
    return run_dir


def start_registered(config_path: str | Path) -> Path:
    config = load_workflow_config(config_path)
    try:
        definition = get_workflow(config.workflow)
    except WorkflowRegistryError as error:
        raise ConfigError(str(error)) from error
    run_dir = config.run.output_dir
    section_key = "validation" if config.workflow == "validate" else config.workflow
    scientific = (
        config.workflow in {"beta1", "beta2", "validate"}
        and isinstance(config.sections.get(section_key), Mapping)
        and (
            isinstance(config.sections[section_key].get("input_model"), str)
            or isinstance(config.sections[section_key].get("upstream"), Mapping)
        )
    )
    stages = definition.stages_for(scientific=scientific)
    if run_dir.exists() and not run_dir.is_dir():
        raise ConfigError(f"run output path is not a directory: {run_dir}")
    if run_dir.exists() and any(run_dir.iterdir()):
        raise ConfigError("run directory is nonempty; choose a new output directory")
    run_dir.mkdir(parents=True, exist_ok=True)
    with acquire_run_lock(run_dir):
        write_workflow_snapshot(config, run_dir)
        manifest = new_workflow_manifest(config, stages)
        _write(run_dir, manifest)
        return _execute(config, run_dir, manifest, stages)


def resume_registered(run_dir: str | Path, *, force_step: str | None = None) -> Path:
    directory = Path(run_dir).resolve()
    with acquire_run_lock(directory):
        config = load_snapshot(directory)
        if not isinstance(config, WorkflowConfig):
            raise ConfigError("run is not a format-2 registered workflow")
        try:
            definition = get_workflow(config.workflow)
        except WorkflowRegistryError as error:
            raise ConfigError(str(error)) from error
        from .manifest import load_workflow_manifest

        manifest = load_workflow_manifest(directory)
        if manifest.get("config_sha256") != sha256_json(
            workflow_config_to_dict(config)
        ):
            raise RegisteredWorkflowError(
                "manifest config_sha256 does not match config snapshot"
            )
        if manifest.get("workflow") != config.workflow:
            raise RegisteredWorkflowError(
                "manifest workflow does not match config snapshot"
            )
        steps = manifest.get("steps")
        if not isinstance(steps, Mapping):
            raise RegisteredWorkflowError("manifest has no workflow steps")
        stage_ids = {str(stage_id) for stage_id in steps}
        if stage_ids == set(definition.scientific_stage_ids):
            stages = definition.scientific_stages
        elif stage_ids == set(definition.stage_ids):
            stages = definition.stages
        else:
            raise RegisteredWorkflowError(
                f"manifest stages do not match workflow '{config.workflow}'"
            )
        return _execute(config, directory, manifest, stages, force_step=force_step)


def is_registered_config(path: str | Path) -> bool:
    try:
        payload = __import__("json").loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return isinstance(payload, dict) and payload.get("format_version") == 2
