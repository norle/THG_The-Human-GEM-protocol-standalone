"""Content hashes and artifact validation for resumable execution."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path


def sha256_file(path: str | Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_json(value: object) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _safe_path(path: Path, run_dir: Path) -> Path:
    root = run_dir.resolve()
    resolved = path.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as error:
        raise ValueError(f"artifact path escapes run directory: {path}") from error
    if not resolved.is_file():
        raise ValueError(f"artifact is not a regular file: {path}")
    return resolved


def artifact_record(role: str, path: Path, run_dir: Path) -> dict[str, object]:
    if not isinstance(role, str) or not role:
        raise ValueError("artifact role must be a non-empty string")
    resolved = _safe_path(Path(path), Path(run_dir))
    return {
        "role": role,
        "path": resolved.relative_to(Path(run_dir).resolve()).as_posix(),
        "sha256": sha256_file(resolved),
        "size": resolved.stat().st_size,
    }


def verify_artifact(record: Mapping[str, object], run_dir: Path) -> bool:
    try:
        role = record["role"]
        raw_path = record["path"]
        expected_hash = record["sha256"]
        expected_size = record["size"]
        if not isinstance(role, str) or not isinstance(raw_path, str):
            return False
        if not isinstance(expected_hash, str) or not isinstance(expected_size, int):
            return False
        path = _safe_path(Path(run_dir) / raw_path, Path(run_dir))
        stat = path.stat()
        return stat.st_size == expected_size and sha256_file(path) == expected_hash
    except (KeyError, OSError, TypeError, ValueError):
        return False


__all__ = ["artifact_record", "sha256_file", "sha256_json", "verify_artifact"]
