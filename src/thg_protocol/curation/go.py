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


def resolve_go_compartment(
    raw_location: str,
    go_id: str | None,
    graph: Mapping[str, Mapping[str, object]],
    compartment_go_terms: Mapping[str, str],
    compartments: Mapping[str, str] | None = None,
) -> dict[str, object]:
    """Resolve a GO term to the nearest configured β2 GO target."""
    targets = {
        str(key): normalize_go_id(value)
        for key, value in compartment_go_terms.items()
        if normalize_go_id(value)
    }
    by_go = {value: key for key, value in targets.items()}
    supplied_go_id = normalize_go_id(go_id)
    if supplied_go_id in by_go:
        result = {
            "raw_location": raw_location,
            "go_id": supplied_go_id,
            "status": "resolved",
            "target_compartment_id": by_go[supplied_go_id],
            "target_go_id": supplied_go_id,
            "resolution_path": [{"id": supplied_go_id}],
        }
        if compartments and by_go[supplied_go_id] in compartments:
            result["target_compartment_name"] = compartments[by_go[supplied_go_id]]
        return result
    start, error = _start_term(raw_location, go_id, graph)
    if error:
        return {
            "raw_location": raw_location,
            "go_id": go_id,
            "status": "rejected",
            "reason": error,
        }
    queue = deque([(start, 0, [])])
    seen: set[str] = set()
    candidates: list[tuple[int, str, list[dict[str, object]]]] = []
    while queue:
        identifier, distance, path = queue.popleft()
        if identifier in seen:
            continue
        seen.add(identifier)
        value = _term(graph, identifier)
        current = path + [{"id": identifier, "name": value.get("name", identifier)}]
        if identifier in by_go:
            candidates.append((distance, by_go[identifier], current))
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
                    (
                        parent_id,
                        distance + 1,
                        current + [{"relation": relation, "id": parent_id}],
                    )
                )
    if not candidates:
        return {
            "raw_location": raw_location,
            "go_id": start,
            "status": "rejected",
            "reason": "location-not-in-registry",
        }
    nearest_distance = min(item[0] for item in candidates)
    nearest = [item for item in candidates if item[0] == nearest_distance]
    target_ids = sorted({item[1] for item in nearest})
    if len(target_ids) != 1:
        return {
            "raw_location": raw_location,
            "go_id": start,
            "status": "rejected",
            "reason": "ambiguous-compartment-resolution",
            "candidate_compartments": target_ids,
        }
    key = target_ids[0]
    result = {
        "raw_location": raw_location,
        "go_id": start,
        "status": "resolved",
        "target_compartment_id": key,
        "target_go_id": targets[key],
        "resolution_path": sorted(item[2] for item in nearest if item[1] == key)[0],
    }
    if compartments and key in compartments:
        result["target_compartment_name"] = compartments[key]
    return result


__all__ = ["load_obo", "normalize_go_id", "parse_obo", "resolve_go_compartment"]
