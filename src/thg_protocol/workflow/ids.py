"""Persistent deterministic IDs for generated model objects."""

from __future__ import annotations

import json
import re
from pathlib import Path

from .hashing import sha256_json


class IdRegistryError(ValueError):
    """Raised for ID collisions or contradictory mappings."""


ID_POLICY_VERSION = 1


def _slug(value: str) -> str:
    result = re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_").lower()
    return result or "object"


class DeterministicIdRegistry:
    """Map stable source identities to IDs without collection-order effects."""

    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path is not None else None
        self.mappings: dict[str, str] = {}
        self.aliases: dict[str, str] = {}
        self.imported: dict[str, str] = {}
        if self.path is not None and self.path.exists():
            self.load(self.path)

    @staticmethod
    def source_key(
        *, object_type: str, source_id: str, compartment: str | None = None
    ) -> str:
        if not object_type.strip() or not source_id.strip():
            raise IdRegistryError("object_type and source_id must be non-empty")
        return json.dumps(
            {
                "object_type": object_type,
                "source_id": source_id,
                "compartment": compartment,
            },
            sort_keys=True,
            separators=(",", ":"),
        )

    def generate(
        self,
        *,
        object_type: str,
        source_id: str,
        compartment: str | None = None,
        prefix: str | None = None,
    ) -> str:
        key = self.source_key(
            object_type=object_type, source_id=source_id, compartment=compartment
        )
        existing = self.mappings.get(key)
        if existing is not None:
            return existing
        stem = _slug(source_id)
        if compartment:
            stem += "_" + _slug(compartment)
        tag = sha256_json({"policy": ID_POLICY_VERSION, "key": key})[:12]
        generated = f"{prefix or _slug(object_type)}_{stem}_{tag}"
        owner = next(
            (source for source, target in self.mappings.items() if target == generated),
            None,
        )
        if owner is not None and owner != key:
            raise IdRegistryError(f"generated ID collision: {generated}")
        self.mappings[key] = generated
        return generated

    def register_imported(self, *, source_id: str, target_id: str) -> None:
        if not source_id.strip() or not target_id.strip():
            raise IdRegistryError("imported IDs must be non-empty")
        existing = self.imported.get(source_id)
        if existing is not None and existing != target_id:
            raise IdRegistryError(f"conflicting imported mapping for '{source_id}'")
        self.imported[source_id] = target_id

    def register_alias(self, *, alias: str, target_id: str) -> None:
        existing = self.aliases.get(alias)
        if existing is not None and existing != target_id:
            raise IdRegistryError(f"conflicting alias mapping for '{alias}'")
        self.aliases[alias] = target_id

    def to_dict(self) -> dict[str, object]:
        return {
            "format_version": 1,
            "policy_version": ID_POLICY_VERSION,
            "mappings": dict(sorted(self.mappings.items())),
            "aliases": dict(sorted(self.aliases.items())),
            "imported": dict(sorted(self.imported.items())),
        }

    def save(self, path: str | Path | None = None) -> Path:
        destination = Path(path) if path is not None else self.path
        if destination is None:
            raise IdRegistryError("an ID registry path is required")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        self.path = destination
        return destination

    def load(self, path: str | Path) -> None:
        source = Path(path)
        try:
            payload = json.loads(source.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise IdRegistryError(f"cannot read ID registry: {source}") from error
        if (
            not isinstance(payload, dict)
            or payload.get("format_version") != 1
            or payload.get("policy_version") != ID_POLICY_VERSION
        ):
            raise IdRegistryError("unsupported ID registry schema or policy version")
        for name in ("mappings", "aliases", "imported"):
            value = payload.get(name)
            if not isinstance(value, dict) or not all(
                isinstance(k, str) and isinstance(v, str) for k, v in value.items()
            ):
                raise IdRegistryError(f"invalid ID registry field: {name}")
        self.mappings = dict(payload["mappings"])
        self.aliases = dict(payload["aliases"])
        self.imported = dict(payload["imported"])
        if len(self.mappings) != len(set(self.mappings.values())):
            raise IdRegistryError("ID registry contains a target collision")
        self.path = source
