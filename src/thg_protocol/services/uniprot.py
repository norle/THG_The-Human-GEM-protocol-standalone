"""Structured UniProt localization evidence adapters."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Protocol

try:
    from tqdm import tqdm
except ImportError:  # pragma: no cover - exercised by clean-wheel checks
    def tqdm(iterable: Iterable[object], **_kwargs: object) -> Iterable[object]:
        return iterable

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
        self, identifiers: Iterable[str], *, progress: bool = False
    ) -> list[UniProtAnnotation]: ...


@dataclass
class StaticUniProtClient:
    annotations: list[UniProtAnnotation | Mapping[str, object]] = field(
        default_factory=list
    )

    def annotations_for(
        self, identifiers: Iterable[str], *, progress: bool = False
    ) -> list[UniProtAnnotation]:
        del progress
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

    def annotations_for(
        self, identifiers: Iterable[str], *, progress: bool = False
    ) -> list[UniProtAnnotation]:
        wanted = sorted(
            {str(item).strip() for item in identifiers} - {""}
        )
        local = super().annotations_for(wanted)
        if local or not wanted:
            return local
        if self.session is None:
            raise RuntimeError("UniProtClient requires the 'requests' dependency")
        records = []
        raw_response = hashlib.sha256()
        for start in tqdm(
            range(0, len(wanted), 100),
            desc="UniProt locations",
            unit="batch",
            disable=not progress,
        ):
            query = " OR ".join(
                (
                    f"xref:ensembl-{item}"
                    if item.startswith("ENS")
                    else f"gene:{item}"
                )
                for item in wanted[start : start + 100]
            )
            response = request(
                self.session,
                "get",
                self.base_url,
                timeout=self.timeout,
                retries=2,
                backoff=0.5,
                params={"query": query, "format": "json", "size": 500},
            )
            raw_response.update(response.content)
            payload = response.json()
            if isinstance(payload, Mapping):
                records.extend(payload.get("results", []))
        self.metadata = {
            "source": "UniProt",
            "release": self.source_release,
            "url": self.base_url,
            "raw_response_sha256": raw_response.hexdigest(),
            "parser_version": "1",
        }
        parsed = []
        for record in records:
            accession = str(record.get("primaryAccession", ""))
            genes = record.get("genes", [])
            names = [item.get("geneName", {}).get("value", "") for item in genes]
            identifiers = {accession, *names}
            for reference in record.get("uniProtKBCrossReferences", []):
                if (
                    not isinstance(reference, Mapping)
                    or reference.get("database") != "Ensembl"
                ):
                    continue
                for value in [
                    reference.get("id", ""),
                    *(
                        property_.get("value", "")
                        for property_ in reference.get("properties", [])
                        if isinstance(property_, Mapping)
                    ),
                ]:
                    identifier = str(value)
                    identifiers.update((identifier, identifier.split(".", 1)[0]))
            gene_ids = sorted(set(wanted) & identifiers) or [
                names[0] if names else accession
            ]
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
                    for gene_id in gene_ids:
                        parsed.extend(
                            UniProtAnnotation(
                                gene_id,
                                accession,
                                str(name),
                                str(go_id),
                                source_release=self.source_release,
                                sl_id=sl_id,
                            )
                            for go_id in (
                                mapped if isinstance(mapped, list) else [mapped]
                            )
                        )
                        if not mapped:
                            parsed.append(
                                UniProtAnnotation(
                                    gene_id,
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
