from __future__ import annotations

import json

from cobra import Model
from cobra.core import Group, Metabolite, Reaction

from thg_protocol.analysis.model_signature import (
    diff_model_signatures,
    model_signature,
)


def _model(rule: str = "g2 and (g1 or g3)") -> Model:
    model = Model("toy")
    model.name = "Toy model"
    first = Metabolite(
        "a_c", name="A", formula="C2H4", charge=-1, compartment="c"
    )
    first.annotation = {"ids": ["two", "one"]}
    second = Metabolite("b_c", name="B", compartment="c")
    reaction = Reaction("R1", name="reaction")
    reaction.lower_bound = -1
    reaction.upper_bound = 3
    reaction.gene_reaction_rule = rule
    reaction.annotation = {"ec-code": ["2.2.2.2", "1.1.1.1"]}
    reaction.add_metabolites({first: -1, second: 1})
    model.add_reactions([reaction])
    model.objective = {reaction: 2}
    group = Group("group", name="Group", kind="collection")
    group.add_members([reaction, first])
    model.add_groups([group])
    return model


def test_model_signature_is_json_compatible_and_semantically_sorted():
    first = model_signature(_model())
    second = model_signature(_model("(g3 or g1) and g2"))

    assert json.loads(json.dumps(first)) == first
    assert first == second
    assert [item["id"] for item in first["metabolites"]] == ["a_c", "b_c"]
    assert first["reactions"][0]["stoichiometry"] == [
        {"metabolite": "a_c", "coefficient": -1.0},
        {"metabolite": "b_c", "coefficient": 1.0},
    ]
    assert first["objective"] == [{"reaction": "R1", "coefficient": 2.0}]
    assert first["groups"][0]["members"] == ["R1", "a_c"]


def test_diff_reports_added_removed_and_changed_objects():
    first = _model()
    second = _model()
    second.reactions.R1.upper_bound = 4
    extra = Reaction("R2")
    extra.add_metabolites({second.metabolites.b_c: -1})
    second.add_reactions([extra])
    second.groups[0].remove_members([second.metabolites.a_c])
    second.remove_metabolites([second.metabolites.a_c])

    diff = diff_model_signatures(model_signature(first), model_signature(second))

    assert diff["added"]["reactions"] == ["R2"]
    assert diff["removed"]["metabolites"] == ["a_c"]
    assert diff["changed"]["reactions"][0]["id"] == "R1"
    assert diff["model"]["changed"] is False
