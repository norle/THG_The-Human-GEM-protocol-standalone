import json

from thg_protocol.gapfill import (
    DeterministicGapfillStrategy,
    MILPGapfillStrategy,
    generate_candidates,
    run_gapfill,
    run_pipeline,
)
from thg_protocol.gapfill.cli import main


def toy_model():
    return {
        "compartments": {"c": "cytosol", "e": "extracellular"},
        "metabolites": [
            {"id": "MAM00001c", "name": "A", "compartment": "c"},
            {"id": "MAM00001e", "name": "A", "compartment": "e"},
            {"id": "MAM00002c", "name": "B", "compartment": "c"},
            {"id": "MAM00002e", "name": "B", "compartment": "e"},
        ],
        "reactions": [
            {"id": "R1", "metabolites": {"MAM00001c": -1, "MAM00002c": 1}},
            {"id": "R2", "metabolites": {"MAM00001e": -1, "MAM00002e": 1}},
        ],
    }


def test_gapfill_candidates_and_pipeline_write_explicit_outputs(tmp_path):
    model_path = tmp_path / "model.json"
    model_path.write_text(json.dumps(toy_model()))
    result = run_pipeline(model_path, tmp_path / "out", max_additions=1)
    assert result["model"].exists()
    assert (tmp_path / "out" / "candidates_all.csv").exists()
    assert generate_candidates(toy_model())


def test_gapfill_cli_help_is_import_safe(capsys):
    try:
        main(["--help"])
    except SystemExit as error:
        assert error.code == 0
    assert "THG JSON gapfill" in capsys.readouterr().out


def test_strategy_contract_is_non_mutating_and_records_coverage():
    model = toy_model()
    candidates = [
        {
            "id": "TG1",
            "metabolites": {"MAM00001c": -1, "MAM00001e": 1},
        }
    ]
    result = run_gapfill(model, candidates, strategy=DeterministicGapfillStrategy())
    assert result.status == "solved"
    assert result.selected == ["TG1"]
    assert result.candidate_coverage == {"TG1": "selected"}
    assert len(model["reactions"]) == 2
    assert len(result.model["reactions"]) == 3
    milp = run_gapfill(model, candidates, strategy=MILPGapfillStrategy())
    assert milp.solver["temporary_reactions"] == 0


def test_gapfill_reports_invalid_candidate_without_partial_mutation():
    result = run_gapfill(
        toy_model(),
        [{"id": "bad", "metabolites": {"missing": -1}}],
    )
    assert result.status == "failed"
    assert "unknown metabolites" in result.failure
    assert result.selected == []
