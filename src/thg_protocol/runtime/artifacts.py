"""Explicit references to artifacts produced by upstream runs."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .hashing import sha256_json, verify_artifact


class ArtifactReferenceError(RuntimeError):
    """Raised when an upstream artifact cannot be proven valid."""


@dataclass(frozen=True)
class ArtifactReference:
    run_dir: Path
    stage_id: str
    role: str
    sha256: str | None = None

    @classmethod
    def from_mapping(
        cls, value: Mapping[str, Any], *, base_dir: Path | None = None
    ) -> ArtifactReference:
        required = {"run_dir", "stage_id", "role"}
        missing = sorted(required - set(value))
        if missing:
            raise ArtifactReferenceError(
                f"upstream artifact reference is missing: {', '.join(missing)}"
            )
        raw_dir = value["run_dir"]
        if not isinstance(raw_dir, str) or not raw_dir.strip():
            raise ArtifactReferenceError("upstream.run_dir must be non-empty text")
        directory = Path(raw_dir)
        if not directory.is_absolute() and base_dir is not None:
            directory = base_dir / directory
        stage_id, role = value["stage_id"], value["role"]
        if not isinstance(stage_id, str) or not stage_id.strip():
            raise ArtifactReferenceError("upstream.stage_id must be non-empty text")
        if not isinstance(role, str) or not role.strip():
            raise ArtifactReferenceError("upstream.role must be non-empty text")
        checksum = value.get("sha256")
        if checksum is not None and (
            not isinstance(checksum, str) or len(checksum) != 64
        ):
            raise ArtifactReferenceError("upstream.sha256 must be a SHA-256 string")
        return cls(directory.resolve(), stage_id, role, checksum)

    def to_dict(self) -> dict[str, object]:
        result: dict[str, object] = {
            "run_dir": str(self.run_dir),
            "stage_id": self.stage_id,
            "role": self.role,
        }
        if self.sha256 is not None:
            result["sha256"] = self.sha256
        return result


@dataclass(frozen=True)
class ResolvedArtifact:
    reference: ArtifactReference
    path: Path
    record: Mapping[str, object]
    manifest_sha256: str

    @property
    def fingerprint(self) -> str:
        return sha256_json(
            {
                "reference": self.reference.to_dict(),
                "record": dict(self.record),
                "manifest_sha256": self.manifest_sha256,
            }
        )


def _read_manifest(run_dir: Path) -> tuple[dict[str, Any], str]:
    path = run_dir / "manifest.json"
    try:
        payload = path.read_text(encoding="utf-8")
        manifest = json.loads(payload)
    except (OSError, json.JSONDecodeError) as error:
        raise ArtifactReferenceError(
            f"cannot read upstream manifest: {path}"
        ) from error
    if not isinstance(manifest, dict) or not isinstance(manifest.get("steps"), dict):
        raise ArtifactReferenceError(f"upstream manifest is malformed: {path}")
    return manifest, hashlib.sha256(payload.encode("utf-8")).hexdigest()


def resolve_artifact(
    reference: ArtifactReference | Mapping[str, Any], *, base_dir: Path | None = None
) -> ResolvedArtifact:
    item = (
        reference
        if isinstance(reference, ArtifactReference)
        else ArtifactReference.from_mapping(reference, base_dir=base_dir)
    )
    manifest, manifest_hash = _read_manifest(item.run_dir)
    entry = manifest["steps"].get(item.stage_id)
    if not isinstance(entry, dict) or entry.get("status") != "completed":
        raise ArtifactReferenceError(
            f"upstream stage '{item.stage_id}' is not completed in {item.run_dir}"
        )
    outputs = entry.get("outputs")
    if not isinstance(outputs, list):
        raise ArtifactReferenceError(f"upstream stage '{item.stage_id}' has no outputs")
    matches = [
        record
        for record in outputs
        if isinstance(record, dict) and record.get("role") == item.role
    ]
    if not matches:
        raise ArtifactReferenceError(
            f"upstream stage '{item.stage_id}' has no output role '{item.role}'"
        )
    if len(matches) != 1:
        raise ArtifactReferenceError(
            f"upstream stage '{item.stage_id}' has ambiguous output role '{item.role}'"
        )
    record = matches[0]
    if not verify_artifact(record, item.run_dir):
        raise ArtifactReferenceError(
            f"upstream artifact changed or is invalid: {item.stage_id}/{item.role}"
        )
    if item.sha256 is not None and record.get("sha256") != item.sha256:
        raise ArtifactReferenceError(
            "upstream artifact checksum does not match the declared reference: "
            f"{item.stage_id}/{item.role}"
        )
    raw_path = record.get("path")
    if not isinstance(raw_path, str):
        raise ArtifactReferenceError("upstream artifact path is invalid")
    return ResolvedArtifact(item, item.run_dir / raw_path, record, manifest_hash)


def upstream_fingerprint(
    references: list[ArtifactReference | Mapping[str, Any]],
    *,
    base_dir: Path | None = None,
) -> dict[str, object]:
    resolved = [resolve_artifact(item, base_dir=base_dir) for item in references]
    return {
        "artifacts": [
            {
                "run_dir": str(item.reference.run_dir),
                "stage_id": item.reference.stage_id,
                "role": item.reference.role,
                "sha256": item.record["sha256"],
                "manifest_sha256": item.manifest_sha256,
            }
            for item in resolved
        ],
        "fingerprint": sha256_json([item.fingerprint for item in resolved]),
    }


__all__ = [
    "ArtifactReference",
    "ArtifactReferenceError",
    "ResolvedArtifact",
    "resolve_artifact",
    "upstream_fingerprint",
]
