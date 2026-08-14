"""Structured UniProt localization evidence adapters."""

from __future__ import annotations

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
            item = (
                raw
                if isinstance(raw, UniProtAnnotation)
                else UniProtAnnotation(
                    gene_id=str(raw.get("gene_id", raw.get("gene", ""))),
                    protein_id=str(raw.get("protein_id", raw.get("uniprot", ""))),
                    raw_location=str(raw.get("raw_location", raw.get("location", ""))),
                    go_id=str(raw.get("go_id", "")),
                    evidence_code=str(raw.get("evidence_code", "")),
                    reference=str(raw.get("reference", "")),
                    source_release=str(raw.get("source_release", "")),
                )
            )
            if item.gene_id in wanted or item.protein_id in wanted:
                result.append(item)
        return result


class UniProtClient(StaticUniProtClient):
    base_url = "https://rest.uniprot.org/uniprotkb/search"

    def __init__(
        self, *, session: object | None = None, timeout: float = 30.0, **kwargs: object
    ):
        super().__init__(**kwargs)
        self.session = session or (requests.Session() if requests is not None else None)
        self.timeout = timeout

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
        ).json()
        records = response.get("results", []) if isinstance(response, Mapping) else []
        parsed = []
        for record in records:
            accession = str(record.get("primaryAccession", ""))
            genes = record.get("genes", [])
            names = [item.get("geneName", {}).get("value", "") for item in genes]
            go_ids = [
                str(item.get("id", ""))
                for item in record.get("uniProtKBCrossReferences", [])
                if item.get("database") == "GO" and item.get("id")
            ]
            for location in record.get("comments", []):
                if location.get("commentType") != "SUBCELLULAR LOCATION":
                    continue
                for value in location.get("subcellularLocations", []):
                    name = value.get("location", {}).get("value", "")
                    parsed.extend(
                        UniProtAnnotation(
                            names[0] if names else accession,
                            accession,
                            str(name),
                            go_id,
                        )
                        for go_id in go_ids or [""]
                    )
        return parsed


__all__ = [
    "StaticUniProtClient",
    "UniProtAnnotation",
    "UniProtClient",
    "UniProtClientProtocol",
]
