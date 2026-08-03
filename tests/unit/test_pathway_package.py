import thg_protocol.pathway as pathway
from thg_protocol.pathway import core


def test_pathway_package_reexports_core_helpers():
    assert pathway.parse_reaction_equation is core.parse_reaction_equation
    assert pathway.get_next_reaction_id is core.get_next_reaction_id
    assert "core.py" in core.__file__


def test_mutation_heavy_workflows_are_exposed():
    assert callable(pathway.create_compartment_metabolites)
    assert callable(pathway.create_compartment_reactions)
