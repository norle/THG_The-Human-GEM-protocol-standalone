"""Pure, offline GO Cellular Component resolution."""

from __future__ import annotations

import re
from collections import deque
from collections.abc import Mapping
from pathlib import Path

GO_ID = re.compile(r"^GO:\d{7}$", re.IGNORECASE)


def normalize_go_id(value: object) -> str:
    text = str(value or "").strip().upper()
    return text if GO_ID.fullmatch(text) else ""


def _term(
    graph: Mapping[str, Mapping[str, object]], identifier: str
) -> Mapping[str, object]:
    value = graph.get(identifier, {})
    return value if isinstance(value, Mapping) else {}


def load_obo(path: str | Path) -> dict[str, dict[str, object]]:
    """Load the small GO graph representation needed by β2."""
    return parse_obo(Path(path).read_text(encoding="utf-8"))


def parse_obo(text: str) -> dict[str, dict[str, object]]:
    graph: dict[str, dict[str, object]] = {}
    current: dict[str, object] | None = None

    def flush() -> None:
        if current is None or current.get("is_obsolete"):
            return
        identifier = normalize_go_id(current.get("id"))
        if identifier:
            graph[identifier] = {
                "name": str(current.get("name", "")),
                "synonyms": sorted(set(current.get("synonyms", []))),
                "parents": list(current.get("parents", [])),
            }

    for raw in text.splitlines() + [""]:
        line = raw.strip()
        if line == "[Term]":
            flush()
            current = {"synonyms": [], "parents": []}
            continue
        if not line or line.startswith("!"):
            if not line:
                flush()
                current = None
            continue
        if current is None or ":" not in line:
            continue
        key, value = line.split(":", 1)
        value = value.strip()
        if key == "synonym":
            match = re.match(r'"([^"]+)"', value)
            if match:
                current.setdefault("synonyms", []).append(match.group(1))
        elif key == "is_a":
            parent = normalize_go_id(value.split("!", 1)[0].strip())
            if parent:
                current.setdefault("parents", []).append(
                    {"relation": "is_a", "id": parent}
                )
        elif key == "relationship":
            relation, _, parent = value.partition(" ")
            parent = normalize_go_id(parent.split("!", 1)[0].strip())
            if relation == "part_of" and parent:
                current.setdefault("parents", []).append(
                    {"relation": "part_of", "id": parent}
                )
        elif key in {"id", "name"}:
            current[key] = value
        elif key == "is_obsolete" and value == "true":
            current["is_obsolete"] = True
    return graph


def _start_term(
    raw_location: str,
    go_id: str | None,
    graph: Mapping[str, Mapping[str, object]],
) -> tuple[str, str | None]:
    identifier = normalize_go_id(go_id)
    if identifier and identifier in graph:
        return identifier, None
    normalized = " ".join(str(raw_location).strip().lower().split())
    matches = []
    for key, value in graph.items():
        names = [value.get("name", ""), *(value.get("synonyms", []) or [])]
        if normalized in {" ".join(str(item).lower().split()) for item in names}:
            matches.append(str(key))
    if len(matches) == 1:
        return matches[0], None
    if len(matches) > 1:
        return "", "ambiguous-go-term"
    return "", "location-not-in-ontology"


def _walk_up(
    graph: Mapping[str, Mapping[str, object]], start: str
) -> dict[str, list[dict[str, object]]]:
    """Return every term reachable from ``start`` through ``is_a`` and
    ``part_of``, each with the shortest path that reached it."""
    queue = deque([(start, [])])
    paths: dict[str, list[dict[str, object]]] = {}
    while queue:
        identifier, path = queue.popleft()
        if identifier in paths:
            continue
        value = _term(graph, identifier)
        current = path + [{"id": identifier, "name": value.get("name", identifier)}]
        paths[identifier] = current
        parents = list(value.get("parents", []) or [])
        for relation, parent_value in [
            (str(item.get("relation", "")), item.get("id"))
            for item in parents
            if isinstance(item, Mapping)
        ] + [
            (str(item[0]), item[1])
            for item in parents
            if isinstance(item, (list, tuple)) and len(item) == 2
        ]:
            parent_id = normalize_go_id(parent_value)
            if relation in {"is_a", "part_of"} and parent_id in graph:
                queue.append(
                    (parent_id, current + [{"relation": relation, "id": parent_id}])
                )
    return paths


