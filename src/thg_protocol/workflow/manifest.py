"""Validated and atomically persisted workflow state."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path

from .config import RunConfig, config_to_dict
from .hashing import sha256_json


class ManifestError(RuntimeError):
    """Raised when a workflow manifest is malformed."""


STAGES = ("reference", "database", "merge", "validation", "memote")
STEP_STATUSES = {"pending", "running", "completed", "failed", "interrupted", "skipped"}
OVERALL_STATUSES = {"pending", "running", "completed", "failed", "interrupted"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def new_manifest(config: RunConfig) -> dict[str, object]:
    now = utc_now()
    return {
        "format_version": 1,
        "run_id": config.run.name,
        "created_at": now,
        "updated_at": now,
        "config_sha256": sha256_json(config_to_dict(config)),
        "package_version": _package_version(),
        "overall_status": "pending",
        "steps": {
            stage: {
                "status": "pending",
                "attempt": 0,
                "fingerprint": None,
                "started_at": None,
                "finished_at": None,
                "outputs": [],
                "error": None,
                "summary": {},
            }
            for stage in STAGES
        },
    }


def _package_version() -> str:
    try:
        from thg_protocol import __version__

        return str(__version__)
    except Exception:  # pragma: no cover - defensive packaging fallback
        return "unknown"


def validate_manifest(manifest: Mapping[str, object]) -> None:
    if not isinstance(manifest, Mapping):
        raise ManifestError("manifest must be a JSON object")
    if manifest.get("format_version") != 1:
        raise ManifestError("unsupported manifest format_version")
    for key in (
        "run_id",
        "created_at",
        "updated_at",
        "config_sha256",
        "package_version",
        "overall_status",
        "steps",
    ):
        if key not in manifest:
            raise ManifestError(f"manifest missing '{key}'")
    if manifest["overall_status"] not in OVERALL_STATUSES:
        raise ManifestError("invalid overall_status")
    steps = manifest["steps"]
    if not isinstance(steps, Mapping) or set(steps) != set(STAGES):
        raise ManifestError("manifest steps must contain exactly the version 1 stages")
    for stage in STAGES:
        entry = steps[stage]
        if not isinstance(entry, Mapping):
            raise ManifestError(f"malformed manifest step: {stage}")
        required = {
            "status",
            "attempt",
            "fingerprint",
            "started_at",
            "finished_at",
            "outputs",
            "error",
        }
        if not required.issubset(entry) or set(entry) - required - {"summary"}:
            raise ManifestError(f"malformed manifest step keys: {stage}")
        if "summary" in entry and not isinstance(entry["summary"], Mapping):
            raise ManifestError(f"invalid summary for step '{stage}'")
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
            if (
                not isinstance(output["role"], str)
                or not isinstance(output["path"], str)
                or not isinstance(output["sha256"], str)
                or not isinstance(output["size"], int)
            ):
                raise ManifestError(f"malformed artifact values in step '{stage}'")
        if entry["error"] is not None and not isinstance(entry["error"], str):
            raise ManifestError(f"invalid error for step '{stage}'")


def load_manifest(run_dir: str | Path) -> dict[str, object]:
    path = Path(run_dir).resolve() / "manifest.json"
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise ManifestError(f"missing or unreadable manifest: {path}") from error
    except json.JSONDecodeError as error:
        raise ManifestError(f"manifest is not valid JSON: {error.msg}") from error
    validate_manifest(manifest)
    return manifest


def write_manifest_atomic(run_dir: Path, manifest: Mapping[str, object]) -> None:
    validate_manifest(manifest)
    directory = Path(run_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "manifest.json"
    temporary = directory / "manifest.json.tmp"
    payload = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    with temporary.open("w", encoding="utf-8") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)
