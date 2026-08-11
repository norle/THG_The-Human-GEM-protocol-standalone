"""Injectable Ensembl annotation client used by THG workflows."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from typing import Any, Protocol

from ._http import request

try:  # Keep package imports safe for no-dependency wheel smoke tests.
    import requests
except ImportError:  # pragma: no cover - exercised by minimal clean wheels
    requests = None  # type: ignore[assignment]


class EnsemblError(RuntimeError):
    """Normalized Ensembl request or response error."""


@dataclass(frozen=True)
class EnsemblAnnotation:
    """Normalized annotation returned for a gene identifier."""

    ensembl: str
    display_name: str | None = None
    biotype: str | None = None
    description: str | None = None
    entrez: tuple[str, ...] = ()
    uniprot: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        """Return the legacy-compatible, JSON-serializable representation."""
        value = asdict(self)
        value["entrez"] = list(self.entrez)
        value["uniprot"] = list(self.uniprot)
        return value


class EnsemblClientProtocol(Protocol):
    """Small annotation boundary that can be replaced with a static fake."""

    def annotate(self, identifiers: Iterable[str]) -> dict[str, EnsemblAnnotation]: ...


@dataclass
class StaticEnsemblClient:
    """Offline client backed by normalized annotations or plain mappings."""

    annotations: dict[str, EnsemblAnnotation | dict[str, Any]] = field(
        default_factory=dict
    )

    def annotate(self, identifiers: Iterable[str]) -> dict[str, EnsemblAnnotation]:
        result: dict[str, EnsemblAnnotation] = {}
        for identifier in identifiers:
            key = str(identifier).strip()
            value = self.annotations.get(key)
            if value is None:
                continue
            if isinstance(value, EnsemblAnnotation):
                result[key] = value
                continue
            result[key] = EnsemblAnnotation(
                ensembl=str(value["ensembl"]),
                display_name=value.get("display_name"),
                biotype=value.get("biotype"),
                description=value.get("description"),
                entrez=tuple(str(item) for item in value.get("entrez", ())),
                uniprot=tuple(str(item) for item in value.get("uniprot", ())),
            )
        return result


class EnsemblClient:
    """Ensembl REST client with explicit timeout, retries, and caching."""

    base_url = "https://rest.ensembl.org"

    def __init__(
        self,
        *,
        session: requests.Session | None = None,
        timeout: float = 15.0,
        retries: int = 3,
        backoff: float = 0.5,
    ) -> None:
        if requests is None:
            raise RuntimeError("EnsemblClient requires the 'requests' dependency")
        self.session = session or requests.Session()
        self.timeout = timeout
        self.retries = max(0, retries)
        self.backoff = max(0.0, backoff)
        self._cache: dict[str, EnsemblAnnotation | None] = {}

    def _request(self, method: str, path: str) -> Any:
        url = f"{self.base_url}{path}"
        try:
            response = request(
                self.session, method.lower(), url, timeout=self.timeout,
                retries=self.retries, backoff=self.backoff,
                headers={"Accept": "application/json"},
            )
            return response.json()
        except requests.HTTPError as error:
            if error.response is not None and error.response.status_code == 404:
                return None
            raise EnsemblError(f"Ensembl request failed for {path}") from error
        except (requests.RequestException, ValueError) as error:
            raise EnsemblError(f"Ensembl request failed for {path}") from error

    @staticmethod
    def _annotation(payload: dict[str, Any]) -> EnsemblAnnotation | None:
        identifier = payload.get("id")
        if not identifier:
            return None
        return EnsemblAnnotation(
            ensembl=str(identifier),
            display_name=payload.get("display_name"),
            biotype=payload.get("biotype"),
            description=payload.get("description"),
        )

    def _xrefs(self, ensembl_id: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
        payload = self._request("GET", f"/xrefs/id/{ensembl_id}") or []
        entrez: set[str] = set()
        uniprot: set[str] = set()
        for item in payload:
            database = str(
                item.get("dbname") or item.get("db_display_name") or ""
            ).lower()
            primary_id = item.get("primary_id")
            if not primary_id:
                continue
            if "entrez" in database or "ncbigene" in database:
                entrez.add(str(primary_id))
            if database.startswith("uniprot") or "uniprot" in database:
                uniprot.add(str(primary_id))
        return tuple(sorted(entrez)), tuple(sorted(uniprot))

    def _lookup(self, identifier: str) -> EnsemblAnnotation | None:
        path = (
            f"/lookup/id/{identifier}"
            if identifier.startswith("ENS") and identifier[3:].isalnum()
            else f"/lookup/symbol/homo_sapiens/{identifier}"
        )
        payload = self._request("GET", path)
        if payload is None:
            return None
        annotation = self._annotation(payload)
        if annotation is None:
            return None
        entrez, uniprot = self._xrefs(annotation.ensembl)
        return EnsemblAnnotation(
            ensembl=annotation.ensembl,
            display_name=annotation.display_name,
            biotype=annotation.biotype,
            description=annotation.description,
            entrez=entrez,
            uniprot=uniprot,
        )

    def annotate(self, identifiers: Iterable[str]) -> dict[str, EnsemblAnnotation]:
        """Annotate identifiers, omitting entries that Ensembl cannot resolve."""
        result: dict[str, EnsemblAnnotation] = {}
        for raw_identifier in identifiers:
            identifier = str(raw_identifier).strip()
            if not identifier:
                continue
            if identifier not in self._cache:
                self._cache[identifier] = self._lookup(identifier)
            annotation = self._cache[identifier]
            if annotation is not None:
                result[identifier] = annotation
        return result
