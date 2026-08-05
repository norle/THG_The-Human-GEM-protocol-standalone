"""Resumable, checksum-verified execution of the version 1 workflow DAG."""

from __future__ import annotations

import os
import shutil
import traceback
from collections.abc import Mapping
from pathlib import Path

from .config import (
    ConfigError,
    RunConfig,
    config_to_dict,
    load_snapshot,
    load_start_config,
    write_snapshot,
)
from .hashing import artifact_record, sha256_json, verify_artifact
from .lock import acquire_run_lock
from .manifest import (
    load_manifest,
    new_manifest,
    utc_now,
    write_manifest_atomic,
)
from .stages import STAGE_OBJECTS, Stage, StageContext, validate_stage_order


class WorkflowError(RuntimeError):
    """Base error for workflow execution failures."""


class StageFailedError(WorkflowError):
    """Raised after a stage failure has been persisted to the manifest."""


def _descendants(stages: tuple[Stage, ...], stage_id: str) -> set[str]:
    descendants: set[str] = set()
    changed = True
    while changed:
        changed = False
        for stage in stages:
            if stage.id == stage_id or any(
                dep == stage_id or dep in descendants for dep in stage.dependencies
            ):
                if stage.id != stage_id and stage.id not in descendants:
                    descendants.add(stage.id)
                    changed = True
    return descendants


def _touch_manifest(manifest: dict[str, object]) -> None:
    manifest["updated_at"] = utc_now()


def _write(run_dir: Path, manifest: dict[str, object]) -> None:
    _touch_manifest(manifest)
    write_manifest_atomic(run_dir, manifest)


def _stage_entry(manifest: dict[str, object], stage_id: str) -> dict[str, object]:
    steps = manifest.get("steps")
    if not isinstance(steps, dict) or not isinstance(steps.get(stage_id), dict):
        raise WorkflowError(f"manifest has no step '{stage_id}'")
    return steps[stage_id]


def _invalidate(
    manifest: dict[str, object], stages: tuple[Stage, ...], stage_id: str
) -> None:
    affected = {stage_id} | _descendants(stages, stage_id)
    for affected_id in affected:
        entry = _stage_entry(manifest, affected_id)
        entry.update(
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
            isinstance(record, Mapping) and verify_artifact(record, run_dir)
            for record in outputs
        )
    )


def _next_attempt(entry: Mapping[str, object]) -> int:
    attempt = entry.get("attempt", 0)
    return int(attempt) + 1 if isinstance(attempt, int) else 1


def _next_attempt_for(run_dir: Path, stage_id: str, entry: Mapping[str, object]) -> int:
    attempt = _next_attempt(entry)
    for parent in (run_dir / "artifacts" / stage_id, run_dir / "failed" / stage_id):
        if not parent.is_dir():
            continue
        for candidate in parent.iterdir():
            if not candidate.name.startswith("attempt-"):
                continue
            try:
                attempt = max(attempt, int(candidate.name.removeprefix("attempt-")) + 1)
            except ValueError:
                continue
    return attempt


def _concise_error(error: BaseException) -> str:
    message = str(error).strip().replace("\n", " ")
    return f"{type(error).__name__}: {message}"[:1000]


def _write_exception_log(path: Path, error: BaseException) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(traceback.format_exc(), encoding="utf-8")


