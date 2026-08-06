"""Versioned normalized evidence records and content-addressed raw cache."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .hashing import sha256_json


class EvidenceError(ValueError):
    """Raised for unsupported or incomplete evidence records."""


EVIDENCE_SCHEMA_VERSION = 1
REQUIRED_FIELDS = (
    "evidence_id",
    "source",
    "source_version",
    "query",
    "normalized_result",
    "raw_response_path",
    "raw_response_sha256",
    "parser_version",
    "normalization_version",
    "confidence",
    "affected_objects",
    "errors",
    "warnings",
    "retry_history",
    "license",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class EvidenceRecord:
    evidence_id: str
    source: str
    source_version: str
    query: object
    normalized_result: object
    raw_response_path: str | None
    raw_response_sha256: str | None
    parser_version: str
    normalization_version: str
    confidence: str
    affected_objects: tuple[str, ...]
    errors: tuple[str, ...]
    warnings: tuple[str, ...]
    retry_history: tuple[Mapping[str, object], ...]
    license: str | None = None
    schema_version: int = EVIDENCE_SCHEMA_VERSION
    recorded_at: str = ""
    normalized_result_sha256: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != EVIDENCE_SCHEMA_VERSION:
            raise EvidenceError(
                f"unsupported evidence schema version: {self.schema_version}"
            )
        normalized_hash = hashlib.sha256(
            json.dumps(
                self.normalized_result,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
            ).encode("utf-8")
        ).hexdigest()
        if (
            self.normalized_result_sha256
            and self.normalized_result_sha256 != normalized_hash
        ):
            raise EvidenceError("normalized result checksum does not match evidence")
        object.__setattr__(self, "normalized_result_sha256", normalized_hash)
        if not self.recorded_at:
            object.__setattr__(self, "recorded_at", _utc_now())

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> EvidenceRecord:
        version = value.get("schema_version", EVIDENCE_SCHEMA_VERSION)
        if version != EVIDENCE_SCHEMA_VERSION:
            raise EvidenceError(f"unsupported evidence schema version: {version}")
        missing = [field for field in REQUIRED_FIELDS if field not in value]
        if missing:
            raise EvidenceError(f"evidence is missing: {', '.join(missing)}")

        def text(key: str, *, nullable: bool = False) -> str | None:
            item = value[key]
            if nullable and item is None:
                return None
            if not isinstance(item, str) or not item.strip():
                raise EvidenceError(f"evidence field '{key}' must be non-empty text")
            return item

        def texts(key: str) -> tuple[str, ...]:
            item = value[key]
            if not isinstance(item, list) or not all(isinstance(x, str) for x in item):
                raise EvidenceError(f"evidence field '{key}' must be a list of text")
            return tuple(item)

        retries = value["retry_history"]
        if not isinstance(retries, list) or not all(
            isinstance(x, dict) for x in retries
        ):
            raise EvidenceError(
                "evidence field 'retry_history' must be a list of objects"
            )
        raw_hash = text("raw_response_sha256", nullable=True)
        if raw_hash is not None and len(raw_hash) != 64:
            raise EvidenceError("raw_response_sha256 must be a SHA-256 string")
        return cls(
            evidence_id=text("evidence_id") or "",
            source=text("source") or "",
            source_version=text("source_version") or "",
            query=value["query"],
            normalized_result=value["normalized_result"],
            raw_response_path=text("raw_response_path", nullable=True),
            raw_response_sha256=raw_hash,
            parser_version=text("parser_version") or "",
            normalization_version=text("normalization_version") or "",
            confidence=text("confidence") or "",
            affected_objects=texts("affected_objects"),
            errors=texts("errors"),
            warnings=texts("warnings"),
            retry_history=tuple(retries),
            license=text("license", nullable=True),
            schema_version=version,
            recorded_at=value.get("recorded_at", ""),
            normalized_result_sha256=value.get("normalized_result_sha256", ""),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "evidence_id": self.evidence_id,
            "source": self.source,
            "source_version": self.source_version,
            "query": self.query,
            "normalized_result": self.normalized_result,
            "raw_response_path": self.raw_response_path,
            "raw_response_sha256": self.raw_response_sha256,
            "parser_version": self.parser_version,
            "normalization_version": self.normalization_version,
            "confidence": self.confidence,
            "affected_objects": list(self.affected_objects),
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "retry_history": [dict(item) for item in self.retry_history],
            "license": self.license,
            "recorded_at": self.recorded_at,
            "normalized_result_sha256": self.normalized_result_sha256,
        }


def evidence_id(*, source: str, query: object, normalized_result: object) -> str:
    """Return an order-independent content-derived evidence ID."""
    return "ev-" + sha256_json(
        {"source": source, "query": query, "normalized_result": normalized_result}
    )


class EvidenceStore:
    """Append-only JSONL evidence store with a content-addressed raw cache."""

    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self.records_path = self.root / "evidence.jsonl"
        self.raw_root = self.root / "raw"

    def cache_raw(self, payload: bytes) -> tuple[Path, str]:
        digest = hashlib.sha256(payload).hexdigest()
        path = self.raw_root / digest[:2] / digest
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.read_bytes() != payload:
            raise EvidenceError(f"content-addressed cache collision: {digest}")
        if not path.exists():
            path.write_bytes(payload)
        return path, digest

    def append(self, record: EvidenceRecord | Mapping[str, Any]) -> EvidenceRecord:
        item = (
            record
            if isinstance(record, EvidenceRecord)
            else EvidenceRecord.from_mapping(record)
        )
        if item.raw_response_path is not None:
            raw = Path(item.raw_response_path)
            if not raw.is_absolute():
                raw = self.root / raw
            if not raw.is_file():
                raise EvidenceError(f"raw response does not exist: {raw}")
            digest = hashlib.sha256(raw.read_bytes()).hexdigest()
            if item.raw_response_sha256 != digest:
                raise EvidenceError("raw response checksum does not match evidence")
        self.root.mkdir(parents=True, exist_ok=True)
        with self.records_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(item.to_dict(), sort_keys=True) + "\n")
        return item

    def read(self) -> tuple[EvidenceRecord, ...]:
        if not self.records_path.exists():
            return ()
        records: list[EvidenceRecord] = []
        for line_number, line in enumerate(
            self.records_path.read_text(encoding="utf-8").splitlines(), 1
        ):
            if not line.strip():
                continue
            try:
                records.append(EvidenceRecord.from_mapping(json.loads(line)))
            except (json.JSONDecodeError, EvidenceError) as error:
                raise EvidenceError(
                    f"invalid evidence JSONL at line {line_number}: {error}"
                ) from error
        return tuple(records)

    def verify_offline(self) -> None:
        for record in self.read():
            if record.raw_response_path is None:
                continue
            raw = Path(record.raw_response_path)
            if not raw.is_absolute():
                raw = self.root / raw
            if not raw.is_file():
                raise EvidenceError(f"recorded raw response is missing: {raw}")
            if (
                hashlib.sha256(raw.read_bytes()).hexdigest()
                != record.raw_response_sha256
            ):
                raise EvidenceError(f"recorded raw response changed: {raw}")
