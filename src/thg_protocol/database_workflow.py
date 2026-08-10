"""Restartable, offline-first Human Database collection primitives.

The module deliberately separates collection from reconstruction.  Adapters
return normalized records, while the cache and error ledger make a run
reproducible without credentials or network access.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Protocol

from .database import GeneRecord, MetaboliteRecord, ReactionRecord, reconstruct_model

SCHEMA_VERSION = 1


@dataclass(frozen=True)
class HarvestError:
    key: str
    error_type: str
    message: str
    attempts: int


@dataclass(frozen=True)
class NormalizedRecords:
    metabolites: tuple[MetaboliteRecord, ...] = ()
    reactions: tuple[ReactionRecord, ...] = ()
    genes: tuple[GeneRecord, ...] = ()
    pathways: Mapping[str, tuple[str, ...]] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.pathways is None:
            object.__setattr__(self, "pathways", {})

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "metabolites": [asdict(item) for item in self.metabolites],
            "reactions": [asdict(item) for item in self.reactions],
            "genes": [asdict(item) for item in self.genes],
            "pathways": {
                key: list(value) for key, value in sorted(self.pathways.items())
            },
        }


class SourceAdapter(Protocol):
    """One source adapter; implementations must not hide network access."""

    release: str

    def fetch(self, key: str) -> Mapping[str, Any]: ...


def normalize_records(payload: Mapping[str, Any]) -> NormalizedRecords:
    """Validate and normalize a versioned record payload deterministically."""
    version = payload.get("schema_version", SCHEMA_VERSION)
    if version != SCHEMA_VERSION:
        raise ValueError(f"unsupported normalized-record schema: {version}")

    def items(name: str) -> list[Mapping[str, Any]]:
        value = payload.get(name, [])
        if not isinstance(value, list) or not all(
            isinstance(item, Mapping) for item in value
        ):
            raise ValueError(f"'{name}' must be a list of objects")
        return [dict(item) for item in value]

    pathways = payload.get("pathways", {})
    if not isinstance(pathways, Mapping):
        raise ValueError("'pathways' must be an object")
    return NormalizedRecords(
        tuple(MetaboliteRecord(**item) for item in items("metabolites")),
        tuple(ReactionRecord(**item) for item in items("reactions")),
        tuple(GeneRecord(**item) for item in items("genes")),
        {
            str(key): tuple(str(value) for value in values)
            for key, values in pathways.items()
        },
    )


def records_checksum(records: NormalizedRecords) -> str:
    body = json.dumps(records.to_dict(), sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(body).hexdigest()


def harvest_snapshot(
    keys: Iterable[str],
    adapter: SourceAdapter,
    cache_dir: str | Path,
    *,
    retries: int = 2,
    delay_seconds: float = 0.0,
) -> tuple[dict[str, Mapping[str, Any]], tuple[HarvestError, ...]]:
    """Harvest keys with bounded retries into a content-addressed cache.

    Cached responses are used before invoking the adapter, so offline reruns
    are deterministic.  Failures are returned as data and never swallowed.
    """
    if retries < 0 or delay_seconds < 0:
        raise ValueError("retries and delay_seconds must be non-negative")
    root = Path(cache_dir)
    root.mkdir(parents=True, exist_ok=True)
    adapter_release = str(getattr(adapter, "release", "unknown"))
    manifest_path = root / "cache-manifest.json"
    cache_compatible = False
    if manifest_path.is_file():
        try:
            previous_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            previous_manifest = None
        cache_compatible = (
            isinstance(previous_manifest, dict)
            and previous_manifest.get("schema_version") == SCHEMA_VERSION
            and previous_manifest.get("adapter_release") == adapter_release
        )
    responses: dict[str, Mapping[str, Any]] = {}
    errors: list[HarvestError] = []
    for key in sorted(set(str(item) for item in keys)):
        digest = hashlib.sha256(key.encode()).hexdigest()
        path = root / f"{digest}.json"
        if cache_compatible and path.is_file():
            payload = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                responses[key] = payload
                continue
        for attempt in range(1, retries + 2):
            try:
                payload = adapter.fetch(key)
                if not isinstance(payload, Mapping):
                    raise TypeError("adapter response must be an object")
                serializable = dict(payload)
                path.write_text(
                    json.dumps(serializable, sort_keys=True) + "\n", encoding="utf-8"
                )
                responses[key] = serializable
                break
            except Exception as error:  # returned in the explicit error ledger
                if attempt > retries:
                    errors.append(
                        HarvestError(key, type(error).__name__, str(error), attempt)
                    )
                elif delay_seconds:
                    time.sleep(delay_seconds)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "adapter_release": adapter_release,
        "keys": sorted(responses),
        "errors": [asdict(error) for error in errors],
    }
    (root / "cache-manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (root / "errors.jsonl").write_text(
        "".join(json.dumps(asdict(error), sort_keys=True) + "\n" for error in errors),
        encoding="utf-8",
    )
    return responses, tuple(errors)


def reconstruct_snapshot(
    model_id: str, records: NormalizedRecords, *, output_path: str | Path | None = None
) -> Any:
    """Reconstruct solely from normalized records; no service clients are used."""
    return reconstruct_model(
        model_id,
        records.metabolites,
        records.reactions,
        records.genes,
        pathways=records.pathways,
        output_path=output_path,
    )


__all__ = [
    "HarvestError",
    "NormalizedRecords",
    "SCHEMA_VERSION",
    "SourceAdapter",
    "harvest_snapshot",
    "normalize_records",
    "records_checksum",
    "reconstruct_snapshot",
]
