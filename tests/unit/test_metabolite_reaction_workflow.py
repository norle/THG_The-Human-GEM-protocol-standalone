import importlib

import pytest

from thg_protocol.annotation.metabolite_reactions import (
    retry_metabolite_annotations,
)
from thg_protocol.services.pubchem import PubChemCompound, StaticPubChemClient


def test_metabolite_reaction_workflow_import_is_safe_without_cobra():
    workflow = importlib.import_module(
        "thg_protocol.annotation.metabolite_reactions"
    )

    assert callable(workflow.run_metabolite_reaction_identification)


def test_legacy_annotation_wrapper_is_import_safe():
    legacy = importlib.import_module("functions.function_annotate_cobra_model")

    assert callable(legacy.annotate_cobra_model)


def test_retry_annotations_uses_static_client_and_rewrites_failures(tmp_path):
    annotation_path = tmp_path / "met_annotation.tsv"
    annotation_path.write_text("", encoding="utf-8")
    failure_path = tmp_path / "met_annotation_failures.tsv"
    records = [
        ("ATP", "C10H16N5O13P3", {}, "MAM00001"),
        ("unknown", "H2O", {}, "MAM00002"),
    ]
    client = StaticPubChemClient(
        {
            "ATP": PubChemCompound(
                cid=5957,
                molecular_formula="C10H16N5O13P3",
                synonyms=("ATP", "C00002"),
                inchi="InChI=1S/test",
                inchikey="TEST",
            )
        }
    )

    result = retry_metabolite_annotations(
        records,
        annotation_path,
        failure_path,
        pubchem_client=client,
        max_rounds=3,
        stop_threshold=0,
        total_metabolite_count=2,
    )

    assert result.annotated == (records[0],)
    assert result.unannotated == (records[1],)
    assert result.rounds_executed == 2
    assert "C00002" in annotation_path.read_text(encoding="utf-8")
    failures = failure_path.read_text(encoding="utf-8")
    assert "unknown\tH2O\tMAM00002\tretry_exhausted" in failures
    assert "ATP" not in failures


@pytest.mark.parametrize(
    ("max_rounds", "stop_threshold"),
    [(-1, 0.1), (1, -0.1), (1, 1.1)],
)
def test_retry_annotations_validates_configuration(
    tmp_path, max_rounds, stop_threshold
):
    with pytest.raises(ValueError):
        retry_metabolite_annotations(
            [],
            tmp_path / "annotations.tsv",
            tmp_path / "failures.tsv",
            pubchem_client=StaticPubChemClient(),
            max_rounds=max_rounds,
            stop_threshold=stop_threshold,
        )