def _resolved(
    raw_location: str,
    go_id: str,
    keys: list[str],
    targets: Mapping[str, str],
    paths: list[list[dict[str, object]]],
    compartments: Mapping[str, str] | None,
) -> dict[str, object]:
    result: dict[str, object] = {
        "raw_location": raw_location,
        "go_id": go_id,
        "status": "resolved",
        "target_compartment_ids": keys,
        "target_go_ids": [targets[key] for key in keys],
        "resolution_paths": paths,
    }
    if compartments:
        result["target_compartment_names"] = [
            compartments[key] for key in keys if key in compartments
        ]
    return result


def resolve_go_compartment(
    raw_location: str,
    go_id: str | None,
    graph: Mapping[str, Mapping[str, object]],
    compartment_go_terms: Mapping[str, str],
    compartments: Mapping[str, str] | None = None,
    compartment_go_aliases: Mapping[str, str] | None = None,
) -> dict[str, object]:
    """Resolve a GO term to every configured β2 compartment it lies in.

    The walk goes up through ``is_a`` and ``part_of`` and collects every
    configured compartment term it reaches. A compartment is then dropped if
    its GO term is an ancestor of another reached compartment's term (e.g.
    mitochondrion when mitochondrial inner membrane was also reached), so
    only the most specific places remain. Compartments that are not
    ancestors of each other are all kept: an axonemal microtubule is both
    cytoskeleton and cilium. Distance in the graph plays no role.

    ``compartment_go_aliases`` maps a GO term to a compartment only when the
    location starts at exactly that term; the upward walk never uses aliases,
    so a broad alias (e.g. cytoplasm -> cytosol) cannot capture descendants.
    """
    targets = {
        str(key): normalize_go_id(value)
        for key, value in compartment_go_terms.items()
        if normalize_go_id(value)
    }
    aliases = {
        normalize_go_id(term): str(key)
        for term, key in (compartment_go_aliases or {}).items()
        if normalize_go_id(term) and str(key) in targets
    }
    by_go = {value: key for key, value in targets.items()}
    supplied_go_id = normalize_go_id(go_id)
    if supplied_go_id in by_go and supplied_go_id not in graph:
        return _resolved(
            raw_location,
            supplied_go_id,
            [by_go[supplied_go_id]],
            targets,
            [[{"id": supplied_go_id}]],
            compartments,
        )
    start, error = _start_term(raw_location, go_id, graph)
    if error:
        return {
            "raw_location": raw_location,
            "go_id": go_id,
            "status": "rejected",
            "reason": error,
        }
    if start in aliases and start not in by_go:
        key = aliases[start]
        result = _resolved(
            raw_location,
            start,
            [key],
            targets,
            [
                [
                    {"id": start, "name": _term(graph, start).get("name", start)},
                    {"relation": "configured_alias", "id": targets[key]},
                ]
            ],
            compartments,
        )
        result["resolution_method"] = "configured-alias"
        return result
    paths = _walk_up(graph, start)
    reached = {by_go[term]: path for term, path in paths.items() if term in by_go}
    if not reached:
        return {
            "raw_location": raw_location,
            "go_id": start,
            "status": "rejected",
            "reason": "location-not-in-registry",
        }
    # A reached compartment that contains another reached one is less specific.
    above = {
        key
        for other in reached
        for key in reached
        if key != other and targets[key] in _walk_up(graph, targets[other])
    }
    keys = sorted(key for key in reached if key not in above)
    return _resolved(
        raw_location, start, keys, targets, [reached[key] for key in keys], compartments
    )


__all__ = ["load_obo", "normalize_go_id", "parse_obo", "resolve_go_compartment"]
