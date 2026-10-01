"""Behavioral contract for metabolic task evaluation (GLPK)."""

from __future__ import annotations

import json

import cobra
import pytest

from thg_protocol.tasks import (
    MetabolicTask,
    TaskSuite,
    load_task_suite,
    run_task,
    run_tasks,
    save_task_suite,
)

OPEN = {"lower_bound": 0, "upper_bound": 1000}


def network(objective: str = "free", direction: str = "max") -> cobra.Model:
    """a_e -> a_c -> b_c -> b_e, an unrelated exchange, and an unbounded loop."""
    model = cobra.Model("tasks")
    model.solver = "glpk"
    metabolites = {
        name: cobra.Metabolite(name, compartment=name[-1])
        for name in ("a_e", "a_c", "b_c", "b_e", "c_e", "x_c", "y_c")
    }

    def reaction(reaction_id, stoichiometry, bounds):
        item = cobra.Reaction(reaction_id, lower_bound=bounds[0], upper_bound=bounds[1])
        item.add_metabolites(
            {metabolites[key]: value for key, value in stoichiometry.items()}
        )
        return item

    model.add_reactions(
        [
            reaction("EX_a", {"a_e": -1}, (-10, 1000)),
            reaction("EX_b", {"b_e": -1}, (0, 1000)),
            reaction("EX_c", {"c_e": -1}, (-1000, 1000)),
            reaction("T_a", {"a_e": -1, "a_c": 1}, (0, 1000)),
            reaction("R1", {"a_c": -1, "b_c": 1}, (0, 1000)),
            reaction("T_b", {"b_c": -1, "b_e": 1}, (0, 1000)),
            reaction("free", {"x_c": -1, "y_c": 1}, (0, float("inf"))),
            reaction("free_back", {"y_c": -1, "x_c": 1}, (0, float("inf"))),
        ]
    )
    model.objective = objective
    model.objective_direction = direction
    return model


def task(**values) -> MetabolicTask:
    return MetabolicTask.from_mapping({"id": "task", **values})


def snapshot(model):
    return (
        [(item.id, tuple(item.bounds)) for item in model.reactions],
        [item.id for item in model.metabolites],
        str(model.objective.expression),
        model.objective.direction,
    )


def test_closed_medium_blocks_unlisted_boundaries():
    produce_b = {"outputs": {"b_e": [1, 1000]}}
    assert run_task(network(), task(**produce_b))["status"] == "failed"
    opened = task(**produce_b, inputs={"a_e": [0, 10]})
    assert run_task(network(), opened)["status"] == "passed"
    retained = task(**produce_b, medium="model")
    assert run_task(network(), retained)["status"] == "passed"
    # A model exchange can still be opened explicitly through bounds.
    reopened = task(**produce_b, bounds={"EX_a": [-10, 0]})
    assert run_task(network(), reopened)["status"] == "passed"


def test_inputs_and_outputs_on_internal_metabolites():
    converted = task(inputs={"a_c": [0, 10]}, outputs={"b_c": [1, 1000]})
    assert run_task(network(), converted)["status"] == "passed"
    unreachable = task(inputs={"b_c": [0, 10]}, outputs={"a_c": [1, 1000]})
    report = run_task(network(), unreachable)
    assert (report["status"], report["actual_outcome"]) == ("failed", "failure")


def test_feasibility_ignores_unbounded_input_objective():
    model = network("free")
    assert model.solver.optimize() == "unbounded"  # as given
    report = run_task(model, task(medium="model"))
    assert report["kind"] == "feasibility"
    assert report["status"] == "passed"
    assert report["solver_status"] == "optimal"
    assert report["objective_value"] is None


