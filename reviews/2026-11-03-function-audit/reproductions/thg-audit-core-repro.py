"""Small in-memory reproductions for THG audit findings; touches no files."""
from cobra import Metabolite, Model, Reaction

from thg_protocol.analysis.consistency import unbounded_reactions
from thg_protocol.gapfill.core import _resolved_parameters
from thg_protocol.model_build.mass_balance import nullity
from thg_protocol.pathway.core import parse_reaction_equation
from thg_protocol.pathway.workflow import implement_pathway
from thg_protocol.pathway.core import (
    create_compartment_reactions,
    parse_universal_reaction,
)

# F1: a finite 1000 flux bound is called mathematically unbounded.
model = Model("finite_1000")
a = Metabolite("a_c", compartment="c")
source = Reaction("R", lower_bound=0, upper_bound=1000)
source.add_metabolites({a: 1})
drain = Reaction("D", lower_bound=0, upper_bound=1000)
drain.add_metabolites({a: -1})
model.add_reactions([source, drain])
model.objective = drain
reported, fraction, fva = unbounded_reactions(model)
assert fva.loc["D", "maximum"] == 1000
assert set(reported) == {"D", "R"} and fraction == 1.0

# F2: one unresolved term is silently dropped from the imported chemistry.
json_model = {
    "metabolites": [
        {"id": "A_c", "name": "A", "compartment": "c"},
        {"id": "B_c", "name": "B", "compartment": "c"},
    ],
    "reactions": [],
}
partial = parse_universal_reaction("A[c] + MISSING[c] --> B[c]", json_model, {})
assert partial == {
    "metabolites": {"A_c": -1.0, "B_c": 1.0},
    "reversible": False,
}
assert [term["name"] for term in parse_reaction_equation("A[c] + malformed --> B[c]")["terms"]] == ["A", "B"]

# F3: generated reaction IDs can take a later explicit ID; that config row is skipped.
json_model = {
    "compartments": {"c": "cytosol"},
    "metabolites": [
        {"id": "A_c", "name": "A", "compartment": "c"},
        {"id": "B_c", "name": "B", "compartment": "c"},
    ],
    "reactions": [],
}
config = {"reactions": [
    {"name": "automatic", "equation": "A[c] --> B[c]"},
    {"id": "MAR00001", "name": "explicit", "equation": "B[c] --> A[c]"},
]}
assert create_compartment_reactions(json_model, {}, "c", config) == 1
assert json_model["reactions"][0]["name"] == "automatic"
assert all(row["name"] != "explicit" for row in json_model["reactions"])

# F4: two configured compartments repeat an ID-less reaction definition.
model = {
    "compartments": {},
    "metabolites": [
        {"id": "A_c", "name": "A", "compartment": "c"},
        {"id": "B_c", "name": "B", "compartment": "c"},
    ],
    "reactions": [],
}
result = implement_pathway(
    model,
    {"compartments": [{"abbreviation": "c", "name": "cytosol"},
                     {"abbreviation": "e", "name": "external"}],
     "reactions": [{"name": "A to B", "equation": "A[c] --> B[c]"}]},
    {},
)
assert result["reactions_added"] == 2
assert result["model"]["reactions"][0]["metabolites"] == result["model"]["reactions"][1]["metabolites"]

# F5: the alleged square nullity completion can be rank deficient.
completed, independent = nullity([[0, 1]])
assert completed.shape == (2, 2) and independent.shape == (1, 2)
assert __import__("numpy").linalg.matrix_rank(completed) == 1

# F6: invalid negative minimum flux passes MILP parameter validation.
params = _resolved_parameters(
    "milp",
    {"universal_model": "universal.xml", "objective": "BIOMASS", "minimum_flux": -1},
)
assert params["minimum_flux"] == -1

print("All six audit reproductions passed.")
