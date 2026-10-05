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


def test_same_id_metabolite_with_other_chemistry_is_renamed_not_merged():
    from thg_protocol.merge import generate_merge_plan

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

    plan = generate_merge_plan(base, incoming)
    assert plan.renamed == {"a_c": "a_c__incoming"}
    categories = {item.category: item for item in plan.decisions}
    assert categories["formula-conflict"].action == "keep-separate"
    assert "renamed to a_c__incoming" in categories["formula-conflict"].reason
    assert categories["reaction-stoichiometry-conflict"].action == "keep-base"

    merged, report = merge_models(base, incoming)
    reaction = merged.reactions.R1
    assert report.overlapping_metabolites == 0
    assert report.added_metabolites == 1
    assert report.overlapping_reactions == 1
    assert (merged.metabolites.a_c.formula, merged.metabolites.a_c.charge) == ("C1", 0)
    renamed = merged.metabolites.a_c__incoming
    assert (renamed.formula, renamed.charge) == ("C2", 1)
    assert reaction.bounds == (-1, 2)
    assert reaction.metabolites == {merged.metabolites.a_c: -1}
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


def _linked(base_formula, base_charge, formula, charge):
    from thg_protocol.merge import generate_merge_plan

    base = _model("base", "R1", "a_c")
    incoming = _model("incoming", "R2", "b_c")
    base.metabolites.a_c.formula, base.metabolites.a_c.charge = (
        base_formula,
        base_charge,
    )
    incoming.metabolites.b_c.formula, incoming.metabolites.b_c.charge = (
        formula,
        charge,
    )
    base.metabolites.a_c.annotation = {"chebi": "1"}
    incoming.metabolites.b_c.annotation = {"chebi": "1"}
    return generate_merge_plan(base, incoming)


def test_linked_metabolites_merge_only_with_identical_formula_and_charge():
    assert _linked("C1H2", 0, "C1H2", 0).metabolite_map == {"b_c": "a_c"}
    assert _linked("CH2", 0, "C1H2", 0).metabolite_map == {"b_c": "a_c"}
    # Unknown on both sides is not a difference.
    assert _linked("C1", None, "C1", None).metabolite_map == {"b_c": "a_c"}
    for chemistry, category in (
        (("C1H3", 0, "C1H2", -1), "protonation-conflict"),
        (("C1H2", 0, "C1H3", 0), "protonation-conflict"),
        (("C1H2", 0, "C1H2", 1), "charge-conflict"),
        (("C1H2", 0, "C2H2", 0), "formula-conflict"),
        (("C1H2", 0, None, 0), "missing-chemistry"),
        (("C1H2", 0, "C1H2", None), "missing-chemistry"),
    ):
        plan = _linked(*chemistry)
        assert plan.metabolite_map == {}, chemistry
        (decision,) = plan.decisions
        assert (decision.category, decision.action) == (category, "keep-separate")
        assert decision.reason.startswith("chebi:1; formula ")
        assert plan.renamed == {}  # different IDs need no rename


def test_same_chemistry_with_disjoint_kegg_ids_is_an_identifier_conflict():
    from thg_protocol.merge import generate_merge_plan

    base = _model("base", "R1", "a_c")
    incoming = _model("incoming", "R2", "b_c")
    base.metabolites.a_c.annotation = {"chebi": "1", "kegg.compound": "C11713"}
    incoming.metabolites.b_c.annotation = {"chebi": "1", "kegg.compound": "C06428"}
    plan = generate_merge_plan(base, incoming)
    assert plan.metabolite_map == {}
    (decision,) = plan.decisions
    assert decision.category == "identifier-conflict"
    assert "kegg.compound" in decision.reason


def test_protonation_variants_keep_their_own_balanced_reactions():
    base = cobra.Model("base")
    acid = cobra.Metabolite("x_c", compartment="c", formula="C2H4O2", charge=0)
    product = cobra.Metabolite("p_c", compartment="c", formula="C2H4O2", charge=0)
    reaction = cobra.Reaction("R_base")
    reaction.add_metabolites({acid: -1, product: 1})
    base.add_reactions([reaction])

    incoming = cobra.Model("incoming")
    anion = cobra.Metabolite("x_c", compartment="c", formula="C2H3O2", charge=-1)
    proton = cobra.Metabolite("h_c", compartment="c", formula="H", charge=1)
    product = cobra.Metabolite("p_c", compartment="c", formula="C2H4O2", charge=0)
    reaction = cobra.Reaction("R_incoming")
    reaction.add_metabolites({anion: -1, proton: -1, product: 1})
    incoming.add_reactions([reaction])

    merged, _ = merge_models(base, incoming)
    assert merged.metabolites.x_c.formula == "C2H4O2"
    assert merged.metabolites.x_c__incoming.formula == "C2H3O2"
    for reaction_id in ("R_base", "R_incoming"):
        assert not merged.reactions.get_by_id(reaction_id).check_mass_balance()


