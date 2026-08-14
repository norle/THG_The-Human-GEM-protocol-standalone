"""GOA annotation parsing and injectable clients."""

from __future__ import annotations

import gzip
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Protocol

from ._http import request

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None  # type: ignore[assignment]


@dataclass(frozen=True)
class GOAAnnotation:
    object_id: str
    symbol: str
    go_id: str
    aspect: str
    qualifier: str
    evidence_code: str
    reference: str
    assigned_by: str
    source_release: str = ""


class GOAClientProtocol(Protocol):
    def annotations_for(self, identifiers: Iterable[str]) -> list[GOAAnnotation]: ...


def parse_gaf(text: str, *, source_release: str = "") -> list[GOAAnnotation]:
    result = []
    for line in text.splitlines():
        if not line or line.startswith("!"):
            continue
        fields = line.split("\t")
        if len(fields) < 15 or fields[8] != "C" or "NOT" in fields[3].split("|"):
            continue
        result.append(
            GOAAnnotation(
                object_id=fields[1],
                symbol=fields[2],
                go_id=fields[4],
                aspect=fields[8],
                qualifier=fields[3] or "located_in",
                evidence_code=fields[6],
                reference=fields[5],
                assigned_by=fields[14],
                source_release=source_release,
            )
        )
    return result


@dataclass
class StaticGOAClient:
    annotations: list[GOAAnnotation | Mapping[str, object]] = field(
        default_factory=list
    )

    def annotations_for(self, identifiers: Iterable[str]) -> list[GOAAnnotation]:
        wanted = {str(item) for item in identifiers}
        result = []
        for raw in self.annotations:
            item = (
                raw
                if isinstance(raw, GOAAnnotation)
                else GOAAnnotation(
                    object_id=str(raw.get("object_id", raw.get("gene_id", ""))),
                    symbol=str(raw.get("symbol", raw.get("gene_id", ""))),
                    go_id=str(raw.get("go_id", "")),
                    aspect=str(raw.get("aspect", "C")),
                    qualifier=str(raw.get("qualifier", "located_in")),
                    evidence_code=str(raw.get("evidence_code", "")),
                    reference=str(raw.get("reference", "")),
                    assigned_by=str(raw.get("assigned_by", "")),
                    source_release=str(raw.get("source_release", "")),
                )
            )
            if item.symbol in wanted or item.object_id in wanted:
                result.append(item)
        return result


class GOAClient:
    """Bulk GOA client; callers should persist its returned records."""

    url = "https://current.geneontology.org/annotations/goa_human.gaf.gz"

    def __init__(self, *, timeout: float = 30.0, session: object | None = None) -> None:
        self.timeout = timeout
        self.session = session or (requests.Session() if requests is not None else None)
        self._annotations: list[GOAAnnotation] | None = None

    def _load(self) -> list[GOAAnnotation]:
        if self._annotations is None:
            if self.session is None:
                raise RuntimeError("GOAClient requires the 'requests' dependency")
            response = request(
                self.session,
                "get",
                self.url,
                timeout=self.timeout,
                retries=2,
                backoff=0.5,
            )
            self._annotations = parse_gaf(
                gzip.decompress(response.content).decode("utf-8"),
                source_release="live",
            )
        return self._annotations

    def annotations_for(self, identifiers: Iterable[str]) -> list[GOAAnnotation]:
        return StaticGOAClient(self._load()).annotations_for(identifiers)


__all__ = [
    "GOAAnnotation",
    "GOAClient",
    "GOAClientProtocol",
    "StaticGOAClient",
    "parse_gaf",
]
