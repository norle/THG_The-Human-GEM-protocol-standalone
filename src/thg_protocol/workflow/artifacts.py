"""Compatibility facade for :mod:`thg_protocol.runtime.artifacts`."""

from thg_protocol.runtime.artifacts import (
    ArtifactReference,
    ArtifactReferenceError,
    ResolvedArtifact,
    resolve_artifact,
    upstream_fingerprint,
)

__all__ = [
    "ArtifactReference",
    "ArtifactReferenceError",
    "ResolvedArtifact",
    "resolve_artifact",
    "upstream_fingerprint",
]