@pytest.mark.parametrize(
    ("threshold", "expected", "status", "outcome"),
    [
        (10, True, "passed", "success"),
        (11, True, "failed", "failure"),
        (11, False, "passed", "failure"),
    ],
)
def test_objective_threshold_with_opposing_input_direction(
    threshold, expected, status, outcome
):
    report = run_task(
        network("EX_b", "min"),
        task(
            inputs={"a_e": [0, 10]},
            outputs={"b_e": [0, 1000]},
            objective={
                "reaction": "TASK_OUT_b_e",
                "direction": "max",
                "threshold": threshold,
            },
            expected=expected,
        ),
    )
    assert report["kind"] == "objective"
    assert report["objective_value"] == pytest.approx(10)
    assert (report["status"], report["actual_outcome"]) == (status, outcome)
    assert report["expected_outcome"] == ("success" if expected else "failure")


@pytest.mark.parametrize(("threshold", "status"), [(4, "passed"), (3, "failed")])
def test_minimize_objective_threshold(threshold, status):
    report = run_task(
        network(),
        task(
            inputs={"a_e": [0, 10]},
            outputs={"b_e": [4, 1000]},
            objective={
                "reaction": "TASK_IN_a_e",
                "direction": "min",
                "threshold": threshold,
            },
        ),
    )
    assert report["objective_value"] == pytest.approx(4)
    assert report["status"] == status


def test_expected_failure_passes_only_for_biological_failure():
    infeasible = task(outputs={"b_e": [1, 1000]}, expected=False)
    report = run_task(network(), infeasible)
    assert report["status"] == "passed"
    assert report["actual_outcome"] == "failure"
    assert report["solver_status"] == "infeasible"


def test_metabolite_as_both_input_and_output():
    # Zero lower bounds on both sides: the metabolite may flow either way.
    either = task(inputs={"b_c": [0, 10]}, outputs={"b_c": [0, 5]})
    assert either.exchange_bounds()["TASK_IN_b_c"][2] == (0, 10)
    assert either.exchange_bounds()["TASK_OUT_b_c"][2] == (0, 5)
    assert run_task(network(), either)["status"] == "passed"
    # An output lower bound is a net production requirement, as in RAVEN: the
    # source is closed, so it cannot be met by cycling through source and sink.
    produce = task(inputs={"b_c": [0, 10]}, outputs={"b_c": [3, 1000]})
    assert produce.exchange_bounds()["TASK_IN_b_c"][2] == (0, 0)
    assert run_task(network(), produce)["status"] == "failed"
    fed = task(inputs={"a_c": [0, 10], "b_c": [0, 10]}, outputs={"b_c": [3, 1000]})
    assert run_task(network(), fed)["status"] == "passed"
    # An input lower bound is likewise a net consumption requirement.
    consume = task(inputs={"a_c": [2, 10]}, outputs={"a_c": [0, 1000]})
    assert consume.exchange_bounds()["TASK_OUT_a_c"][2] == (0, 0)
    assert run_task(network(), consume)["status"] == "failed"
    drained = task(
        inputs={"a_c": [2, 10]}, outputs={"a_c": [0, 1000], "b_c": [0, 1000]}
    )
    assert run_task(network(), drained)["status"] == "passed"


@pytest.mark.parametrize("expected", [True, False])
def test_nonzero_input_and_output_lower_bounds_are_invalid(expected):
    with pytest.raises(ValueError, match="both input"):
        task(
            inputs={"b_c": [1, 10]},
            outputs={"b_c": [1, 10]},
            expected=expected,
        )


def test_unknown_ids_are_invalid_even_when_failure_is_expected():
    report = run_task(network(), task(bounds={"missing": [0, 1]}, expected=False))
    assert report["status"] == "invalid"
    assert report["passed"] is False
    assert "unknown reaction 'missing'" in report["diagnostics"]["problems"]
    unknown_input = task(inputs={"nope_c": [0, 1]}, expected=False)
    report = run_task(network(), unknown_input)
    assert report["status"] == "invalid"
    assert "unknown input metabolite 'nope_c'" in report["diagnostics"]["problems"]
    temporary = task(
        temporary_reactions=[{"id": "tmp", "stoichiometry": {"nope_c": -1}, **OPEN}],
        expected=False,
    )
    assert run_task(network(), temporary)["status"] == "invalid"
    clash = task(
        temporary_reactions=[{"id": "R1", "stoichiometry": {"a_c": -1}, **OPEN}]
    )
    assert run_task(network(), clash)["status"] == "invalid"


