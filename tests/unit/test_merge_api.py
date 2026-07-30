import cobra

from thg_protocol.merge import merge_models, merge_models_from_paths


def _model(model_id, reaction_id, metabolite_id, *, annotation=None):
    model = cobra.Model(model_id)
    model.compartments["c"] = "cytosol"
    metabolite = cobra.Metabolite(metabolite_id, compartment="c", formula="C1")
    reaction = cobra.Reaction(reaction_id)
    reaction.add_metabolites({metabolite: -1})
    reaction.annotation.update(annotation or {})
    model.add_reactions([reaction])
    return model


def test_merge_models_is_non_mutating_and_writes_output(tmp_path):
    base = _model("base", "R1", "a_c")
    incoming = _model(
        "incoming",
        "R2",
        "b_c",
        annotation={"kegg.reaction": "R00001"},
    )

    merged, report = merge_models(
        base,
        incoming,
        output_path=tmp_path / "nested" / "merged.xml",
    )

    assert report.added_metabolites == 1
    assert report.added_reactions == 1
    assert merged.reactions.has_id("R1")
    assert merged.reactions.has_id("R2")
    assert not base.reactions.has_id("R2")
    assert report.output_path == tmp_path / "nested" / "merged.xml"
    assert report.output_path.exists()


def test_merge_models_from_paths_removes_isolated_metabolites(tmp_path):
    base = _model("base", "R1", "a_c")
    isolated = cobra.Metabolite("unused_c", compartment="c")
    base.add_metabolites([isolated])
    incoming = _model("incoming", "R2", "a_c")
    base_path = tmp_path / "base.xml"
    incoming_path = tmp_path / "incoming.xml"
    output_path = tmp_path / "out" / "merged.json"
    cobra.io.write_sbml_model(base, base_path)
    cobra.io.write_sbml_model(incoming, incoming_path)

    merged, report = merge_models_from_paths(
        base_path,
        incoming_path,
        output_path,
        remove_isolated_metabolites=True,
    )

    assert merged.metabolites.has_id("a_c")
    assert not merged.metabolites.has_id("unused_c")
    assert report.removed_isolated_metabolites == 1
    assert output_path.exists()
