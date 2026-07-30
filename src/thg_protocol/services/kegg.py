"""Injectable KEGG client boundary used by GPR workflows."""

from __future__ import annotations

import re
import time
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Protocol

try:  # Keep imports safe in a minimal installed wheel.
    import requests
except ImportError:  # pragma: no cover - exercised by clean-wheel checks
    requests = None  # type: ignore[assignment]


class KeggError(RuntimeError):
    """Normalized KEGG request failure."""


class KeggClientProtocol(Protocol):
    """Boundary for KEGG pages, entries, and GPR fallback lookups."""

    def get_page(self, url: str) -> str: ...

    def get_entries(
        self,
        kegg_ids: Iterable[str],
        *,
        database: str = "compound",
        batch_size: int = 10,
        requests_per_second: float = 3,
    ) -> dict[str, str]: ...

    def get_ec_html(self, ec_number: str) -> str: ...

    def link_ec_to_ko(self, ec_number: str) -> str: ...

    def link_ko_to_genes(self, ko_identifiers: list[str]) -> str: ...

    def get_reaction_entries(
        self,
        kegg_ids: Iterable[str],
        *,
        batch_size: int = 10,
        requests_per_second: float = 3,
    ) -> dict[str, str]: ...


@dataclass
class StaticKeggClient:
    """Offline KEGG response adapter, keyed by normalized request inputs."""

    ec_pages: dict[str, str] = field(default_factory=dict)
    ec_to_ko: dict[str, str] = field(default_factory=dict)
    ko_to_genes: dict[tuple[str, ...], str] = field(default_factory=dict)
    reaction_entries: dict[str, str] = field(default_factory=dict)
    pages: dict[str, str] = field(default_factory=dict)
    entries: dict[str, str] = field(default_factory=dict)

    def get_page(self, url: str) -> str:
        return self.pages.get(url, "")

    def get_entries(
        self,
        kegg_ids: Iterable[str],
        *,
        database: str = "compound",
        batch_size: int = 10,
        requests_per_second: float = 3,
    ) -> dict[str, str]:
        del database, batch_size, requests_per_second
        values = {**self.entries, **self.reaction_entries}
        return {
            str(kegg_id): values[str(kegg_id)]
            for kegg_id in kegg_ids
            if str(kegg_id) in values
        }

    def get_ec_html(self, ec_number: str) -> str:
        return self.ec_pages.get(str(ec_number), "")

    def link_ec_to_ko(self, ec_number: str) -> str:
        return self.ec_to_ko.get(str(ec_number), "")

    def link_ko_to_genes(self, ko_identifiers: list[str]) -> str:
        return self.ko_to_genes.get(tuple(ko_identifiers), "")

    def get_reaction_entries(
        self,
        kegg_ids: Iterable[str],
        *,
        batch_size: int = 10,
        requests_per_second: float = 3,
    ) -> dict[str, str]:
        return self.get_entries(
            kegg_ids,
            database="reaction",
            batch_size=batch_size,
            requests_per_second=requests_per_second,
        )


class KeggClient:
    """KEGG REST/DBGET adapter with explicit timeout, retry, and caching."""

    def __init__(
        self,
        *,
        session: requests.Session | None = None,
        timeout: float = 30.0,
        retries: int = 3,
        backoff: float = 0.5,
    ) -> None:
        if requests is None:
            raise RuntimeError("KeggClient requires the 'requests' dependency")
        self.session = session or requests.Session()
        self.timeout = timeout
        self.retries = max(0, retries)
        self.backoff = max(0.0, backoff)
        self._cache: dict[str, str] = {}
        self._reaction_cache: dict[tuple[str, str], str | None] = {}

    def _get(self, url: str) -> str:
        if url in self._cache:
            return self._cache[url]
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                response = self.session.get(url, timeout=self.timeout)
                response.raise_for_status()
                self._cache[url] = response.text
                return response.text
            except requests.RequestException as error:
                last_error = error
                if attempt < self.retries:
                    time.sleep(self.backoff * (2**attempt))
        raise KeggError(f"KEGG request failed for {url}") from last_error

    def get_ec_html(self, ec_number: str) -> str:
        return self._get(f"http://www.genome.jp/dbget-bin/www_bget?ec:{ec_number}")

    def get_page(self, url: str) -> str:
        return self._get(url)

    def link_ec_to_ko(self, ec_number: str) -> str:
        return self._get(f"https://rest.kegg.jp/link/ko/ec:{ec_number}")

    def link_ko_to_genes(self, ko_identifiers: list[str]) -> str:
        return self._get(f"https://rest.kegg.jp/link/genes/{'+'.join(ko_identifiers)}")

    def get_reaction_entries(
        self,
        kegg_ids: Iterable[str],
        *,
        batch_size: int = 10,
        requests_per_second: float = 3,
    ) -> dict[str, str]:
        """Fetch and parse one or more KEGG reaction entries.

        KEGG accepts several reaction IDs in a single ``get`` request. The
        client owns batching, pacing, retries, and response caching so
        workflows only receive a normalized reaction-ID-to-entry mapping.
        """
        return self.get_entries(
            kegg_ids,
            database="reaction",
            batch_size=min(batch_size, 10),
            requests_per_second=requests_per_second,
        )

    def get_entries(
        self,
        kegg_ids: Iterable[str],
        *,
        database: str = "compound",
        batch_size: int = 10,
        requests_per_second: float = 3,
    ) -> dict[str, str]:
        if batch_size < 1:
            raise ValueError("batch_size must be positive")
        if requests_per_second <= 0:
            raise ValueError("requests_per_second must be positive")

        # KEGG's multi-entry ``get`` endpoint accepts at most ten identifiers.
        # Keep callers that historically supplied a larger value safe as well.
        batch_size = min(batch_size, 10)
        identifiers = list(dict.fromkeys(str(kegg_id).strip() for kegg_id in kegg_ids))
        identifiers = [identifier for identifier in identifiers if identifier]
        results: dict[str, str] = {}
        missing = [
            identifier
            for identifier in identifiers
            if (database, identifier) not in self._reaction_cache
        ]
        last_request_at: float | None = None
        minimum_delay = 1.0 / requests_per_second

        for start in range(0, len(missing), batch_size):
            batch = missing[start : start + batch_size]
            if last_request_at is not None:
                remaining = minimum_delay - (time.monotonic() - last_request_at)
                if remaining > 0:
                    time.sleep(remaining)

            prefix = {"compound": "cpd:", "glycan": "gl:", "reaction": "rn:"}.get(
                database, ""
            )
            query = "+".join(f"{prefix}{identifier}" for identifier in batch)
            text = self._get(f"https://rest.kegg.jp/get/{query}")
            last_request_at = time.monotonic()
            for entry in re.split(r"(?:///|\n(?=ENTRY\s+[A-Z]))", text):
                match = re.search(r"ENTRY\s+([A-Z][0-9]+)", entry)
                if match:
                    results[match.group(1)] = entry
            for identifier in batch:
                self._reaction_cache[(database, identifier)] = results.get(identifier)

        results = {
            identifier: self._reaction_cache[(database, identifier)]
            for identifier in identifiers
            if self._reaction_cache.get((database, identifier)) is not None
        }
        return results
