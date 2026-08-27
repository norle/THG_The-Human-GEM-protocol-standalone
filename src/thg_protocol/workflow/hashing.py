"""Compatibility facade for the runtime hashing helpers."""

from thg_protocol.runtime.hashing import (
    artifact_record,
    sha256_file,
    sha256_json,
    verify_artifact,
)

__all__ = ["artifact_record", "sha256_file", "sha256_json", "verify_artifact"]
