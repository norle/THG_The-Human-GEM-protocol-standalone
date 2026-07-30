import cobra

from thg_protocol.analysis import find_network_components, write_component_report


def test_network_components_are_structured_and_non_mutating(tmp_path):
    model = cobra.Model("toy")
    a = cobra.Metabolite("a_c", compartment="c")
    b = cobra.Metabolite("b_c", compartment="c")
    c = cobra.Metabolite("c_c", compartment="c")
    first = cobra.Reaction("R1")
    first.add_metabolites({a: -1, b: 1})
    second = cobra.Reaction("R2")
    second.add_metabolites({c: -1})
    model.add_reactions([first, second])

    results = find_network_components(model)
    report = write_component_report(results, tmp_path / "components.json")

    assert len(model.reactions) == 2
    assert len(results["components"]) == 2
    assert results["component_info"][0]["reaction_count"] == 1
    assert report.read_text().startswith("{\n")


def test_network_components_keep_same_named_reactions_and_metabolites_distinct():
    model = cobra.Model("collision")
    metabolite = cobra.Metabolite("shared", compartment="c")
    reaction = cobra.Reaction("shared")
    reaction.add_metabolites({metabolite: -1})
    model.add_reactions([reaction])

    results = find_network_components(model)

    assert results["graph"].number_of_nodes() == 2
    assert set(results["graph"].nodes) == {
        ("metabolite", "shared"),
        ("reaction", "shared"),
    }
    assert results["component_info"][0]["reaction_count"] == 1
    assert results["component_info"][0]["metabolite_count"] == 1
