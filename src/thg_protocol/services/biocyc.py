"""Injectable BioCyc client boundary used by GPR workflows."""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Mapping
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

    def get_cco(self, identifier: str) -> Mapping[str, object] | None: ...


@dataclass
class StaticBioCycClient:
    """Offline client keyed by ``(org, EC)`` and absolute page URL."""

    ec_pages: dict[tuple[str, str], str] = field(default_factory=dict)
    pages: dict[str, str] = field(default_factory=dict)
    cco_terms: dict[str, Mapping[str, object]] = field(default_factory=dict)
    cco_graph: dict[str, Mapping[str, object]] = field(default_factory=dict)

    def get_ec_html(self, ec_number: str, org: str = "META") -> str:
        return self.ec_pages.get((org.upper(), str(ec_number)), "")

    def get_page(self, url: str) -> str:
        return self.pages.get(url, "")

    def get_cco(self, identifier: str) -> Mapping[str, object] | None:
        return (self.cco_terms or self.cco_graph).get(str(identifier))


class BioCycClient:
    """BioCyc HTTP adapter with explicit timeout, retry, and page caching."""

    base_url = "https://websvc.biocyc.org"

    def __init__(
        self,
        *,
        session: requests.Session | None = None,
        timeout: float = 30.0,
        retries: int = 3,
        backoff: float = 0.5,
        email: str | None = None,
        password: str | None = None,
        release: str = "",
    ) -> None:
        if requests is None:
            raise RuntimeError("BioCycClient requires the 'requests' dependency")
        self.session = session or requests.Session()
        self.timeout = timeout
        self.retries = max(0, retries)
        self.backoff = max(0.0, backoff)
        self._cache: dict[str, str] = {}
        self.source_release = release
        self.metadata: dict[str, object] = {}
        email = email if email is not None else os.environ.get("BIOCYC_EMAIL")
        password = (
            password if password is not None else os.environ.get("BIOCYC_PASSWORD")
        )
        if bool(email) != bool(password):
            raise BioCycError("BioCyc email and password must be provided together")
        if email and password:
            self._login(email, password)

    def _login(self, email: str, password: str) -> None:
        try:
            response = request(
                self.session,
                "post",
                f"{self.base_url}/ajax-login",
                timeout=self.timeout,
                retries=self.retries,
                backoff=self.backoff,
                data={"email": email, "password": password},
            )
            payload = response.json()
        except (requests.RequestException, ValueError) as error:
            raise BioCycError("BioCyc login failed") from error
        if not isinstance(payload, Mapping) or not payload.get("success"):
            raise BioCycError("BioCyc login failed")

    def _get(self, url: str) -> str:
        if url in self._cache:
            return self._cache[url]
        try:
            response = request(
                self.session,
                "get",
                url,
                timeout=self.timeout,
                retries=self.retries,
                backoff=self.backoff,
            )
        except requests.RequestException as error:
            raise BioCycError(f"BioCyc request failed for {url}") from error
        self._cache[url] = response.text
        self.metadata = {
            "source": "BioCyc",
            "release": self.source_release,
            "url": url,
            "raw_response_sha256": hashlib.sha256(
                getattr(response, "content", response.text.encode())
            ).hexdigest(),
            "parser_version": "1",
        }
        return response.text

    def get_ec_html(self, ec_number: str, org: str = "META") -> str:
        return self._get(
            f"{self.base_url}/{org}/NEW-IMAGE?type=EC-NUMBER&object=EC-{ec_number}"
        )

    def get_page(self, url: str) -> str:
        return self._get(url)

    def get_cco(self, identifier: str) -> Mapping[str, object] | None:
        """Retrieve a normalized CCO term when a live caller requests it."""
        try:
            payload = json.loads(
                self._get(f"{self.base_url}/ONTOLOGY?object={identifier}")
            )
        except (TypeError, json.JSONDecodeError):
            return None
        return payload if isinstance(payload, Mapping) else None
