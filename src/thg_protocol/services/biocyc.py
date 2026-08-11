"""Injectable BioCyc client boundary used by GPR workflows."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from ._http import request

try:  # Keep imports safe in a minimal installed wheel.
    import requests
except ImportError:  # pragma: no cover - exercised by clean-wheel checks
    requests = None  # type: ignore[assignment]


class BioCycError(RuntimeError):
    """Normalized BioCyc request failure."""


class BioCycClientProtocol(Protocol):
    """Boundary for the small set of BioCyc pages used by GPR parsing."""

    def get_ec_html(self, ec_number: str, org: str = "META") -> str: ...

    def get_page(self, url: str) -> str: ...


@dataclass
class StaticBioCycClient:
    """Offline client keyed by ``(org, EC)`` and absolute page URL."""

    ec_pages: dict[tuple[str, str], str] = field(default_factory=dict)
    pages: dict[str, str] = field(default_factory=dict)

    def get_ec_html(self, ec_number: str, org: str = "META") -> str:
        return self.ec_pages.get((org.upper(), str(ec_number)), "")

    def get_page(self, url: str) -> str:
        return self.pages.get(url, "")


class BioCycClient:
    """BioCyc HTTP adapter with explicit timeout, retry, and page caching."""

    def __init__(
        self,
        *,
        session: requests.Session | None = None,
        timeout: float = 30.0,
        retries: int = 3,
        backoff: float = 0.5,
    ) -> None:
        if requests is None:
            raise RuntimeError("BioCycClient requires the 'requests' dependency")
        self.session = session or requests.Session()
        self.timeout = timeout
        self.retries = max(0, retries)
        self.backoff = max(0.0, backoff)
        self._cache: dict[str, str] = {}

    def _get(self, url: str) -> str:
        if url in self._cache:
            return self._cache[url]
        try:
            response = request(
                self.session, "get", url, timeout=self.timeout,
                retries=self.retries, backoff=self.backoff,
            )
        except requests.RequestException as error:
            raise BioCycError(f"BioCyc request failed for {url}") from error
        self._cache[url] = response.text
        return response.text

    def get_ec_html(self, ec_number: str, org: str = "META") -> str:
        return self._get(
            f"https://websvc.biocyc.org/{org}/NEW-IMAGE?type=EC-NUMBER&object=EC-{ec_number}"
        )

    def get_page(self, url: str) -> str:
        return self._get(url)