def test_annotation_linked_reactions_need_identical_protons():
    from thg_protocol.merge import generate_merge_plan

    def model(model_id, reaction_id, protons):
        result = cobra.Model(model_id)
        a = cobra.Metabolite("a_c", compartment="c", formula="C1", charge=0)
        h = cobra.Metabolite("h_c", compartment="c", formula="H", charge=1)
        reaction = cobra.Reaction(reaction_id)
        reaction.add_metabolites({a: -1, h: protons})
        reaction.annotation["kegg.reaction"] = "R00001"
        result.add_reactions([reaction])
        return result

    plan = generate_merge_plan(model("base", "R1", 1), model("incoming", "R2", 1))
    assert plan.reaction_map == {"R2": "R1"}
    plan = generate_merge_plan(model("base", "R1", 1), model("incoming", "R2", 2))
    assert plan.reaction_map == {}
    assert [
        item.category for item in plan.decisions if "reaction" in item.category
    ] == ["reaction-stoichiometry-conflict"]


def _atp_model(model_id, prefix):
    model = cobra.Model(model_id)
    for compartment in ("c", "m"):
        metabolite = cobra.Metabolite(
            f"{prefix}atp_{compartment}", compartment=compartment, formula="C10"
        )
        metabolite.annotation = {"kegg.compound": "C00002", "chebi": "CHEBI:30616"}
        model.add_metabolites([metabolite])
    return model


def test_shared_identifiers_pair_metabolites_within_each_compartment():
    from thg_protocol.merge import generate_merge_plan

    plan = generate_merge_plan(_atp_model("base", "x"), _atp_model("incoming", "y"))
    assert plan.metabolite_map == {"yatp_c": "xatp_c", "yatp_m": "xatp_m"}
    mapped = [item for item in plan.decisions if item.category.startswith("metab")]
    assert [(item.left_id, item.right_id) for item in mapped] == [
        ("xatp_c", "yatp_c"),
        ("xatp_m", "yatp_m"),
    ]
    assert mapped[0].reason == "chebi:CHEBI:30616, kegg.compound:C00002"


def test_identifiers_pairing_one_metabolite_with_two_are_ambiguous():
    from thg_protocol.merge import generate_merge_plan

    base = _model("base", "R1", "a_c")
    base.add_metabolites([cobra.Metabolite("b_c", compartment="c", formula="C1")])
    base.metabolites.a_c.annotation = {"chebi": "1"}
    base.metabolites.b_c.annotation = {"hmdb": "H1"}
    incoming = _model("incoming", "R2", "z_c")
    incoming.metabolites.z_c.annotation = {"chebi": "1", "hmdb": "H1"}
    plan = generate_merge_plan(base, incoming)
    assert plan.metabolite_map == {}
    (decision,) = plan.decisions
    assert (decision.category, decision.left_id, decision.right_id) == (
        "ambiguous-metabolite",
        "a_c,b_c",
        "z_c",
    )
    assert decision.reason == "chebi:1, hmdb:H1"


def test_shared_annotations_do_not_compete_with_matching_ids():
    from thg_protocol.merge import generate_merge_plan

    def model(model_id):
        result = cobra.Model(model_id)
        for metabolite_id in ("a_c", "b_c"):  # duplicate ChEBI in one compartment
            metabolite = cobra.Metabolite(metabolite_id, compartment="c", formula="C1")
            metabolite.annotation = {"chebi": "1"}
            result.add_metabolites([metabolite])
        return result

    plan = generate_merge_plan(model("base"), model("incoming"))
    assert plan.metabolite_map == {"a_c": "a_c", "b_c": "b_c"}
    assert {item.category for item in plan.decisions} == {"metabolite-equivalence"}
