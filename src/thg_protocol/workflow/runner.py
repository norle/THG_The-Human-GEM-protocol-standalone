"""Public workflow facade: resolve a DAG, then hand it to the runtime."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from thg_protocol.runtime.engine import ExecutionError, execute
from thg_protocol.runtime.hashing import sha256_json
from thg_protocol.runtime.locking import acquire_run_lock
from thg_protocol.runtime.manifest import (
    ManifestError,
    load_manifest,
    new_manifest,
    utc_now,
    write_manifest_atomic,
)

from .config import (
    ConfigError,
    WorkflowConfig,
    load_snapshot,
    load_workflow_config,
    workflow_config_to_dict,
    write_workflow_snapshot,
)
from .registry import WorkflowRegistryError, get_workflow


class WorkflowError(RuntimeError):
    """Raised when workflow resolution or execution fails."""


def _write(run_dir: Path, manifest: dict[str, object]) -> None:
    manifest["updated_at"] = utc_now()
    write_manifest_atomic(run_dir, manifest)


def _resume_config_key(config: WorkflowConfig) -> dict[str, object]:
    payload = workflow_config_to_dict(config)
    section = payload.get(config.workflow)
    if isinstance(section, dict):
        payload[config.workflow] = {
            key: value for key, value in section.items() if key != "n_jobs"
        }
    if config.workflow in {"gapfill", "reference"}:
        payload.pop("gapfill", None)
    return payload


def _definition(config: WorkflowConfig):
    try:
        return get_workflow(config.workflow)
    except WorkflowRegistryError as error:
        raise ConfigError(str(error)) from error


def _resolved_stages(config: WorkflowConfig, definition: object):
    del config
    return definition.stages


def _execute(
    config: WorkflowConfig,
    run_dir: Path,
    manifest: dict[str, object],
    stages: tuple[object, ...],
    *,
    force_step: str | None = None,
) -> Path:
    try:
        return execute(
            config=config,
            workflow_id=config.workflow,
            run_dir=run_dir,
            manifest=manifest,
            stages=stages,
            force_step=force_step,
        )
    except ExecutionError as error:
        raise WorkflowError(str(error)) from error


def start(config_path: str | Path) -> Path:
    config = load_workflow_config(config_path)
    definition = _definition(config)
    stages = _resolved_stages(config, definition)
    run_dir = config.run.output_dir
    if run_dir.exists() and not run_dir.is_dir():
        raise ConfigError(f"run output path is not a directory: {run_dir}")
    if run_dir.exists() and any(run_dir.iterdir()):
        try:
            saved_config = load_snapshot(run_dir)
            load_manifest(run_dir)
        except (ConfigError, ManifestError) as error:
            raise ConfigError(
                "run directory is nonempty and is not a resumable registered run"
            ) from error
        if _resume_config_key(saved_config) != _resume_config_key(config):
            raise ConfigError(
                "run directory contains a different configuration; "
                "choose a new output directory"
            )
        return resume(run_dir, _config_override=config)
    run_dir.mkdir(parents=True, exist_ok=True)
    with acquire_run_lock(run_dir):
        write_workflow_snapshot(config, run_dir)
        manifest = new_manifest(
            workflow_id=config.workflow,
            run_id=config.run.name,
            config_sha256=sha256_json(workflow_config_to_dict(config)),
            stages=stages,
            workflow_version=definition.version,
        )
        _write(run_dir, manifest)
        return _execute(config, run_dir, manifest, stages)


def resume(
    run_dir: str | Path,
    *,
    force_step: str | None = None,
    _config_override: WorkflowConfig | None = None,
) -> Path:
    directory = Path(run_dir).resolve()
    with acquire_run_lock(directory):
        saved_config = load_snapshot(directory)
        if not isinstance(saved_config, WorkflowConfig):
            raise ConfigError("run is not a registered workflow")
        config = saved_config
        definition = _definition(config)
        manifest = load_manifest(directory)
        if manifest.get("workflow_version", 1) != definition.version:
            raise WorkflowError(
                "incompatible workflow version; choose a new output directory"
            )
        if manifest.get("config_sha256") != sha256_json(
            workflow_config_to_dict(saved_config)
        ):
            raise WorkflowError("manifest config_sha256 does not match config snapshot")
        if _config_override is not None:
            if _resume_config_key(_config_override) != _resume_config_key(saved_config):
                raise ConfigError(
                    "run directory contains a different configuration; "
                    "choose a new output directory"
                )
            config = _config_override
            write_workflow_snapshot(config, directory)
            manifest["config_sha256"] = sha256_json(workflow_config_to_dict(config))
            _write(directory, manifest)
        if manifest.get("workflow") != config.workflow:
            raise WorkflowError("manifest workflow does not match config snapshot")
        steps = manifest.get("steps")
        if not isinstance(steps, Mapping):
            raise WorkflowError("manifest has no workflow steps")
        stage_ids = {str(stage_id) for stage_id in steps}
        if stage_ids != set(definition.stage_ids):
            raise WorkflowError(
                f"manifest stages do not match workflow '{config.workflow}'"
            )
        stages = definition.stages
        return _execute(config, directory, manifest, stages, force_step=force_step)


def get_status(run_dir: str | Path) -> Mapping[str, object]:
    return load_manifest(run_dir)


__all__ = ["WorkflowError", "start", "resume", "get_status"]
