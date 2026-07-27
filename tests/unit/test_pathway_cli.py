import json

from thg_protocol.pathway.cli import main


def test_pathway_cli_help_is_import_safe(capsys):
    try:
        main(["--help"])
    except SystemExit as error:
        assert error.code == 0
    assert "Implement configured pathway components" in capsys.readouterr().out


def test_implement_pathway_files_writes_output(tmp_path):
    model = {
        "compartments": {"c": "cytosol"},
        "metabolites": [
            {"id": "MAM00001c", "name": "A", "compartment": "c", "formula": "C"},
            {"id": "MAM00002c", "name": "B", "compartment": "c", "formula": "C"},
        ],
        "reactions": [],
    }
    config = {
        "compartments": [{"abbreviation": "c", "name": "cytosol"}],
        "reactions": [{"id": "MAR00001", "equation": "A[c] --> B[c]"}],
    }
    model_path = tmp_path / "model.json"
    config_path = tmp_path / "config.json"
    database_path = tmp_path / "database.json"
    output_path = tmp_path / "out" / "model.json"
    for path, value in (
        (model_path, model),
        (config_path, config),
        (database_path, {}),
    ):
        path.write_text(json.dumps(value))

    import thg_protocol.pathway as pathway

    result = pathway.implement_pathway_files(
        model_path, config_path, database_path, output_path
    )

    assert result["reactions_added"] == 1
    assert json.loads(output_path.read_text())["reactions"][0]["id"] == "MAR00001"
