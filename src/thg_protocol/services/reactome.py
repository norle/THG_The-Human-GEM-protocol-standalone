"""Injectable Reactome reaction and catalyst evidence boundary."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Protocol

from ._http import request

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None  # type: ignore[assignment]


class ReactomeClientProtocol(Protocol):
    def reactions_for_rhea(self, rhea_id: str) -> list[Mapping[str, object]]: ...
    def reaction(self, reactome_id: str) -> Mapping[str, object] | None: ...


@dataclass
class StaticReactomeClient:
    by_rhea: dict[str, list[Mapping[str, object]]] = field(default_factory=dict)
    reactions: dict[str, Mapping[str, object]] = field(default_factory=dict)

    def reactions_for_rhea(self, rhea_id: str) -> list[Mapping[str, object]]:
        return list(self.by_rhea.get(str(rhea_id), ()))

    def reaction(self, reactome_id: str) -> Mapping[str, object] | None:
        return self.reactions.get(str(reactome_id))


def catalyst_candidate_gpr(record: Mapping[str, object]) -> str:
    """Render explicit Reactome catalyst structure without inventing ANDs."""
    catalyst = record.get("catalyst", record.get("catalyst_activity", {}))
    if not isinstance(catalyst, Mapping):
        return ""
    members = catalyst.get("members", catalyst.get("proteins", []))
    if not isinstance(members, list):
        return ""
    genes = sorted(
        {
            str(item.get("gene", item.get("gene_symbol", item.get("symbol", ""))))
            for item in members
            if isinstance(item, Mapping)
            and item.get("gene", item.get("gene_symbol", item.get("symbol")))
        }
    )
    if not genes:
        return ""
    catalyst_type = str(catalyst.get("type", "")).lower()
    if catalyst_type in {"complex", "protein-complex"}:
        operator = " and "
    elif catalyst_type in {
        "entity-set",
        "entity set",
        "alternative",
        "alternatives",
        "isoenzyme",
    }:
        operator = " or "
    else:
        return ""
    return operator.join(f"({gene})" for gene in genes)


class ReactomeClient(StaticReactomeClient):
    base_url = "https://reactome.org/ContentService/data"

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

    def _remote(self, path: str) -> object:
        if self.session is None:
            raise RuntimeError("ReactomeClient requires the 'requests' dependency")
        response = request(
            self.session,
            "get",
            self.base_url + path,
            timeout=self.timeout,
            retries=2,
            backoff=0.5,
        )
        self.metadata = {
            "source": "Reactome",
            "release": self.source_release,
            "url": self.base_url + path,
            "raw_response_sha256": hashlib.sha256(response.content).hexdigest(),
            "parser_version": "1",
        }
        return response.json()

    def reactions_for_rhea(self, rhea_id: str) -> list[Mapping[str, object]]:
        local = super().reactions_for_rhea(rhea_id)
        if local:
            return local
        payload = self._remote(f"/search/query?query={rhea_id}")
        return list(payload.get("results", [])) if isinstance(payload, Mapping) else []

    def reaction(self, reactome_id: str) -> Mapping[str, object] | None:
        local = super().reaction(reactome_id)
        if local is not None:
            return local
        payload = self._remote(f"/query/{reactome_id}")
        return payload if isinstance(payload, Mapping) else None


__all__ = [
    "ReactomeClient",
    "ReactomeClientProtocol",
    "StaticReactomeClient",
    "catalyst_candidate_gpr",
]
