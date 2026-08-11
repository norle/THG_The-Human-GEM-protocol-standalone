"""Validated and atomically persisted registered-workflow state."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path

from .config import WorkflowConfig, workflow_config_to_dict
from .hashing import sha256_json


class ManifestError(RuntimeError):
    """Raised when a workflow manifest is malformed."""


STEP_STATUSES = {"pending", "running", "completed", "failed", "interrupted", "skipped"}
OVERALL_STATUSES = {"pending", "running", "completed", "failed", "interrupted"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _package_version() -> str:
    try:
        from thg_protocol import __version__

        return str(__version__)
    except Exception:  # pragma: no cover
        return "unknown"


def new_workflow_manifest(
    config: WorkflowConfig, stages: tuple[object, ...]
) -> dict[str, object]:
    now = utc_now()
    return {
        "format_version": 2,
        "workflow": config.workflow,
        "run_id": config.run.name,
        "created_at": now,
        "updated_at": now,
        "config_sha256": sha256_json(workflow_config_to_dict(config)),
        "package_version": _package_version(),
        "overall_status": "pending",
        "steps": {
            stage.id: {
                "status": "pending",
                "attempt": 0,
                "fingerprint": None,
                "started_at": None,
                "finished_at": None,
                "outputs": [],
                "error": None,
                "summary": {},
            }
            for stage in stages
        },
    }


def validate_workflow_manifest(manifest: Mapping[str, object]) -> None:
    if manifest.get("format_version") != 2:
        raise ManifestError("unsupported workflow manifest format_version")
    for key in (
        "workflow", "run_id", "created_at", "updated_at", "config_sha256",
        "package_version", "overall_status", "steps",
    ):
        if key not in manifest:
            raise ManifestError(f"workflow manifest missing '{key}'")
    if not isinstance(manifest["workflow"], str) or not manifest["workflow"]:
        raise ManifestError("workflow manifest workflow must be non-empty text")
    if manifest["overall_status"] not in OVERALL_STATUSES:
        raise ManifestError("invalid overall_status")
    steps = manifest["steps"]
    if not isinstance(steps, Mapping) or not steps:
        raise ManifestError("workflow manifest steps must be a non-empty object")
    for stage, entry in steps.items():
        if not isinstance(stage, str) or not stage or not isinstance(entry, Mapping):
            raise ManifestError("malformed workflow manifest step")
        required = {
            "status", "attempt", "fingerprint", "started_at", "finished_at",
            "outputs", "error",
        }
        if not required.issubset(entry) or set(entry) - required - {"summary"}:
            raise ManifestError(f"malformed workflow manifest step keys: {stage}")
        if entry["status"] not in STEP_STATUSES:
            raise ManifestError(f"invalid status for step '{stage}'")
        if not isinstance(entry["attempt"], int) or entry["attempt"] < 0:
            raise ManifestError(f"invalid attempt for step '{stage}'")
        if entry["fingerprint"] is not None and not isinstance(
            entry["fingerprint"], str
        ):
            raise ManifestError(f"invalid fingerprint for step '{stage}'")
        if not isinstance(entry["outputs"], list):
            raise ManifestError(f"invalid outputs for step '{stage}'")
        for output in entry["outputs"]:
            if not isinstance(output, Mapping) or set(output) != {
                "role",
                "path",
                "sha256",
                "size",
            }:
                raise ManifestError(f"malformed artifact in step '{stage}'")
            if not (
                isinstance(output["role"], str)
                and isinstance(output["path"], str)
                and isinstance(output["sha256"], str)
                and isinstance(output["size"], int)
            ):
                raise ManifestError(f"malformed artifact values in step '{stage}'")
        if entry["error"] is not None and not isinstance(entry["error"], str):
            raise ManifestError(f"invalid error for step '{stage}'")


def write_manifest_atomic(run_dir: Path, manifest: Mapping[str, object]) -> None:
    validate_workflow_manifest(manifest)
    directory = Path(run_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "manifest.json"
    temporary = directory / "manifest.json.tmp"
    with temporary.open("w", encoding="utf-8") as handle:
        handle.write(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def load_workflow_manifest(run_dir: str | Path) -> dict[str, object]:
    path = Path(run_dir).resolve() / "manifest.json"
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise ManifestError(f"missing or unreadable manifest: {path}") from error
    except json.JSONDecodeError as error:
        raise ManifestError(f"manifest is not valid JSON: {error.msg}") from error
    validate_workflow_manifest(manifest)
    return manifest


__all__ = [
    "ManifestError", "load_workflow_manifest", "new_workflow_manifest",
    "validate_workflow_manifest", "write_manifest_atomic",
]
