import json
import os

import pytest

from thg_protocol import config
from thg_protocol.config import load_environment_files
from thg_protocol.workflow.config import ConfigError, load_workflow_config


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


def test_load_environment_files_does_not_override_process_environment(
    tmp_path, monkeypatch
):
    dotenv = tmp_path / ".env"
    dotenv.write_text(
        "# comment\n"
        "export BIOCYC_EMAIL=file@example.com\n"
        "BIOCYC_PASSWORD='secret value'\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("BIOCYC_EMAIL", "process@example.com")
    monkeypatch.delenv("BIOCYC_PASSWORD", raising=False)

    loaded = load_environment_files([dotenv])

    assert loaded == (dotenv.resolve(),)
    assert os.environ["BIOCYC_EMAIL"] == "process@example.com"
    assert os.environ["BIOCYC_PASSWORD"] == "secret value"


def test_load_environment_files_checks_cwd_before_package_root(tmp_path, monkeypatch):
    cwd = tmp_path / "cwd"
    package = tmp_path / "package"
    cwd.mkdir()
    package.mkdir()
    (cwd / ".env").write_text("THG_DOTENV_ORDER=cwd\n", encoding="utf-8")
    (package / ".env").write_text("THG_DOTENV_ORDER=package\n", encoding="utf-8")
    monkeypatch.chdir(cwd)
    monkeypatch.setattr(config, "get_project_root", lambda: package)
    monkeypatch.delenv("THG_ENV_FILE", raising=False)
    monkeypatch.delenv("THG_DOTENV_ORDER", raising=False)

    loaded = load_environment_files()

    assert loaded == ((cwd / ".env").resolve(), (package / ".env").resolve())
    assert os.environ["THG_DOTENV_ORDER"] == "cwd"


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


def test_beta2_go_targets_are_validated_at_load_time(tmp_path):
    path = tmp_path / "beta2.json"
    path.write_text(
        json.dumps(
            {
                "workflow": "beta2",
                "run": {"name": "check", "output_dir": str(tmp_path / "run")},
                "beta2": {
                    "compartments": {"x": "Mitochondria", "y": "Cytosol"},
                    "compartment_go_terms": {
                        "x": "GO:0005739",
                        "y": "GO:0005739",
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match="must be unique"):
        load_workflow_config(path)
