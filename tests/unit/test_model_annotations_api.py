import json

from functions.analyze_annotations import build_parser
from functions.build_id_database import (
    build_database_from_model,
    build_parser as database_parser,
)
from thg_protocol.annotation import (
    analyze_model_annotations,
    extract_metabolite_annotations,
)


def test_model_annotation_analysis_is_explicit_and_non_mutating(tmp_path):
    model_path = tmp_path / "model.json"
    model_path.write_text(
        json.dumps(
            {
                "metabolites": [
                    {
                        "name": "ATP",
                        "compartment": "c",
                        "annotation": {"kegg.compound": ["C00002"]},
                        "inchi": "InChI=1S/test",
                    },
                    {
                        "name": "ATP mitochondrial",
                        "compartment": "m",
                        "annotation": {"chebi": ["CHEBI:1", "CHEBI:2"]},
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    assert analyze_model_annotations(model_path) == {"kegg.compound": 1, "chebi": 1}
    extracted, missing = extract_metabolite_annotations(
        model_path, ["ATP", "mitochondrial", "unknown"]
    )
    assert extracted["ATP"] == {
        "kegg.compound": "C00002",
        "inchi": "InChI=1S/test",
    }
    assert missing == ["mitochondrial", "unknown"]


def test_annotation_cli_requires_explicit_targets():
    target = next(
        action for action in build_parser()._actions if action.dest == "target"
    )
    assert target.required is True


def test_legacy_database_builder_uses_explicit_model_targets_and_output(tmp_path):
    model_path = tmp_path / "model.json"
    output = tmp_path / "nested" / "database.json"
    model_path.write_text(
        json.dumps(
            {
                "metabolites": [
                    {
                        "name": "ATP",
                        "compartment": "c",
                        "annotation": {"kegg.compound": ["C00002"]},
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    database = build_database_from_model(model_path, ["ATP"], output)
    assert database["ATP"]["kegg.compound"] == "C00002"
    assert json.loads(output.read_text()) == database
    assert next(
        action for action in database_parser()._actions if action.dest == "output"
    ).required
