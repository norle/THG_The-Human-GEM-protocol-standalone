"""HTTP boundary for the legacy subcellular-location workflow."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol

from ._http import request

try:
    import requests
except ImportError:  # pragma: no cover - exercised by minimal wheel checks
    requests = None  # type: ignore[assignment]


class LocationError(RuntimeError):
    """Normalized location-page request failure."""


class LocationClientProtocol(Protocol):
    """Boundary for pages consulted by the location resolver."""

    def get_page(self, url: str) -> str: ...

    def post_page(self, url: str, *, files: Mapping[str, Any]) -> str: ...


@dataclass
class StaticLocationClient:
    """Offline location client keyed by absolute URL."""

    pages: dict[str, str] = field(default_factory=dict)
    uploads: dict[str, str] = field(default_factory=dict)

    def get_page(self, url: str) -> str:
        return self.pages.get(url, "")

    def post_page(self, url: str, *, files: Mapping[str, Any]) -> str:
        del files
        return self.uploads.get(url, "")


class LocationClient:
    """Generic HTTP adapter with timeout, retries, and response caching."""

    def __init__(
        self,
        *,
        session: requests.Session | None = None,
        timeout: float = 30.0,
        retries: int = 3,
        backoff: float = 0.5,
    ) -> None:
        if requests is None:
            raise RuntimeError("LocationClient requires the 'requests' dependency")
        self.session = session or requests.Session()
        self.timeout = timeout
        self.retries = max(0, retries)
        self.backoff = max(0.0, backoff)
        self._cache: dict[str, str] = {}

    def get_page(self, url: str) -> str:
        if url in self._cache:
            return self._cache[url]
        try:
            response = request(
                self.session, "get", url, timeout=self.timeout,
                retries=self.retries, backoff=self.backoff,
            )
        except requests.RequestException as error:
            raise LocationError(f"Location request failed for {url}") from error
        self._cache[url] = response.text
        return response.text

    def post_page(self, url: str, *, files: Mapping[str, Any]) -> str:
        """Upload files through the same retry/timeout boundary as page reads."""
        if requests is None:  # pragma: no cover - guarded by __init__
            raise RuntimeError("LocationClient requires the 'requests' dependency")
        try:
            return request(
                self.session, "post", url, files=files, timeout=self.timeout,
                retries=self.retries, backoff=self.backoff,
            ).text
        except requests.RequestException as error:
            raise LocationError(f"Location upload failed for {url}") from error
