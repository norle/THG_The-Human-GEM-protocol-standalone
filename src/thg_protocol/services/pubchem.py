"""Injectable PubChem client boundary used by annotation workflows."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Protocol

try:  # Keep package imports and CLI help safe in a --no-deps wheel smoke test.
    import requests
except ImportError:  # pragma: no cover - exercised by minimal clean wheels
    requests = None  # type: ignore[assignment]


class PubChemError(RuntimeError):
    """Normalized PubChem request or response error."""


@dataclass(frozen=True)
class PubChemCompound:
    """Normalized subset of compound data needed by THG annotation."""

    cid: int
    molecular_formula: str = ""
    synonyms: tuple[str, ...] = ()
    inchi: str = ""
    inchikey: str = ""


class PubChemClientProtocol(Protocol):
    """Small boundary that can be replaced with a static fake in tests."""

    def get_compound(self, name: str) -> PubChemCompound | None: ...


@dataclass
class StaticPubChemClient:
    """Offline client backed by normalized compounds or plain mappings."""

    compounds: dict[str, PubChemCompound | dict[str, Any]] = field(default_factory=dict)

    def get_compound(self, name: str) -> PubChemCompound | None:
        value = self.compounds.get(name)
        if value is None:
            value = self.compounds.get(name.strip())
        if value is None:
            return None
        if isinstance(value, PubChemCompound):
            return value
        return PubChemCompound(
            cid=int(value["cid"]),
            molecular_formula=value.get("molecular_formula", value.get("formula", "")),
            synonyms=tuple(value.get("synonyms", ())),
            inchi=value.get("inchi", ""),
            inchikey=value.get("inchikey", ""),
        )


class PubChemClient:
    """PUG REST client with timeout, retry, and in-process caching."""

    def __init__(
        self,
        *,
        session: requests.Session | None = None,
        timeout: float = 15.0,
        retries: int = 3,
        backoff: float = 0.5,
        min_interval: float = 0.2,
    ):
        if requests is None:
            raise RuntimeError("PubChemClient requires the 'requests' dependency")
        self.session = session or requests.Session()
        self.timeout = timeout
        self.retries = max(0, retries)
        self.backoff = max(0.0, backoff)
        self.min_interval = max(0.0, min_interval)
        self._last_request = 0.0
        self._cache: dict[str, PubChemCompound | None] = {}

    def get_compound(self, name: str) -> PubChemCompound | None:
        key = name.strip()
        if key in self._cache:
            return self._cache[key]
        url = (
            "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/"
            + requests.utils.quote(key, safe="")
            + "/property/MolecularFormula,InChI,InChIKey/JSON"
        )
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                wait = self.min_interval - (time.monotonic() - self._last_request)
                if wait > 0:
                    time.sleep(wait)
                self._last_request = time.monotonic()
                response = self.session.get(url, timeout=self.timeout)
                if response.status_code == 404:
                    self._cache[key] = None
                    return None
                response.raise_for_status()
                properties = (
                    response.json().get("PropertyTable", {}).get("Properties", [])
                )
                if not properties:
                    self._cache[key] = None
                    return None
                item = properties[0]
                wait = self.min_interval - (time.monotonic() - self._last_request)
                if wait > 0:
                    time.sleep(wait)
                self._last_request = time.monotonic()
                synonyms_response = self.session.get(
                    f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{item['CID']}/synonyms/JSON",
                    timeout=self.timeout,
                )
                synonyms_response.raise_for_status()
                synonyms = (
                    synonyms_response.json()
                    .get("InformationList", {})
                    .get("Information", [{}])[0]
                    .get("Synonym", [])
                )
                compound = PubChemCompound(
                    cid=int(item["CID"]),
                    molecular_formula=item.get("MolecularFormula", ""),
                    synonyms=tuple(synonyms),
                    inchi=item.get("InChI", ""),
                    inchikey=item.get("InChIKey", ""),
                )
                self._cache[key] = compound
                return compound
            except (requests.RequestException, ValueError, KeyError) as error:
                last_error = error
                if attempt < self.retries:
                    time.sleep(self.backoff * (2**attempt))
        raise PubChemError(f"PubChem lookup failed for {name!r}") from last_error
