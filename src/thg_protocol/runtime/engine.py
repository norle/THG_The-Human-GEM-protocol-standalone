"""Generic resumable execution engine for resolved stage sequences."""

from __future__ import annotations

import logging
import os
import shutil
import time
import traceback
from collections.abc import Mapping, Sequence
from pathlib import Path

from .hashing import artifact_record, sha256_json, verify_artifact
from .manifest import utc_now, write_manifest_atomic
from .stage import Stage, StageContext

LOGGER = logging.getLogger("thg_protocol.workflow")


class ExecutionError(RuntimeError):
    """Raised when a resolved stage sequence cannot complete."""


def _descendants(stages: Sequence[Stage], stage_id: str) -> set[str]:
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
        raise ExecutionError(f"manifest has no step '{stage_id}'")
    return steps[stage_id]


def _write(run_dir: Path, manifest: dict[str, object]) -> None:
    manifest["updated_at"] = utc_now()
    write_manifest_atomic(run_dir, manifest)


def _invalidate(
    manifest: dict[str, object], stages: Sequence[Stage], stage_id: str
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


def _attach_run_log(run_dir: Path) -> logging.Handler:
    path = run_dir / "logs" / "run.log"
    path.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(path, encoding="utf-8")
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%H:%M:%S")
    )
    logging.getLogger("thg_protocol.workflow").addHandler(handler)
    return handler


def _error(error: BaseException) -> str:
    return f"{type(error).__name__}: {str(error).strip().replace(chr(10), ' ')}"[:1000]


def execute(
    *,
    config: object,
    workflow_id: str = "workflow",
    run_dir: Path,
    manifest: dict[str, object],
    stages: tuple[Stage, ...],
    force_step: str | None = None,
) -> Path:
    """Execute already-resolved stages; no workflow discovery happens here."""
    handler = _attach_run_log(run_dir)
    try:
        if force_step is not None:
            if force_step not in {stage.id for stage in stages}:
                raise ExecutionError(f"unknown stage: {force_step}")
            LOGGER.info(
                "invalidating stage %s and its descendants",
                force_step,
                extra={"thg_compact": True},
            )
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
        LOGGER.info(
            "running %s workflow with %s stages in %s",
            workflow_id,
            len(stages),
            run_dir,
            extra={"thg_compact": True},
        )
        for index, stage in enumerate(stages, start=1):
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
                LOGGER.info(
                    "[%s/%s] %s: skipped (disabled)",
                    index,
                    len(stages),
                    stage.id,
                    extra={"thg_compact": True},
                )
                continue
            context = StageContext(config, run_dir, manifest)
            fingerprint = sha256_json(stage.fingerprint_data(context))
            if (
                entry["status"] == "completed"
                and entry.get("fingerprint") == fingerprint
                and _artifacts_valid(entry, run_dir)
            ):
                LOGGER.info(
                    "[%s/%s] %s: reused valid artifacts",
                    index,
                    len(stages),
                    stage.id,
                    extra={"thg_compact": True},
                )
                LOGGER.debug("%s fingerprint: %s", stage.id, fingerprint)
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
            LOGGER.info(
                "[%s/%s] %s: starting attempt %s", index, len(stages), stage.id, attempt
            )
            LOGGER.debug("%s fingerprint: %s", stage.id, fingerprint)
            started = time.monotonic()
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
                        raise ExecutionError(
                            f"stage '{stage.id}' returned an output outside its "
                            "work directory"
                        ) from error
                    if not resolved.is_file():
                        raise ExecutionError(
                            f"stage '{stage.id}' returned a non-file output"
                        )
                if final.exists():
                    raise ExecutionError(
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
                LOGGER.info(
                    "[%s/%s] %s: completed in %.2fs",
                    index,
                    len(stages),
                    stage.id,
                    time.monotonic() - started,
                    extra={"thg_compact": True},
                )
                LOGGER.debug("%s summary: %r", stage.id, dict(result.summary))
                for record in outputs:
                    LOGGER.debug("%s output: %s", stage.id, record.get("path"))
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
                log_path.parent.mkdir(parents=True, exist_ok=True)
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
                    status="failed",
                    finished_at=utc_now(),
                    outputs=[],
                    error=_error(error),
                )
                log_path.parent.mkdir(parents=True, exist_ok=True)
                log_path.write_text(traceback.format_exc(), encoding="utf-8")
                manifest["overall_status"] = "failed"
                _write(run_dir, manifest)
                LOGGER.error(
                    "[%s/%s] %s: failed; log: %s",
                    index,
                    len(stages),
                    stage.id,
                    log_path,
                )
                raise ExecutionError(
                    f"stage '{stage.id}' failed: {_error(error)}"
                ) from error
        manifest["overall_status"] = "completed"
        _write(run_dir, manifest)
        LOGGER.info("workflow completed: %s", run_dir, extra={"thg_compact": True})
        return run_dir
    finally:
        logger = logging.getLogger("thg_protocol.workflow")
        logger.removeHandler(handler)
        handler.close()


__all__ = ["ExecutionError", "execute"]
