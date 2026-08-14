"""Pinned GO ontology loaders."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

from ._http import request

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None  # type: ignore[assignment]


class GOALoaderProtocol(Protocol):
    def load(self) -> Mapping[str, Mapping[str, object]]: ...


@dataclass
class StaticGOALoader:
    graph: Mapping[str, Mapping[str, object]]

    def load(self) -> Mapping[str, Mapping[str, object]]:
        return self.graph


class GOALoader:
    url = "https://current.geneontology.org/ontology/go-basic.obo"

    def __init__(self, *, session: object | None = None, timeout: float = 60.0) -> None:
        self.session = session or (requests.Session() if requests is not None else None)
        self.timeout = timeout

    def load(self) -> Mapping[str, Mapping[str, object]]:
        if self.session is None:
            raise RuntimeError("GOALoader requires the 'requests' dependency")
        response = request(
            self.session,
            "get",
            self.url,
            timeout=self.timeout,
            retries=2,
            backoff=0.5,
        )
        from thg_protocol.curation.go import parse_obo

        return parse_obo(response.text)


__all__ = ["GOALoader", "GOALoaderProtocol", "StaticGOALoader"]
