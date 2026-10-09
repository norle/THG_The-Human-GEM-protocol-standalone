from thg_protocol.gapfill import (
    gapfill_model,
    generate_gapfill_plan,
    run_gapfill,
)
from thg_protocol.gapfill.cli import build_parser, main
from thg_protocol.gapfill.core import _transport_candidates


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


def test_gapfill_model_is_non_mutating():
    model = toy_model()
    result = gapfill_model(
        model,
        method="greedy",
        parameters={"max_additions": 1, "allowed_connections": [["c", "e"]]},
    )
    assert result.status == "partial"
    assert result.selected
    assert len(model["reactions"]) == 2


def test_gapfill_cli_help_is_import_safe(capsys):
    try:
        main(["--help"])
    except SystemExit as error:
        assert error.code == 0
    assert "THG JSON gapfill" in capsys.readouterr().out


def test_gapfill_is_non_mutating_and_records_coverage():
    model = toy_model()
    candidates = [
        {
            "id": "TG1",
            "metabolites": {"MAM00001c": -1, "MAM00001e": 1},
        }
    ]
    result = run_gapfill(model, candidates)
    assert result.status == "solved"
    assert result.selected == ["TG1"]
    assert result.candidate_coverage == {"TG1": "selected"}
    assert len(model["reactions"]) == 2
    assert len(result.model["reactions"]) == 3


def test_gapfill_reports_invalid_candidate_without_partial_mutation():
    result = run_gapfill(
        toy_model(),
        [{"id": "bad", "metabolites": {"missing": -1}}],
    )
    assert result.status == "failed"
    assert "unknown metabolites" in result.failure
    assert result.selected == []


def test_standalone_gapfill_is_non_mutating_and_reuses_reversible_transport():
    model = toy_model()
    model["reactions"].append(
        {
            "id": "existing_transport",
            "metabolites": {"MAM00001e": 2, "MAM00001c": -2},
            "lower_bound": -1000,
            "upper_bound": 1000,
        }
    )
    result = gapfill_model(
        model,
        method="greedy",
        parameters={"allowed_connections": [["c", "e"]]},
    )
    assert result.status == "solved"
    assert result.candidate_coverage["GAPFILL_MAM00001c_MAM00001e"] == "already-present"
    assert all(
        reaction["id"] != "GAPFILL_MAM00002c_MAM00002e"
        for reaction in model["reactions"]
    )


def test_transport_gapfill_rejects_empty_allowed_connections():
    result = gapfill_model(
        toy_model(),
        method="greedy",
        parameters={"max_additions": 1, "allowed_connections": []},
    )
    assert result.status == "failed"
    assert "allowed_connections" in result.failure


def test_sink_milp_requires_allowed_connections():
    for parameters in ({}, {"allowed_connections": []}):
        result = gapfill_model(toy_model(), method="sink-milp", parameters=parameters)
        assert result.status == "failed"
        assert "allowed_connections" in result.failure


def test_sink_milp_rejects_milp_only_parameters():
    result = gapfill_model(
        toy_model(),
        method="sink-milp",
        parameters={"allowed_connections": [["c", "e"]], "objective": "R1"},
    )
    assert result.status == "failed"
    assert "objective" in result.failure


def test_generate_plan_accepts_precomputed_result():
    model = toy_model()
    parameters = {"max_additions": 1, "allowed_connections": [["c", "e"]]}
    result = gapfill_model(model, method="greedy", parameters=parameters)
    result.selected = []
    plan = generate_gapfill_plan(
        model, method="greedy", parameters=parameters, result=result
    )
    assert plan["proposals"] == []


def test_sink_milp_rejects_lambda_outside_unit_interval():
    for lam in (0, 1, 1.5):
        result = gapfill_model(
            toy_model(),
            method="sink-milp",
            parameters={"allowed_connections": [["c", "e"]], "tradeoff_lambda": lam},
        )
        assert result.status == "failed"
        assert "tradeoff_lambda" in result.failure


def test_cli_accepts_sink_milp():
    args = build_parser().parse_args(
        ["--model", "m.json", "--method", "sink-milp", "--output-dir", "out"]
    )
    assert args.method == "sink-milp"


def test_transport_candidates_pair_every_metabolite_once_in_any_order():
    model = toy_model()
    model["compartments"]["m"] = "mitochondrion"
    model["metabolites"] = [
        {"id": "MAM00001m", "compartment": "m"},
        {"id": "MAM00001c", "compartment": "c"},
        {"id": "MAM00001e", "compartment": "e"},
    ]
    model["reactions"] = []
    candidates = _transport_candidates(
        model, [("c", "e"), ("c", "m"), ("e", "m")], ["A", "B", "C"]
    )
    assert [candidate.id for candidate in candidates] == [
        "GAPFILL_MAM00001c_MAM00001e",
        "GAPFILL_MAM00001c_MAM00001m",
        "GAPFILL_MAM00001e_MAM00001m",
    ]


def test_run_gapfill_rejects_existing_ids_for_dict_and_cobra_models():
    from cobra.io import model_from_dict

    mapped = toy_model()
    for source in (mapped, model_from_dict({**mapped, "genes": []})):
        result = run_gapfill(
            source, [{"id": "R1", "metabolites": {"MAM00001c": -1, "MAM00001e": 1}}]
        )
        assert result.status == "failed"
        assert result.selected == []
        assert result.candidate_coverage["R1"] == "invalid-collision"
        assert (
            len(
                result.model["reactions"]
                if isinstance(result.model, dict)
                else result.model.reactions
            )
            == 2
        )


def test_run_gapfill_failure_rolls_back_earlier_valid_candidates():
    from cobra.io import model_from_dict

    mapped = toy_model()
    candidates = [
        {"id": "valid", "metabolites": {"MAM00001c": -1, "MAM00001e": 1}},
        {"id": "invalid", "metabolites": {"missing": -1}},
    ]
    for source in (mapped, model_from_dict({**mapped, "genes": []})):
        result = run_gapfill(source, candidates)
        assert result.status == "failed"
        assert result.selected == []
        assert (
            len(
                result.model["reactions"]
                if isinstance(result.model, dict)
                else result.model.reactions
            )
            == 2
        )


def test_run_gapfill_ignores_collisions_outside_the_selection():
    candidates = [
        {"id": "valid", "cost": 1, "metabolites": {"MAM00001c": -1, "MAM00001e": 1}},
        {"id": "R1", "cost": 2, "metabolites": {"MAM00002c": -1, "MAM00002e": 1}},
    ]
    result = run_gapfill(toy_model(), candidates, max_additions=1)
    assert result.status == "solved"
    assert result.selected == ["valid"]
    assert result.candidate_coverage["R1"] == "invalid-collision"


def test_transport_candidates_fall_back_to_suffix_without_compartments():
    mapped = toy_model()
    for metabolite in mapped["metabolites"]:
        del metabolite["compartment"]
    candidates = _transport_candidates(mapped, [("c", "e")], ["A", "B", "C"])
    assert [candidate.id for candidate in candidates] == [
        "GAPFILL_MAM00001c_MAM00001e",
        "GAPFILL_MAM00002c_MAM00002e",
    ]