def _execute(
    config: RunConfig,
    run_dir: Path,
    manifest: dict[str, object],
    *,
    stages: tuple[Stage, ...] = STAGE_OBJECTS,
    force_step: str | None = None,
) -> Path:
    validate_stage_order(stages)
    if force_step is not None and force_step not in {stage.id for stage in stages}:
        raise WorkflowError(f"unknown stage: {force_step}")

    if force_step is not None:
        _invalidate(manifest, stages, force_step)
    for stage in stages:
        entry = _stage_entry(manifest, stage.id)
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
        entry = _stage_entry(manifest, stage.id)
        if not stage.enabled(config):
            if entry["status"] != "skipped" or entry.get("outputs"):
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

        fingerprint = sha256_json(
            stage.fingerprint_data(StageContext(config, run_dir, manifest))
        )
        valid_completed = (
            entry["status"] == "completed"
            and entry.get("fingerprint") == fingerprint
            and _artifacts_valid(entry, run_dir)
        )
        if valid_completed:
            continue

        _invalidate(manifest, stages, stage.id)
        entry = _stage_entry(manifest, stage.id)
        attempt = _next_attempt_for(run_dir, stage.id, entry)
        temporary = run_dir / ".tmp" / f"{stage.id}-attempt-{attempt:04d}"
        final = run_dir / "artifacts" / stage.id / f"attempt-{attempt:04d}"
        log_path = run_dir / "logs" / f"{stage.id}-attempt-{attempt:04d}.log"
        temporary.parent.mkdir(parents=True, exist_ok=True)
        shutil.rmtree(temporary, ignore_errors=True)
        temporary.mkdir(parents=True)
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
            output_paths = []
            for _, path in result.outputs:
                resolved = path.resolve()
                try:
                    relative = resolved.relative_to(temporary.resolve())
                except ValueError as error:
                    raise WorkflowError(
                        f"stage '{stage.id}' returned an output outside "
                        "its work directory"
                    ) from error
                if not resolved.is_file():
                    raise WorkflowError(
                        f"stage '{stage.id}' returned a non-file output"
                    )
                output_paths.append(relative)
            if final.exists():
                raise WorkflowError(
                    f"refusing to overwrite existing attempt directory: {final}"
                )
            final.parent.mkdir(parents=True, exist_ok=True)
            os.replace(temporary, final)
            records = [
                artifact_record(role, final / relative, run_dir)
                for (role, _), relative in zip(
                    result.outputs, output_paths, strict=True
                )
            ]
            entry.update(
                status="completed",
                finished_at=utc_now(),
                outputs=records,
                error=None,
                summary=dict(result.summary),
            )
            _write(run_dir, manifest)
        except KeyboardInterrupt as error:
            if temporary.exists():
                failed = run_dir / "failed" / stage.id / f"attempt-{attempt:04d}"
                failed.parent.mkdir(parents=True, exist_ok=True)
                if not failed.exists():
                    os.replace(temporary, failed)
            entry.update(
                status="interrupted",
                finished_at=utc_now(),
                outputs=[],
                error="interrupted by user",
            )
            _write_exception_log(log_path, error)
            manifest["overall_status"] = "interrupted"
            _write(run_dir, manifest)
            raise
        except Exception as error:
            if temporary.exists():
                failed = run_dir / "failed" / stage.id / f"attempt-{attempt:04d}"
                failed.parent.mkdir(parents=True, exist_ok=True)
                if not failed.exists():
                    os.replace(temporary, failed)
            entry.update(
                status="failed",
                finished_at=utc_now(),
                outputs=[],
                error=_concise_error(error),
            )
            _write_exception_log(log_path, error)
            manifest["overall_status"] = "failed"
            _write(run_dir, manifest)
            raise StageFailedError(
                f"stage '{stage.id}' failed: {_concise_error(error)}"
            ) from error

    manifest["overall_status"] = "completed"
    _write(run_dir, manifest)
    return run_dir


def start(config_path: str | Path) -> Path:
    config = load_start_config(config_path)
    run_dir = config.run.output_dir
    if run_dir.exists() and not run_dir.is_dir():
        raise ConfigError(f"run output path is not a directory: {run_dir}")
    if (run_dir / "manifest.json").exists():
        raise ConfigError(
            f"run directory already contains a manifest; use resume: {run_dir}"
        )
    if run_dir.exists() and any(run_dir.iterdir()):
        raise ConfigError(
            "run directory is nonempty without a manifest; choose a new output "
            "directory or remove unrelated files explicitly"
        )
    run_dir.mkdir(parents=True, exist_ok=True)
    with acquire_run_lock(run_dir):
        write_snapshot(config, run_dir)
        manifest = new_manifest(config)
        _write(run_dir, manifest)
        return _execute(config, run_dir, manifest)


def resume(run_dir: str | Path, *, force_step: str | None = None) -> Path:
    directory = Path(run_dir).resolve()
    with acquire_run_lock(directory):
        config = load_snapshot(directory)
        manifest = load_manifest(directory)
        if manifest.get("config_sha256") != sha256_json(config_to_dict(config)):
            raise WorkflowError("manifest config_sha256 does not match config snapshot")
        return _execute(config, directory, manifest, force_step=force_step)


def get_status(run_dir: str | Path) -> Mapping[str, object]:
    return load_manifest(Path(run_dir).resolve())
