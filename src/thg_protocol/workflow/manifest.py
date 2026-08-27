"""Compatibility facade for the runtime manifest helpers."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from thg_protocol.runtime.hashing import sha256_json
from thg_protocol.runtime.manifest import (
    ManifestError,
    load_manifest,
    new_manifest,
    utc_now,
    validate_manifest,
    write_manifest_atomic,
)


def new_workflow_manifest(
    config: object, stages: Sequence[object]
) -> dict[str, object]:
    return new_manifest(
        workflow_id=str(config.workflow),
        run_id=str(config.run.name),
        config_sha256=sha256_json(_config_dict(config)),
        stages=stages,
    )


def _config_dict(config: object) -> dict[str, object]:
    from .config import workflow_config_to_dict

    return workflow_config_to_dict(config)


def load_workflow_manifest(run_dir: str | Path) -> dict[str, object]:
    return load_manifest(run_dir)


__all__ = [
    "ManifestError",
    "load_workflow_manifest",
    "new_workflow_manifest",
    "validate_workflow_manifest",
    "write_manifest_atomic",
    "utc_now",
]

validate_workflow_manifest = validate_manifest
