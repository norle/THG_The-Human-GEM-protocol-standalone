import json

import pytest

from thg_protocol import config


def test_load_config_resolves_relative_path_from_cwd(tmp_path, monkeypatch):
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"model": {"base": "base.xml"}}))
    monkeypatch.chdir(tmp_path)

    loaded_config = config.load_config("config.json")

    assert loaded_config == {"model": {"base": "base.xml"}}


def test_get_model_paths_resolves_relative_paths_from_project_root():
    base_path, output_path = config.get_model_paths(
        {"model": {"base": "models/base.xml", "output": "models/output.xml"}}
    )

    assert base_path == str(config.get_project_root() / "models/base.xml")
    assert output_path == str(config.get_project_root() / "models/output.xml")


def test_get_compartments_validates_required_fields():
    with pytest.raises(ValueError, match="Invalid compartment definition"):
        config.get_compartments({"compartments": [{"name": "cytosol"}]})


def test_resolve_compartment_abbreviation_matches_name_or_abbreviation():
    model = {"compartments": {"c": "Cytosol", "m": "Mitochondria"}}

    resolved_by_name = config.resolve_compartment_abbreviation(
        model,
        {"name": "cytosol", "abbreviation": "x"},
    )
    resolved_by_abbreviation = config.resolve_compartment_abbreviation(
        model,
        {"name": "Different", "abbreviation": "m"},
    )

    assert resolved_by_name["exists"] is True
    assert resolved_by_name["abbreviation"] == "c"
    assert resolved_by_abbreviation["exists"] is True
    assert resolved_by_abbreviation["abbreviation"] == "m"


def test_resolve_compartment_abbreviation_reports_missing_compartment():
    resolved = config.resolve_compartment_abbreviation(
        {"compartments": {"c": "Cytosol"}},
        {"name": "peroxisome", "abbreviation": "p"},
    )

    assert resolved == {
        "abbreviation": "p",
        "exists": False,
        "existing_abbrev": None,
        "name": "peroxisome",
    }


def test_legacy_functions_config_wrapper_exports_package_api():
    from functions import config as legacy_config

    assert legacy_config.load_config is config.load_config
    assert legacy_config.get_model_paths is config.get_model_paths


def test_legacy_functions_package_imports_without_pathway_side_effects():
    import functions

    assert functions.load_config is config.load_config
    assert "add_compartment" in functions.__all__
