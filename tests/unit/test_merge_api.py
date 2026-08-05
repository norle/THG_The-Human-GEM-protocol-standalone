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


def test_identifier_merge_retains_base_chemistry_bounds_and_gpr_on_conflict():
    base = cobra.Model("base")
    base_metabolite = cobra.Metabolite(
        "a_c", compartment="c", formula="C1", charge=0, name="base A"
    )
    base_reaction = cobra.Reaction(
        "R1", name="base reaction", lower_bound=-1, upper_bound=2
    )
    base_reaction.add_metabolites({base_metabolite: -1})
    base_reaction.gene_reaction_rule = "G1"
    base.add_reactions([base_reaction])

    incoming = cobra.Model("incoming")
    incoming_metabolite = cobra.Metabolite(
        "a_c", compartment="c", formula="C2", charge=1, name="incoming A"
    )
    incoming_reaction = cobra.Reaction(
        "R1", name="incoming reaction", lower_bound=-10, upper_bound=10
    )
    incoming_reaction.add_metabolites({incoming_metabolite: -2})
    incoming_reaction.gene_reaction_rule = "G2"
    incoming_reaction.annotation["kegg.reaction"] = "R00001"
    incoming.add_reactions([incoming_reaction])

    merged, report = merge_models(base, incoming)
    reaction = merged.reactions.R1
    metabolite = merged.metabolites.a_c

    assert report.overlapping_metabolites == 1
    assert report.overlapping_reactions == 1
    assert metabolite.formula == "C1"
    assert metabolite.charge == 0
    assert reaction.bounds == (-1, 2)
    assert reaction.metabolites[metabolite] == -1
    assert reaction.gene_reaction_rule == "G1"
    assert reaction.annotation == {"kegg.reaction": "R00001"}


def test_identifier_merge_does_not_match_different_ids_by_chemistry():
    base = _model("base", "R1", "a_c")
    incoming = _model("incoming", "R2", "b_c")
    incoming.metabolites.b_c.formula = base.metabolites.a_c.formula

    merged, report = merge_models(base, incoming)

    assert report.added_metabolites == 1
    assert report.added_reactions == 1
    assert merged.metabolites.has_id("a_c")
    assert merged.metabolites.has_id("b_c")
    assert merged.reactions.has_id("R1")
    assert merged.reactions.has_id("R2")
