import inspect
import json

import pytest

import thg_protocol.annotation.metabolites as metabolites
from thg_protocol.services.pubchem import PubChemCompound, StaticPubChemClient


class StopAfterCheckpoint(BaseException):
    """Test-only interruption that pytest does not treat as SIGINT."""


def test_metabolite_annotation_api_exposes_characterized_helper_names():
    assert "identify_metabolite" in metabolites.__all__
    assert "formula_similarity" in metabolites.__all__
    assert "process_annotation" in metabolites.__all__
    assert (
        inspect.signature(metabolites.generate_met_annotation).parameters["out"].default
        is inspect.Parameter.empty
    )
    assert (
        inspect.signature(metabolites.process_annotation)
        .parameters["annotation_file"]
        .default
        is inspect.Parameter.empty
    )


def test_legacy_annotation_file_helper_uses_canonical_snapshot():
    assert metabolites.global_met_annotation_file().endswith(
        "supplementary_material/metabolite_reaction/met_annotation.tsv"
    )


def test_generate_met_annotation_passes_an_injected_pubchem_client(tmp_path):
    output = tmp_path / "met_annotation.tsv"
    client = StaticPubChemClient(
        {
            "glucose": PubChemCompound(
                5793, "C6H12O6", ("glucose", "C00031"), "InChI=1S/glucose", "KEY"
            )
        }
    )

    annotated, unannotated = metabolites.generate_met_annotation(
        [("glucose", "C6H12O6", "", "MAM00001c")],
        out=output,
        client=client,
        delay_between_requests=0,
    )

    assert len(annotated) == 1
    assert not unannotated
    assert "5793" in output.read_text()
    assert (tmp_path / "met_annotation_failures.tsv").exists()


def test_generate_met_annotation_resumes_from_an_input_fingerprinted_checkpoint(
    tmp_path, monkeypatch
):
    output = tmp_path / "met_annotation.tsv"
    records = [
        ("first", "C1", "", "M1"),
        ("second", "C2", "", "M2"),
        ("third", "C3", "", "M3"),
    ]
    calls = []

    def interrupted(name, formula, identifier, *, client):
        del client
        calls.append(name)
        if name == "second" and calls.count(name) == 1:
            raise StopAfterCheckpoint
        return f"{name}\t\t{formula}\t\t\t\t{identifier}\n"

    monkeypatch.setattr(metabolites, "identify_metabolite", interrupted)
    with pytest.raises(StopAfterCheckpoint):
        metabolites.generate_met_annotation(
            records,
            output,
            delay_between_requests=0,
            checkpoint_interval=1,
        )

    checkpoint = tmp_path / "met_annotation.checkpoint.json"
    saved = json.loads(checkpoint.read_text())
    assert saved["format_version"] == 2
    assert saved["next_index"] == 1
    assert not output.exists()

    annotated, unannotated = metabolites.generate_met_annotation(
        records,
        output,
        delay_between_requests=0,
        checkpoint_interval=1,
    )

    assert [record[0] for record in annotated] == ["first", "second", "third"]
    assert not unannotated
    assert not checkpoint.exists()
    assert output.read_text().count("\n") == 3
    assert calls == ["first", "second", "second", "third"]


def test_generate_met_annotation_rejects_a_checkpoint_for_different_input(
    tmp_path, monkeypatch
):
    output = tmp_path / "met_annotation.tsv"

    def interrupted(name, formula, identifier, *, client):
        del client
        if name == "second":
            raise StopAfterCheckpoint
        return f"{name}\t\t{formula}\t\t\t\t{identifier}\n"

    monkeypatch.setattr(metabolites, "identify_metabolite", interrupted)
    with pytest.raises(StopAfterCheckpoint):
        metabolites.generate_met_annotation(
            [("first", "C1", "", "M1"), ("second", "C2", "", "M2")],
            output,
            delay_between_requests=0,
            checkpoint_interval=1,
        )

    with pytest.raises(ValueError, match="does not match"):
        metabolites.generate_met_annotation(
            [("first", "C1", "", "M1"), ("different", "C2", "", "M2")],
            output,
            delay_between_requests=0,
        )


def test_generate_met_annotation_honors_request_delay(tmp_path, monkeypatch):
    sleep_calls = []

    def fake_sleep(seconds):
        sleep_calls.append(seconds)

    def identified(name, formula, identifier, *, client):
        del client
        return f"{name}\t\t{formula}\t\t\t\t{identifier}\n"

    monkeypatch.setattr(metabolites.time, "sleep", fake_sleep)
    monkeypatch.setattr(metabolites, "identify_metabolite", identified)
    metabolites.generate_met_annotation(
        [("first", "C1", "", "M1"), ("second", "C2", "", "M2")],
        tmp_path / "met_annotation.tsv",
        delay_between_requests=0.25,
    )

    assert sleep_calls == [0.25]
