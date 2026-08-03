import json

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
