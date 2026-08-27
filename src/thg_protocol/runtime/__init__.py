"""Generic resumable execution primitives."""

from .artifacts import (
    ArtifactReference,
    ArtifactReferenceError,
    ResolvedArtifact,
    resolve_artifact,
    upstream_fingerprint,
)
from .concurrency import parallel_map
from .hashing import artifact_record, sha256_file, sha256_json, verify_artifact
from .locking import RunLockedError, acquire_run_lock, unlock_run
from .manifest import (
    ManifestError,
    load_manifest,
    new_manifest,
    validate_manifest,
    write_manifest_atomic,
)
from .stage import Stage, StageContext, StageResult

__all__ = [
    "ArtifactReference",
    "ArtifactReferenceError",
    "ResolvedArtifact",
    "resolve_artifact",
    "upstream_fingerprint",
    "parallel_map",
    "artifact_record",
    "sha256_file",
    "sha256_json",
    "verify_artifact",
    "RunLockedError",
    "acquire_run_lock",
    "unlock_run",
    "ManifestError",
    "load_manifest",
    "new_manifest",
    "validate_manifest",
    "write_manifest_atomic",
    "Stage",
    "StageContext",
    "StageResult",
]
