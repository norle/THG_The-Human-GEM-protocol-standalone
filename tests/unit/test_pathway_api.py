import thg_protocol.pathway as pathway


def test_pathway_api_exposes_legacy_public_helper_names():
    assert "add_compartment" in pathway.__all__
    assert "check_pathway_exists" in pathway.__all__
    assert "get_next_metabolite_id" in pathway.__all__
    assert "get_next_reaction_id" in pathway.__all__


def test_pathway_helpers_preserve_current_pure_behavior():
    model = {
        "compartments": {"c": "cytosol"},
        "metabolites": [
            {"id": "MAM00001c", "compartment": "c"},
            {"id": "MAM00027gc", "compartment": "gc"},
        ],
        "reactions": [
            {"id": "MAR00002", "metabolites": {"MAM00027gc": -1.0}},
            {"id": "MAR00009", "metabolites": {"MAM00001c": 1.0}},
        ],
    }

    updated_model, used_abbrev, already_existed = pathway.add_compartment(
        model, "gc", "glycocalyx"
    )

    assert updated_model is model
    assert used_abbrev == "gc"
    assert already_existed is False
    assert model["compartments"]["gc"] == "glycocalyx"
    assert pathway.get_next_metabolite_id(model) == "MAM00028"
    assert pathway.get_next_reaction_id(model) == "MAR00010"
    assert pathway.check_pathway_exists(model, "gc") == {
        "has_compartment": True,
        "compartment": "glycocalyx",
        "metabolite_count": 1,
        "reaction_count": 1,
        "metabolites": ["MAM00027gc"],
        "reactions": ["MAR00002"],
    }


def test_find_metabolite_robust_can_copy_formula_match_to_target_compartment():
    model = {
        "compartments": {"c": "cytosol", "gc": "glycocalyx"},
        "metabolites": [
            {
                "id": "MAM01234c",
                "name": "Example metabolite",
                "compartment": "c",
                "formula": "C2H4O2",
                "charge": -1,
                "annotation": {"kegg.compound": "C00001", "chebi": "123"},
            },
        ],
        "reactions": [],
    }

    metabolite = pathway.find_metabolite_robust(
        model,
        "example metabolite",
        {},
        compartment="gc",
        auto_create=True,
    )

    assert metabolite == {
        "id": "MAM01234gc",
        "name": "Example metabolite",
        "compartment": "gc",
        "formula": "C2H4O2",
        "charge": -1,
        "annotation": {"kegg.compound": "C00001", "chebi": "123"},
    }
    assert len(model["metabolites"]) == 2


def test_parse_reaction_equation_preserves_names_with_plus_signs():
    parsed = pathway.parse_reaction_equation(
        "2 ATP[c] + H+[m] <=> ADP[c] + H2O[m]"
    )

    assert parsed == {
        "reversible": True,
        "terms": [
            {"name": "ATP", "compartment": "c", "stoich": -2.0},
            {"name": "H+", "compartment": "m", "stoich": -1.0},
            {"name": "ADP", "compartment": "c", "stoich": 1.0},
            {"name": "H2O", "compartment": "m", "stoich": 1.0},
        ],
    }


def test_parse_universal_reaction_resolves_model_metabolites():
    model = {
        "compartments": {"c": "cytosol"},
        "metabolites": [
            {"id": "MAM00001c", "name": "ATP", "compartment": "c"},
            {"id": "MAM00002c", "name": "ADP", "compartment": "c"},
        ],
        "reactions": [],
    }

    reaction = pathway.parse_universal_reaction(
        "2 ATP[c] --> ADP[c]", model, {}
    )

    assert reaction == {
        "metabolites": {"MAM00001c": -2.0, "MAM00002c": 1.0},
        "reversible": False,
    }


def test_pathway_configuration_helpers_select_and_translate_without_mutation():
    config = {
        "metabolites": {
            "specific": {
                "Example": {"compartment": "gl", "formula": "C2"},
                "Other": {"compartment": "c", "formula": "C3"},
            }
        }
    }

    selected = pathway.select_pathway_metabolites(
        config, "specific", "gc", {"gl": "gc"}
    )

    assert selected == {"Example": {"compartment": "gl", "formula": "C2"}}
    assert config["metabolites"]["specific"]["Example"]["compartment"] == "gl"
    assert pathway.substitute_compartment_abbreviations(
        "A[gl] --> B[c]", {"gl": "gc"}
    ) == "A[gc] --> B[c]"


def test_build_reaction_from_config_maps_optional_fields():
    reaction = pathway.build_reaction_from_config(
        {
            "id": "MAR00001",
            "name": "Example",
            "gpr": "geneA",
            "notes": "A note",
            "ec": "1.2.3.4",
            "sbo": "SBO:0000176",
        },
        {"metabolites": {"MAM00001c": -1.0}},
    )

    assert reaction == {
        "id": "MAR00001",
        "name": "Example",
        "metabolites": {"MAM00001c": -1.0},
        "lower_bound": 0.0,
        "upper_bound": 1000.0,
        "gene_reaction_rule": "geneA",
        "subsystem": "",
        "notes": {"description": "A note"},
        "annotation": {"ec-code": "1.2.3.4", "sbo": "SBO:0000176"},
    }


def test_create_compartment_metabolites_promotes_targets_and_configured_entries():
    model = {
        "compartments": {"c": "cytosol", "gc": "glycocalyx"},
        "metabolites": [
            {
                "id": "MAM00001c",
                "name": "ATP",
                "compartment": "c",
                "formula": "C10H16N5O13P3",
            }
        ],
        "reactions": [],
    }
    config = {
        "metabolites": {
            "targets": {"ATP": {}},
            "specific": {
                "Carrier": {
                    "compartment": "gl",
                    "formula": "C2H4",
                    "chebi": "123",
                }
            },
        },
        "reactions": [{"equation": "ATP[gc] --> Carrier[gc]"}],
    }

    count = pathway.create_compartment_metabolites(
        model, {}, "gc", config, "specific", {"gl": "gc"}
    )

    assert count == 2
    assert {metabolite["id"] for metabolite in model["metabolites"]} == {
        "MAM00001c",
        "MAM00001gc",
        "MAM00002gc",
    }
    assert model["metabolites"][-1]["annotation"] == {"chebi": "123"}


def test_create_compartment_reactions_uses_package_builder():
    model = {
        "compartments": {"c": "cytosol"},
        "metabolites": [
            {"id": "MAM00001c", "name": "A", "compartment": "c"},
            {"id": "MAM00002c", "name": "B", "compartment": "c"},
        ],
        "reactions": [],
    }
    config = {
        "reactions": [
            {"id": "MAR00001", "equation": "A[c] --> B[c]", "name": "A to B"}
        ]
    }

    assert pathway.create_compartment_reactions(model, {}, "c", config) == 1
    assert model["reactions"][0]["id"] == "MAR00001"