def test_generated_reaction_names_must_not_clash():
    model = network()
    existing = cobra.Reaction("TASK_IN_a_e")
    existing.add_metabolites({model.metabolites.a_e: 1})
    model.add_reactions([existing])
    report = run_task(model, task(inputs={"a_e": [0, 10]}))
    assert report["status"] == "invalid"
    assert (
        "temporary reaction 'TASK_IN_a_e' already exists in the model"
        in report["diagnostics"]["problems"]
    )
    with pytest.raises(ValueError, match="clash with input/output"):
        task(
            outputs={"b_c": [0, 1]},
            temporary_reactions=[
                {"id": "TASK_OUT_b_c", "stoichiometry": {"b_c": -1}, **OPEN}
            ],
        )


@pytest.mark.parametrize(
    "payload",
    [
        {"bounds": {"R1": [5, 1]}},
        {"bounds": {"R1": [0, float("inf")]}},
        {"bounds": {"R1": [0]}},
        {"bounds": {"R1": ["0", 1]}},
        {"bounds": {"R1": [False, 1]}},
        {"inputs": {"a_e": [2, 1]}},
        {"outputs": {"b_e": [0, float("nan")]}},
        {"inputs": ["a_e"]},
        {"objective": "EX_b"},
        {"objective": {"reaction": "EX_b", "direction": "up", "threshold": 1}},
        {"objective": {"reaction": "EX_b", "direction": "max"}},
        {"expected": "no"},
        {"medium": "open"},
        {"uptake": {"EX_a": [-10, 0]}},
        {"secretion": {"EX_b": [0, 10]}},
        {"description": 3},
        {"temporary_reactions": [{"id": "tmp", "stoichiometry": {}, **OPEN}]},
        {"temporary_reactions": [{"id": "tmp", "stoichiometry": {"b_c": -1}}]},
        {
            "temporary_reactions": [
                {"id": "tmp", "stoichiometry": {"b_c": -1}, "lower_bound": 0}
            ]
        },
        {"metadata": {"source_rows": [{"file": "t.tsv", "row": 0, "columns": []}]}},
    ],
)
def test_malformed_definitions_are_rejected(payload):
    with pytest.raises(ValueError):
        task(**payload)


def test_duplicate_task_ids_and_json_keys_are_rejected(tmp_path):
    with pytest.raises(ValueError, match="duplicate task IDs"):
        TaskSuite("suite", "1", (MetabolicTask("a"), MetabolicTask("a")))
    path = tmp_path / "suite.json"
    path.write_text(
        '{"id": "s", "tasks": [{"id": "a", "inputs": {"a_e": [0, 1], "a_e": [0, 2]}}]}',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="duplicate JSON key"):
        load_task_suite(path)


def test_overlapping_constraints_intersect():
    overlapping = task(
        inputs={"a_e": [0, 10]},
        outputs={"b_e": [0, 1000]},
        bounds={"TASK_IN_a_e": [-5, 5]},
        objective={"reaction": "TASK_OUT_b_e", "direction": "max", "threshold": 5},
    )
    assert overlapping.reaction_bounds()["TASK_IN_a_e"] == (0, 5)
    report = run_task(network(), overlapping)
    assert report["objective_value"] == pytest.approx(5)
    assert report["status"] == "passed"


@pytest.mark.parametrize("expected", [True, False])
def test_contradictory_constraints_are_invalid_definitions(expected):
    with pytest.raises(ValueError, match="contradictory bounds for 'TASK_IN_a_e'"):
        task(
            inputs={"a_e": [5, 10]},
            bounds={"TASK_IN_a_e": [0, 2]},
            expected=expected,
        )
    with pytest.raises(ValueError, match="contradictory bounds for 'tmp'"):
        task(
            temporary_reactions=[
                {"id": "tmp", "stoichiometry": {"b_c": -1}, **OPEN, "lower_bound": 2}
            ],
            bounds={"tmp": [0, 1]},
            expected=expected,
        )


