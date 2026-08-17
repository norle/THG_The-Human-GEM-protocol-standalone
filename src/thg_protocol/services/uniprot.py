"""Structured UniProt localization evidence adapters."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Protocol

from ._http import request

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None  # type: ignore[assignment]


@dataclass(frozen=True)
class UniProtAnnotation:
    gene_id: str
    protein_id: str = ""
    raw_location: str = ""
    go_id: str = ""
    evidence_code: str = ""
    reference: str = ""
    source_release: str = ""
    sl_id: str = ""


class UniProtClientProtocol(Protocol):
    def annotations_for(
        self, identifiers: Iterable[str]
    ) -> list[UniProtAnnotation]: ...


@dataclass
class StaticUniProtClient:
    annotations: list[UniProtAnnotation | Mapping[str, object]] = field(
        default_factory=list
    )

    def annotations_for(self, identifiers: Iterable[str]) -> list[UniProtAnnotation]:
        wanted = {str(item) for item in identifiers}
        result = []
        for raw in self.annotations:
            if isinstance(raw, UniProtAnnotation):
                items = [raw]
            else:
                mapping = raw.get("sl_to_go", {})
                sl_id = str(raw.get("sl_id", raw.get("location_id", "")))
                mapped = mapping.get(sl_id, []) if isinstance(mapping, Mapping) else []
                go_ids = mapped if isinstance(mapped, list) else [mapped]
                if raw.get("go_id"):
                    go_ids = [raw["go_id"]]
                items = [
                    UniProtAnnotation(
                        gene_id=str(raw.get("gene_id", raw.get("gene", ""))),
                        protein_id=str(raw.get("protein_id", raw.get("uniprot", ""))),
                        raw_location=str(
                            raw.get("raw_location", raw.get("location", ""))
                        ),
                        go_id=str(go_id),
                        evidence_code=str(raw.get("evidence_code", "")),
                        reference=str(raw.get("reference", "")),
                        source_release=str(raw.get("source_release", "")),
                        sl_id=sl_id,
                    )
                    for go_id in go_ids or [""]
                ]
            result.extend(
                item
                for item in items
                if item.gene_id in wanted or item.protein_id in wanted
            )
        return result


class UniProtClient(StaticUniProtClient):
    base_url = "https://rest.uniprot.org/uniprotkb/search"

    def __init__(
        self,
        *,
        session: object | None = None,
        timeout: float = 30.0,
        release: str = "",
        **kwargs: object,
    ):
        super().__init__(**kwargs)
        self.session = session or (requests.Session() if requests is not None else None)
        self.timeout = timeout
        self.source_release = release
        self.metadata: dict[str, object] = {}

    def annotations_for(self, identifiers: Iterable[str]) -> list[UniProtAnnotation]:
        wanted = [str(item) for item in identifiers]
        local = super().annotations_for(wanted)
        if local or not wanted:
            return local
        if self.session is None:
            raise RuntimeError("UniProtClient requires the 'requests' dependency")
        query = "+OR+".join(f"gene:{item}" for item in wanted)
        response = request(
            self.session,
            "get",
            self.base_url,
            timeout=self.timeout,
            retries=2,
            backoff=0.5,
            params={"query": query, "format": "json", "size": 500},
        )
        payload = response.json()
        self.metadata = {
            "source": "UniProt",
            "release": self.source_release,
            "url": self.base_url,
            "raw_response_sha256": hashlib.sha256(response.content).hexdigest(),
            "parser_version": "1",
        }
        records = payload.get("results", []) if isinstance(payload, Mapping) else []
        parsed = []
        for record in records:
            accession = str(record.get("primaryAccession", ""))
            genes = record.get("genes", [])
            names = [item.get("geneName", {}).get("value", "") for item in genes]
            for location in record.get("comments", []):
                if location.get("commentType") != "SUBCELLULAR LOCATION":
                    continue
                for value in location.get("subcellularLocations", []):
                    name = value.get("location", {}).get("value", "")
                    sl_id = str(value.get("location", {}).get("id", ""))
                    mappings = record.get("sl_to_go", {})
                    mapped = (
                        mappings.get(sl_id, [])
                        if isinstance(mappings, Mapping)
                        else []
                    )
                    parsed.extend(
                        UniProtAnnotation(
                            names[0] if names else accession,
                            accession,
                            str(name),
                            str(go_id),
                            source_release=self.source_release,
                            sl_id=sl_id,
                        )
                        for go_id in (mapped if isinstance(mapped, list) else [mapped])
                    )
                    if not mapped:
                        parsed.append(
                            UniProtAnnotation(
                                names[0] if names else accession,
                                accession,
                                str(name),
                                "",
                                source_release=self.source_release,
                                sl_id=sl_id,
                            )
                        )
        return parsed


__all__ = [
    "StaticUniProtClient",
    "UniProtAnnotation",
    "UniProtClient",
    "UniProtClientProtocol",
]
