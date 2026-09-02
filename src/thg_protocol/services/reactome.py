"""Injectable Reactome reaction and catalyst evidence boundary."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Protocol
from urllib.parse import quote, urlencode

from thg_protocol.gpr.evidence import SgprEvidence
from thg_protocol.gpr.stoichiometry import (
    AndNode,
    GeneNode,
    OrNode,
    SgprNode,
    normalize_sgpr,
)

from ._http import _UnavailableRequestMixin, request

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
    evidence = catalyst_sgpr(record)
    if evidence.sgpr is None:
        return ""

    def render(node: SgprNode) -> str:
        if isinstance(node, GeneNode):
            return f"({node.gene})"
        operator = " and " if isinstance(node, AndNode) else " or "
        return operator.join(render(child) for child in node.children)

    return render(evidence.sgpr)


def _member_node(value: object, source: str = "reactome") -> SgprNode | None:
    if not isinstance(value, Mapping):
        return None
    gene = value.get("gene", value.get("gene_symbol", value.get("symbol")))
    nested = value.get("catalyst", value.get("catalyst_activity"))
    if nested is None and value.get("type"):
        nested = value
    if isinstance(nested, Mapping):
        node = _catalyst_node(nested, source)
        if node is not None:
            return node
    if not gene:
        return None
    coefficient = value.get(
        "coefficient", value.get("stoichiometry", value.get("count"))
    )
    if coefficient is not None:
        try:
            coefficient = int(coefficient)
        except (TypeError, ValueError):
            coefficient = None
    return GeneNode(
        str(gene),
        coefficient,
        "observed" if coefficient is not None else "unknown",
        source,
        tuple(str(item) for item in value.get("evidence", ()) or ()),
    )


def _catalyst_node(
    catalyst: Mapping[str, object], source: str = "reactome"
) -> SgprNode | None:
    catalyst_type = (
        str(catalyst.get("type", catalyst.get("class", ""))).lower().replace("_", "-")
    )
    if catalyst_type in {"complex", "protein-complex"}:
        cls = AndNode
    elif catalyst_type in {
        "entity-set",
        "entity set",
        "alternative",
        "alternatives",
        "isoenzyme",
        "isoenzymes",
    }:
        cls = OrNode
    else:
        return None
    members = catalyst.get(
        "members",
        catalyst.get(
            "proteins", catalyst.get("components", catalyst.get("children", []))
        ),
    )
    if not isinstance(members, (list, tuple)):
        return None
    children = tuple(
        node for item in members if (node := _member_node(item, source)) is not None
    )
    if cls is AndNode:
        repeated: dict[str, list[GeneNode]] = {}
        for child in children:
            if isinstance(child, GeneNode) and child.coefficient is None:
                repeated.setdefault(child.gene, []).append(child)
        replacements = {
            gene: GeneNode(
                gene,
                len(values),
                "inferred",
                source,
                tuple(item for value in values for item in value.evidence),
            )
            for gene, values in repeated.items()
            if len(values) > 1
        }
        emitted: set[str] = set()
        collapsed = []
        for child in children:
            if isinstance(child, GeneNode) and child.gene in replacements:
                if child.gene in emitted:
                    continue
                emitted.add(child.gene)
                collapsed.append(replacements[child.gene])
            else:
                collapsed.append(child)
        children = tuple(collapsed)
    return normalize_sgpr(cls(children)) if children else None


def catalyst_sgpr(record: Mapping[str, object], *, ec: str = "") -> SgprEvidence:
    """Convert a Reactome catalyst record to canonical structural evidence."""
    catalyst = record.get("catalyst", record.get("catalyst_activity", record))
    node = _catalyst_node(catalyst) if isinstance(catalyst, Mapping) else None
    identifier = record.get("reactome_id", record.get("stId", record.get("id", "")))
    return SgprEvidence(
        source="reactome",
        ec=ec or str(record.get("ec", "")),
        sgpr=node,
        confidence="strong" if node is not None else "weak",
        status="resolved" if node is not None else "unresolved",
        provenance=(str(identifier),) if identifier else (),
        warnings=() if node is not None else ("unknown-reactome-catalyst-structure",),
    )


class ReactomeClient(_UnavailableRequestMixin, StaticReactomeClient):
    base_url = "https://reactome.org/ContentService"

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
        self.failed_requests = 0

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
        identifier = str(rhea_id).split(":", 1)[-1]
        query = urlencode({"query": f"RHEA:{identifier}", "types": "Reaction"})
        try:
            payload = self._remote(f"/search/query?{query}")
        except Exception as error:
            if self._unavailable(error):
                return []
            raise
        if not isinstance(payload, Mapping):
            return []
        matches = []
        for group in payload.get("results", []):
            if isinstance(group, Mapping) and isinstance(group.get("entries"), list):
                matches.extend(
                    item for item in group["entries"] if isinstance(item, Mapping)
                )
            elif isinstance(group, Mapping) and group.get("stId"):
                matches.append(group)
        return matches

    def reaction(self, reactome_id: str) -> Mapping[str, object] | None:
        local = super().reaction(reactome_id)
        if local is not None:
            return local
        try:
            payload = self._remote(f"/data/query/{quote(str(reactome_id), safe='')}")
        except Exception as error:
            if self._unavailable(error):
                return None
            raise
        return payload if isinstance(payload, Mapping) else None


__all__ = [
    "ReactomeClient",
    "ReactomeClientProtocol",
    "StaticReactomeClient",
    "catalyst_sgpr",
    "catalyst_candidate_gpr",
]