def test_temporary_reaction_stoichiometry_is_respected():
    demand = {
        "id": "demand_b",
        "stoichiometry": {"b_c": -2},
        **OPEN,
    }
    report = run_task(
        network(),
        task(
            inputs={"a_e": [0, 10]},
            temporary_reactions=[demand],
            objective={"reaction": "demand_b", "direction": "max", "threshold": 5},
        ),
    )
    assert report["objective_value"] == pytest.approx(5)
    assert report["status"] == "passed"


def test_input_model_and_shared_copy_are_restored_between_tasks():
    model = network("EX_b", "min")
    before = snapshot(model)
    tasks = [
        MetabolicTask(
            "open",
            inputs={"a_e": (0, 10)},
            temporary_reactions=(
                {"id": "sink_b", "stoichiometry": {"b_c": -1}, **OPEN},
            ),
            objective={"reaction": "sink_b", "direction": "max", "threshold": 10},
        ),
        MetabolicTask("closed", outputs={"b_e": (1, 1000)}, expected=False),
        MetabolicTask("closed-again", outputs={"b_e": (1, 1000)}, expected=False),
    ]
    report = run_tasks(model, tasks)
    assert [item["status"] for item in report["tasks"]] == ["passed"] * 3
    assert report["passed"] is True
    assert snapshot(model) == before


def test_solver_errors_never_count_as_expected_failures():
    unbounded = task(
        medium="model",
        objective={"reaction": "free", "direction": "max", "threshold": 1},
        expected=False,
    )
    report = run_task(network(), unbounded)
    assert report["status"] == "error"
    assert report["solver_status"] == "unbounded"
    assert report["actual_outcome"] is None
    broken = task(solver="no-such-solver", expected=False)
    report = run_task(network(), broken)
    assert report["status"] == "error"
    assert report["passed"] is False
    suite = run_tasks(network(), [broken])
    assert suite["passed"] is False
    assert suite["counts"]["error"] == 1


def test_import_problems_are_invalid_and_cannot_be_saved(tmp_path):
    problem = {"message": "glucose[e]: no model metabolite matches", "row": 4}
    unresolved = MetabolicTask("unresolved", expected=False, problems=(problem,))
    report = run_task(network(), unresolved)
    assert report["status"] == "invalid"
    assert report["diagnostics"]["import_problems"] == [problem]
    with pytest.raises(ValueError, match="unresolved import problems: unresolved"):
        save_task_suite(TaskSuite("s", "1", (unresolved,)), tmp_path / "s.json")


def test_metadata_round_trips_through_json(tmp_path):
    metadata = {
        "description": "Aerobic rephosphorylation of ATP from glucose",
        "source_rows": [
            {
                "file": "metabolicTasks_Essential.txt",
                "row": 4,
                "columns": [
                    ["ID", "ER"],
                    ["DESCRIPTION", "Aerobic rephosphorylation"],
                    ["IN", "O2[e];glucose[e]"],
                    ["IN LB", None],
                    ["COMMENTS", "first"],
                    ["COMMENTS", "repeated column"],
                ],
            },
            {
                "file": "metabolicTasks_Essential.txt",
                "row": 5,
                "columns": [["ID", None], ["EQU", "ATP[c] => ADP[c]"], ["EQU LB", "1"]],
            },
        ],
    }
    suite = TaskSuite(
        "suite",
        "1",
        (
            MetabolicTask(
                "ER-1",
                description="Aerobic rephosphorylation",
                inputs={"a_e": (0, 10)},
                outputs={"b_e": (0, 1000)},
                temporary_reactions=(
                    {"id": "tmp", "stoichiometry": {"a_c": -1}, **OPEN},
                ),
                bounds={"R1": (0, 5)},
                objective={"reaction": "tmp", "direction": "max", "threshold": 1},
                metadata=metadata,
            ),
        ),
        metadata={"source": "legacy"},
    )
    path = save_task_suite(suite, tmp_path / "suite.json")
    loaded = load_task_suite(path)
    assert loaded == suite
    assert loaded.tasks[0].metadata == metadata
    assert json.loads(path.read_text(encoding="utf-8")) == suite.to_dict()
