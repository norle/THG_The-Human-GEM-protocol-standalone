"""Injectable Rhea reaction evidence boundary."""

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


class RheaClientProtocol(Protocol):
    def reactions_for_ec(self, ec_number: str) -> list[Mapping[str, object]]: ...
    def reaction(self, rhea_id: str) -> Mapping[str, object] | None: ...
    def proteins_for_reaction(self, rhea_id: str) -> list[Mapping[str, object]]: ...


@dataclass
class StaticRheaClient:
    by_ec: dict[str, list[Mapping[str, object]]] = field(default_factory=dict)
    reactions: dict[str, Mapping[str, object]] = field(default_factory=dict)
    proteins: dict[str, list[Mapping[str, object]]] = field(default_factory=dict)
    release: str = ""

    def reactions_for_ec(self, ec_number: str) -> list[Mapping[str, object]]:
        return list(self.by_ec.get(str(ec_number), ()))

    def reaction(self, rhea_id: str) -> Mapping[str, object] | None:
        return self.reactions.get(str(rhea_id))

    def proteins_for_reaction(self, rhea_id: str) -> list[Mapping[str, object]]:
        return list(self.proteins.get(str(rhea_id), ()))


class RheaClient(StaticRheaClient):
    """Small JSON adapter; a supplied snapshot remains the preferred input."""

    base_url = "https://www.rhea-db.org"

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
            raise RuntimeError("RheaClient requires the 'requests' dependency")
        response = request(
            self.session,
            "get",
            self.base_url + path,
            timeout=self.timeout,
            retries=2,
            backoff=0.5,
        )
        self.metadata = {
            "source": "Rhea",
            "release": self.source_release,
            "url": self.base_url + path,
            "raw_response_sha256": hashlib.sha256(response.content).hexdigest(),
            "parser_version": "1",
        }
        return response.json()

    def reactions_for_ec(self, ec_number: str) -> list[Mapping[str, object]]:
        local = super().reactions_for_ec(ec_number)
        if local:
            return local
        payload = self._remote(f"/rhea/?query=ec:{ec_number}&format=json")
        return (
            list(payload)
            if isinstance(payload, list)
            else list(payload.get("results", []))
            if isinstance(payload, Mapping)
            else []
        )

    def reaction(self, rhea_id: str) -> Mapping[str, object] | None:
        local = super().reaction(rhea_id)
        if local is not None:
            return local
        payload = self._remote(f"/rhea/{rhea_id}?format=json")
        return payload if isinstance(payload, Mapping) else None

    def proteins_for_reaction(self, rhea_id: str) -> list[Mapping[str, object]]:
        local = super().proteins_for_reaction(rhea_id)
        if local:
            return local
        value = self.reaction(rhea_id) or {}
        proteins = value.get("proteins", [])
        return list(proteins) if isinstance(proteins, list) else []


__all__ = ["RheaClient", "RheaClientProtocol", "StaticRheaClient"]
