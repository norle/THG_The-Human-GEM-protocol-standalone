"""Putative-transport (PTR) gapfill: candidates, connectors, sink coverage, MILP.

The legacy three-phase pipeline, as pure functions over COBRApy models:

1. candidates: same-base metabolite pairs in allowed compartment pairs that
   either join two network components or link main-component dead ends;
2. connectors: a minimum spanning tree over components, one PTR per edge;
3. coverage and selection: per component, which blocked reactions each PTR
   unblocks with temporary dead-end sinks, then one MILP picks the PTRs.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, replace
from typing import Any

from .core import GapfillCandidate, _as_mapping, _suffix, _TransportSearch

_RANK = {"A": 0, "B": 1, "C": 2}


def _base(metabolite_id: str) -> str:
    return re.sub(r"[a-z]+$", "", metabolite_id)


@dataclass(frozen=True)
class Components:
    """Connected components of the undirected reaction–metabolite graph.

    ``of`` maps metabolite and reaction IDs to a component number; numbers are
    ordered by node count, descending, so 1 is the main component.
    """

    of: dict[str, int]
    sizes: dict[int, int]


def network_components(model: Any) -> Components:
    """Number components by size; metabolites in no reaction get no entry."""
    parent: dict[str, str] = {}

    def find(item: str) -> str:
        while parent[item] != item:
            parent[item] = parent[parent[item]]
            item = parent[item]
        return item

    for reaction in model.reactions:
        parent.setdefault(reaction.id, reaction.id)
        for metabolite in reaction.metabolites:
            parent.setdefault(metabolite.id, metabolite.id)
            left, right = find(reaction.id), find(metabolite.id)
            if left != right:
                parent[right] = left
    groups: dict[str, list[str]] = {}
    for node in parent:
        groups.setdefault(find(node), []).append(node)
    ordered = sorted(groups.values(), key=lambda nodes: (-len(nodes), min(nodes)))
    of = {node: number for number, nodes in enumerate(ordered, 1) for node in nodes}
    return Components(
        of, {number: len(nodes) for number, nodes in enumerate(ordered, 1)}
    )


@dataclass(frozen=True)
class PtrCandidate:
    """A reversible same-base transport between two compartments.

    ``met1 < met2``; ``compartments`` and ``components`` follow that order.
    ``present`` marks a pair an existing transport already covers: such a
    candidate is reported but never added.
    """

    met1: str
    met2: str
    base: str
    compartments: tuple[str, str]
    components: tuple[int, int]
    type: str
    reaction_id: str
    present: bool = False

    @property
    def main_only(self) -> bool:
        return self.components == (1, 1)

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "compartments": list(self.compartments),
            "components": list(self.components),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> PtrCandidate:
        return cls(
            **{
                **payload,
                "compartments": tuple(payload["compartments"]),
                "components": tuple(payload["components"]),
            }
        )

    def as_gapfill_candidate(self) -> GapfillCandidate:
        return GapfillCandidate(
            self.reaction_id,
            {self.met1: -1.0, self.met2: 1.0},
            -1000.0,
            1000.0,
            source="putative-transport",
            annotation={"type": self.type, "base": self.base},
        )


def _kind(metabolite_id: str, produced: set[str], consumed: set[str]) -> str:
    if metabolite_id in produced - consumed:
        return "product"
    if metabolite_id in consumed - produced:
        return "substrate"
    return "none"


def generate_ptr_candidates(
    model: Any,
    allowed_connections: list[tuple[str, str]],
    candidate_types: list[str],
    components: Components,
) -> list[PtrCandidate]:
    """Pairs that join two components, or two main-component dead ends.

    A pair across components qualifies with any type. A pair inside the main
    component qualifies only as type A or B, i.e. when it links dead ends.
    Candidates sorted by ``reaction_id``.
    """
    allowed = {tuple(sorted(pair)) for pair in allowed_connections}
    produced: set[str] = set()
    consumed: set[str] = set()
    for reaction in model.reactions:
        for metabolite, coefficient in reaction.metabolites.items():
            if coefficient > 0:
                produced.add(metabolite.id)
            elif coefficient < 0:
                consumed.add(metabolite.id)
    buckets: dict[str, list[tuple[str, str]]] = {}
    for metabolite in model.metabolites:
        if metabolite.id in components.of:
            compartment = metabolite.compartment or _suffix(metabolite.id)
            buckets.setdefault(_base(metabolite.id), []).append(
                (metabolite.id, compartment)
            )
    search = _TransportSearch(_as_mapping(model))
    result = []
    for base, members in buckets.items():
        members.sort()
        for index, (met1, compartment1) in enumerate(members):
            for met2, compartment2 in members[index + 1 :]:
                if tuple(sorted((compartment1, compartment2))) not in allowed:
                    continue
                kinds = {
                    _kind(met1, produced, consumed),
                    _kind(met2, produced, consumed),
                }
                kind = (
                    "A"
                    if kinds == {"product", "substrate"}
                    else "B"
                    if len(kinds) == 1 and kinds != {"none"}
                    else "C"
                )
                pair = (components.of[met1], components.of[met2])
                if kind not in candidate_types or (
                    pair[0] == pair[1] and (pair[0] != 1 or kind == "C")
                ):
                    continue
                candidate = PtrCandidate(
                    met1,
                    met2,
                    base,
                    (compartment1, compartment2),
                    pair,
                    kind,
                    re.sub(r"[^A-Za-z0-9_]", "_", f"GAPFILL_PTR_{met1}_{met2}"),
                )
                if search.covers(candidate.as_gapfill_candidate()):
                    candidate = replace(candidate, present=True)
                result.append(candidate)
    return sorted(result, key=lambda candidate: candidate.reaction_id)
