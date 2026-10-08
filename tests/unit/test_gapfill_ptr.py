"""Putative-transport (sink-MILP) gapfill phases on small COBRApy models."""

import re

import cobra
import pytest

from thg_protocol.gapfill.ptr import (
    PtrCandidate,
    generate_ptr_candidates,
    network_components,
)


def build(reactions, *, reversible=(), compartments=None, unused=()):
    """Build a model from ``{reaction_id: {metabolite_id: coefficient}}``.

    Compartments come from the trailing lowercase suffix unless overridden.
    """
    compartments = compartments or {}
    model = cobra.Model("ptr")
    metabolites = {}
    for metabolite_id in [
        *{mid for stoich in reactions.values() for mid in stoich},
        *unused,
    ]:
        if metabolite_id not in metabolites:
            suffix = re.search(r"[a-z]+$", metabolite_id)
            metabolites[metabolite_id] = cobra.Metabolite(
                metabolite_id,
                compartment=compartments.get(
                    metabolite_id, suffix.group(0) if suffix else ""
                ),
            )
    model.add_metabolites(sorted(metabolites.values(), key=lambda met: met.id))
    for reaction_id, stoich in reactions.items():
        reaction = cobra.Reaction(
            reaction_id,
            lower_bound=-1000.0 if reaction_id in reversible else 0.0,
            upper_bound=1000.0,
        )
        model.add_reactions([reaction])
        reaction.add_metabolites(
            {model.metabolites.get_by_id(mid): value for mid, value in stoich.items()}
        )
    return model


def candidates_of(model, connections=(("c", "e"),), types=("A", "B", "C")):
    return generate_ptr_candidates(
        model, list(connections), list(types), network_components(model)
    )


def two_islands():
    """Main island Xc/Yc cycle, small island Xe/We cycle: no dead ends."""
    return build(
        {
            "R1": {"Xc": -1, "Yc": 1},
            "R2": {"Yc": -1, "Xc": 1},
            "R3": {"Xe": -1, "We": 1},
            "R4": {"We": -1, "Xe": 1},
            "R5": {"Yc": -1, "Zc": 1},
        }
    )


def main_with_dead_ends():
    """One island with c and e metabolites: Ac substrate, Ae product dead end."""
    return build(
        {
            "R1": {"Ac": -1, "Bc": 1},
            "R2": {"Bc": -1, "Cc": 1},
            "R3": {"Cc": -1, "Bc": 1},
            "R4": {"Bc": -1, "Ce": 1},
            "R5": {"Ce": -1, "Bc": 1},
            "R6": {"Ce": -1, "Ae": 1},
        }
    )


def test_components_number_main_first():
    model = two_islands()
    model.add_metabolites([cobra.Metabolite("Qc", compartment="c")])
    components = network_components(model)
    assert components.of["Xc"] == components.of["R5"] == 1
    assert components.of["Xe"] == components.of["R3"] == 2
    assert "Qc" not in components.of
    assert components.sizes == {1: 6, 2: 4}


def test_cross_component_pair_is_a_candidate_of_any_type():
    (candidate,) = candidates_of(two_islands())
    assert candidate == PtrCandidate(
        met1="Xc",
        met2="Xe",
        base="X",
        compartments=("c", "e"),
        components=(1, 2),
        type="C",
        reaction_id="GAPFILL_PTR_Xc_Xe",
    )
    assert PtrCandidate.from_dict(candidate.to_dict()) == candidate


def test_main_component_pair_needs_a_dead_end():
    candidates = candidates_of(main_with_dead_ends())
    assert [(item.met1, item.met2, item.type) for item in candidates] == [
        ("Ac", "Ae", "A")
    ]
    assert candidates[0].components == (1, 1)


def test_pairs_outside_allowed_connections_are_dropped():
    assert candidates_of(two_islands(), connections=[("c", "m")]) == []


def test_existing_transport_suppresses_candidate():
    model = main_with_dead_ends()
    reaction = cobra.Reaction("T", lower_bound=-1000.0, upper_bound=1000.0)
    model.add_reactions([reaction])
    reaction.add_metabolites({model.metabolites.Ac: -1, model.metabolites.Ae: 1})
    (candidate,) = candidates_of(model)
    assert candidate.present


def test_metabolite_without_suffix_uses_compartment_attribute():
    model = build(
        {
            "R1": {"GLC1": -1, "Yc": 1},
            "R2": {"Yc": -1, "GLC1": 1},
            "R3": {"GLC1e": -1, "We": 1},
            "R4": {"We": -1, "GLC1e": 1},
        },
        compartments={"GLC1": "c"},
    )
    (candidate,) = candidates_of(model)
    assert (candidate.met1, candidate.met2) == ("GLC1", "GLC1e")
    assert candidate.base == "GLC1"
    assert candidate.compartments == ("c", "e")


@pytest.mark.parametrize("types", [["A", "B"], ["C"]])
def test_candidate_types_filter(types):
    found = candidates_of(two_islands(), types=types)
    assert [item.type for item in found] == [t for t in ["C"] if t in types]
