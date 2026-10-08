"""The incremental greedy search must select what a copy-per-trial search selects."""

import random

import pytest

from thg_protocol.gapfill import gapfill_model
from thg_protocol.gapfill.core import (
    _add_candidate,
    _candidate_model_copy,
    _covered_transport,
    _metrics,
    _transport_candidates,
)


def _copying_greedy(model, connections, max_additions):
    """Reference search: score every candidate on a full model copy."""
    current_model = _candidate_model_copy(model)
    candidates = [
        candidate
        for candidate in _transport_candidates(
            current_model, connections, ["A", "B", "C"]
        )
        if not _covered_transport(current_model, candidate)
    ]
    rank = {"A": 0, "B": 1, "C": 2}
    selected = []
    while len(selected) < max_additions:
        current = _metrics(current_model)
        scored = []
        for candidate in candidates:
            trial = _candidate_model_copy(current_model)
            _add_candidate(trial, candidate)
            after = _metrics(trial)
            improvement = (
                current["dead_ends"] - after["dead_ends"],
                current["components"] - after["components"],
            )
            if improvement != (0, 0):
                scored.append(
                    (
                        (
                            -improvement[0],
                            -improvement[1],
                            rank[candidate.annotation["type"]],
                            candidate.id,
                        ),
                        candidate,
                    )
                )
        if not scored:
            break
        _, best = min(scored)
        _add_candidate(current_model, best)
        selected.append(best.id)
        candidates.remove(best)
    return selected, _metrics(current_model)


def _random_model(seed):
    rng = random.Random(seed)
    compartments = ["c", "e", "m"]
    metabolites = [
        {"id": f"M{base:02d}{compartment}", "compartment": compartment}
        for base in range(8)
        for compartment in compartments
        if rng.random() < 0.7
    ]
    ids = [item["id"] for item in metabolites]
    reactions = []
    for index in range(rng.randint(3, 10)):
        left, right = rng.sample(ids, 2)
        stoichiometry = {left: -1, right: 1}
        if rng.random() < 0.3:
            stoichiometry[rng.choice(ids)] = rng.choice((-1, 1))
        reactions.append(
            {
                "id": f"R{index}",
                "metabolites": stoichiometry,
                "lower_bound": rng.choice((-1000, 0)),
                "upper_bound": 1000,
            }
        )
    return {
        "compartments": dict.fromkeys(compartments, "x"),
        "metabolites": metabolites,
        "reactions": reactions,
    }


@pytest.mark.parametrize("seed", range(40))
def test_greedy_selection_matches_copy_per_trial_search(seed):
    model = _random_model(seed)
    connections = [("c", "e"), ("c", "m")]
    known = {item["compartment"] for item in model["metabolites"]}
    if not {"c", "e", "m"} <= known:
        pytest.skip("random model lacks a compartment")
    expected, expected_after = _copying_greedy(model, connections, 4)

    result = gapfill_model(
        model,
        method="greedy",
        parameters={"max_additions": 4, "allowed_connections": connections},
    )

    assert result.selected == expected
    assert result.after_metrics == expected_after


def test_greedy_scoring_does_not_copy_the_model_per_candidate(monkeypatch):
    from thg_protocol.gapfill import core

    model = _random_model(3)
    copies = []
    original = core._candidate_model_copy
    monkeypatch.setattr(
        core,
        "_candidate_model_copy",
        lambda item: copies.append(1) or original(item),
    )

    gapfill_model(
        model,
        method="greedy",
        parameters={"max_additions": 4, "allowed_connections": [("c", "e")]},
    )

    assert len(copies) <= 1
