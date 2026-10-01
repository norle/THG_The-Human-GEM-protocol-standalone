"""RAVEN task table import (GLPK)."""

from __future__ import annotations

import json
import re
from pathlib import Path

import cobra
import pytest

from thg_protocol.raven_tasks import (
    TaskMapping,
    convert_raven_tasks,
    import_raven_tasks,
    load_task_input,
    read_raven_rows,
)
from thg_protocol.tasks import load_task_suite, run_task_suite

FIXTURES = Path(__file__).parents[1] / "fixtures" / "memote" / "data"
ESSENTIAL = FIXTURES / "metabolicTasks_Essential.txt"
HEADER = [
    "",
    "ID",
    "DESCRIPTION",
    "SHOULD FAIL",
    "IN",
    "IN LB",
    "IN UB",
    "OUT",
    "OUT LB",
    "OUT UB",
    "EQU",
    "EQU LB",
    "EQU UB",
    "CHANGED RXN",
    "CHANGED LB",
    "CHANGED UB",
    "PRINT FLUX",
    "COMMENTS",
]


def table(tmp_path, *rows: dict[str, str], name: str = "tasks.txt") -> Path:
    lines = ["#\tcomment row", "\t".join(HEADER)]
    for row in rows:
        lines.append("\t".join(row.get(column, "") for column in HEADER))
    path = tmp_path / name
    path.write_text("\r\n".join(lines) + "\r\n", encoding="utf-8")
    return path


def model() -> cobra.Model:
    """glucose[e] -> glucose[c] -> pyruvate[c], with an exchange for glucose."""
    result = cobra.Model("raven")
    result.solver = "glpk"
    names = {
        "glc_e": ("glucose", "e"),
        "glc_c": ("glucose", "c"),
        "pyr_c": ("pyruvate", "c"),
        "pyr_e": ("pyruvate", "e"),
        "atp_c": ("ATP", "c"),
        "adp_c": ("ADP", "c"),
        "h2o_c": ("H2O", "c"),
        "dup1_c": ("twin", "c"),
        "dup2_c": ("twin", "c"),
    }
    metabolites = {
        key: cobra.Metabolite(key, name=name, compartment=comp)
        for key, (name, comp) in names.items()
    }
    result.add_metabolites(list(metabolites.values()))
    result.compartments = {"c": "cytosol", "e": "extracellular"}

    def reaction(reaction_id, stoichiometry, bounds=(0, 1000)):
        item = cobra.Reaction(reaction_id, lower_bound=bounds[0], upper_bound=bounds[1])
        item.add_metabolites(
            {metabolites[key]: value for key, value in stoichiometry.items()}
        )
        return item

    result.add_reactions(
        [
            reaction("EX_glc", {"glc_e": -1}, (-10, 1000)),
            reaction("GLCt", {"glc_e": -1, "glc_c": 1}),
            reaction("GLY", {"glc_c": -1, "pyr_c": 2, "adp_c": -2, "atp_c": 2}),
            reaction("PYRt", {"pyr_c": -1, "pyr_e": 1}),
        ]
    )
    return result


def only(result):
    assert len(result.suite.tasks) == 1
    return result.suite.tasks[0]


def test_rows_defaults_and_metadata(tmp_path):
    path = table(
        tmp_path,
        {
            "ID": "1",
            "DESCRIPTION": "glucose to pyruvate",
            "IN": "glucose[e]",
            "OUT": "pyruvate[e]",
            "OUT LB": "1",
            "PRINT FLUX": "1",
            "COMMENTS": "note",
        },
        {"IN": "ADP[c]"},
        {"OUT": "ATP[c]", "EQU": "ATP[c] => ADP[c]"},
    )
    result = import_raven_tasks(path, model())
    assert result.problems == ()
    task = only(result)
    assert task.id == "1"
    assert task.description == "glucose to pyruvate"
    assert task.expected is True
    assert task.inputs == {"glc_e": (0.0, 1000.0), "adp_c": (0.0, 1000.0)}
    assert task.outputs == {"pyr_e": (1.0, 1000.0), "atp_c": (0.0, 1000.0)}
    assert task.temporary_reactions[0] == {
        "id": "TEMPORARY_1",
        "name": "ATP[c] => ADP[c]",
        "lower_bound": 0.0,
        "upper_bound": 1000.0,
        "stoichiometry": {"atp_c": -1.0, "adp_c": 1.0},
        "gene_reaction_rule": "",
    }
    rows = task.metadata["source_rows"]
    assert [row["row"] for row in rows] == [3, 4, 5]
    assert rows[0]["file"] == "tasks.txt"
    assert ["PRINT FLUX", "1"] in rows[0]["columns"]
    assert ["IN LB", None] in rows[0]["columns"]
    assert result.suite.metadata["source"]["format"] == "raven"
    report = run_task_suite(model(), result.suite)
    assert report["tasks"][0]["status"] == "passed"


def test_equation_parsing(tmp_path):
    path = table(
        tmp_path,
        {
            "ID": "eq",
            "EQU": "2 ADP[c] + 0.5 H2O[c] <=> 2 ATP[c] + H2O[c]",
        },
        {"EQU": "glucose[c] => 2 pyruvate[c]", "EQU LB": "1", "EQU UB": "4"},
    )
    first, second = only(import_raven_tasks(path, model())).temporary_reactions
    assert first["stoichiometry"] == {"adp_c": -2.0, "h2o_c": 0.5, "atp_c": 2.0}
    assert (first["lower_bound"], first["upper_bound"]) == (-1000.0, 1000.0)
    assert second["id"] == "TEMPORARY_2"
    assert (second["lower_bound"], second["upper_bound"]) == (1.0, 4.0)


def test_equation_cannot_add_metabolites(tmp_path):
    path = table(tmp_path, {"ID": "new", "EQU": "glucose[c] => lactate[c]"})
    result = import_raven_tasks(path, model())
    problem = result.problems[0]
    assert (problem["row"], problem["column"], problem["text"]) == (
        3,
        "EQU",
        "lactate[c]",
    )
    assert "RAVEN would add it" in problem["message"]
    assert run_task_suite(model(), result.suite)["tasks"][0]["status"] == "invalid"


def test_unresolved_and_ambiguous_names_make_tasks_invalid(tmp_path):
    path = table(
        tmp_path,
        {"ID": "missing", "IN": "glucose[x]"},
        {"ID": "typo", "IN": "glucos[e]"},
        {"ID": "ambiguous", "IN": "twin[c]", "SHOULD FAIL": "1"},
        {"ID": "fine", "IN": "glucose[e]"},
    )
    result = import_raven_tasks(path, model())
    by_task = {item["task"]: item for item in result.problems}
    assert "compartment 'x'" in by_task["missing"]["message"]
    assert by_task["typo"]["candidates"] == ["glc_e (GLUCOSE[e])"]
    assert by_task["ambiguous"]["candidates"] == ["dup1_c", "dup2_c"]
    assert by_task["ambiguous"]["file"] == "tasks.txt"
    assert by_task["ambiguous"]["row"] == 5
    report = run_task_suite(model(), result.suite)
    statuses = {item["id"]: item["status"] for item in report["tasks"]}
    assert statuses == {
        "missing": "invalid",
        "typo": "invalid",
        "ambiguous": "invalid",
        "fine": "passed",
    }
    ambiguous = next(item for item in report["tasks"] if item["id"] == "ambiguous")
    assert ambiguous["diagnostics"]["import_problems"][0]["text"] == "twin[c]"
    # Conversion refuses to write while problems remain ...
    output = tmp_path / "suite.json"
    with pytest.raises(ValueError, match="3 unresolved problems"):
        convert_raven_tasks(path, model(), output)
    assert not output.exists()
    # ... unless only the resolved tasks are written, listing the omitted ones.
    convert_raven_tasks(path, model(), output, resolved_only=True)
    saved = load_task_suite(output)
    assert [task.id for task in saved.tasks] == ["fine"]
    omitted = saved.metadata["omitted_tasks"]
    assert [item["id"] for item in omitted] == ["missing", "typo", "ambiguous"]


def test_mapping_overrides(tmp_path):
    path = table(
        tmp_path,
        {"ID": "1", "IN": "Glc[ext];twin[c]", "CHANGED RXN": "glycolysis"},
        {"CHANGED RXN": "PYRt", "CHANGED LB": "0", "CHANGED UB": "0"},
        {"ID": "2", "IN": "glucose[ext]"},
    )
    path.write_text(
        path.read_text(encoding="utf-8").replace("glycolysis\t\t", "glycolysis\t0\t5"),
        encoding="utf-8",
    )
    mapping_path = tmp_path / "mapping.json"
    mapping_path.write_text(
        json.dumps(
            {
                "metabolites": {"glc[EXT]": "glc_e", "twin[c]": "dup2_c"},
                "compartments": {"ext": "e"},
                "reactions": {"glycolysis": "GLY"},
            }
        ),
        encoding="utf-8",
    )
    result = import_raven_tasks(path, model(), mapping=mapping_path)
    assert result.problems == ()
    first, second = result.suite.tasks
    assert first.inputs == {"glc_e": (0.0, 1000.0), "dup2_c": (0.0, 1000.0)}
    assert first.bounds == {"GLY": (0.0, 5.0), "PYRt": (0.0, 0.0)}
    assert second.inputs == {"glc_e": (0.0, 1000.0)}
    assert result.suite.metadata["mapping"]["reactions"] == {"glycolysis": "GLY"}
    bad = TaskMapping(metabolites={"glucose[ext]": "nope"})
    problem = import_raven_tasks(path, model(), mapping=bad).problems
    assert any("nope" in item["message"] for item in problem)
    with pytest.raises(ValueError, match="conflicting"):
        TaskMapping(compartments={"e": "e", "E": "c"})


def test_changed_reaction_bounds_have_no_default(tmp_path):
    path = table(tmp_path, {"ID": "1", "CHANGED RXN": "GLY", "CHANGED UB": "5"})
    problem = import_raven_tasks(path, model()).problems[0]
    assert (problem["column"], problem["message"].split(": ")[-1]) == (
        "CHANGED LB",
        "a bound is required",
    )


def test_allmetsin_expands_with_explicit_precedence(tmp_path):
    path = table(
        tmp_path,
        {
            "ID": "all",
            "IN": "ALLMETSIN[e];glucose[e];ADP[c]",
            "IN LB": "1",
            "IN UB": "5",
            "OUT": "ALLMETS",
            "OUT LB": "3",
            "OUT UB": "100",
        },
        {"OUT": "pyruvate[e]", "OUT LB": "2", "OUT UB": "20"},
    )
    task = only(import_raven_tasks(path, model()))
    # Wildcards use only the upper bound; explicit constraints win on their side.
    assert task.inputs == {
        "glc_e": (1.0, 5.0),
        "adp_c": (1.0, 5.0),
        "pyr_e": (0.0, 5.0),
    }
    assert task.outputs["pyr_e"] == (2.0, 20.0)
    assert task.outputs["atp_c"] == (0.0, 100.0)
    assert len(task.outputs) == len(model().metabolites)
    # glucose[e] keeps IN LB as a requirement although ALLMETS also lists it.
    assert task.exchange_bounds()["TASK_OUT_glc_e"][2] == (0.0, 0.0)
    assert any("IN LB 1.0 on 'glc_e'" in note for note in task.metadata["import_notes"])
    # pyruvate[e] has OUT LB 2, so the ALLMETSIN input is closed, as in RAVEN.
    assert task.exchange_bounds()["TASK_IN_pyr_e"][2] == (0.0, 0.0)
    assert run_task_suite(model(), import_raven_tasks(path, model()).suite)["passed"]


def test_should_fail_values(tmp_path):
    path = table(
        tmp_path,
        {"ID": "a", "SHOULD FAIL": "TRUE"},
        {"ID": "b", "SHOULD FAIL": "1"},
        {"ID": "c", "SHOULD FAIL": "0"},
        {"ID": "d", "SHOULD FAIL": "false"},
        {"ID": "e"},
        {"ID": "f", "SHOULD FAIL": "yes"},
    )
    result = import_raven_tasks(path, model())
    expected = {task.id: task.expected for task in result.suite.tasks}
    assert expected == {
        "a": False,
        "b": False,
        "c": True,
        "d": True,
        "e": True,
        "f": True,
    }
    notes = {
        task.id: task.metadata.get("import_notes", []) for task in result.suite.tasks
    }
    assert "RAVEN treats any non-empty cell as true" in notes["c"][0]
    assert [item["task"] for item in result.problems] == ["f"]


def test_repeated_constraints_intersect_or_conflict(tmp_path):
    path = table(
        tmp_path,
        {"ID": "overlap", "IN": "glucose[e]", "IN LB": "0", "IN UB": "7"},
        {"IN": "glucose[e]", "IN LB": "1", "IN UB": "10"},
        {"ID": "conflict", "IN": "glucose[e]", "IN LB": "0", "IN UB": "1"},
        {"IN": "glucose[e]", "IN LB": "2", "IN UB": "10"},
    )
    result = import_raven_tasks(path, model())
    overlap, conflict = result.suite.tasks
    assert overlap.inputs == {"glc_e": (1.0, 7.0)}
    assert "intersected to [1.0, 7.0]" in overlap.metadata["import_notes"][0]
    assert conflict.problems
    assert "contradictory constraints on 'glc_e'" in conflict.problems[0]["message"]


def test_nonzero_input_and_output_lower_bounds_conflict(tmp_path):
    path = table(
        tmp_path,
        {
            "ID": "1",
            "IN": "glucose[e]",
            "IN LB": "1",
            "OUT": "glucose[e]",
            "OUT LB": "1",
        },
    )
    problem = import_raven_tasks(path, model()).problems[0]
    assert "nonzero IN LB and OUT LB" in problem["message"]


def test_duplicate_raven_ids_are_renamed(tmp_path):
    path = table(tmp_path, {"ID": "ER", "IN": "glucose[e]"}, {"ID": "ER"})
    ids = [task.id for task in import_raven_tasks(path, model()).suite.tasks]
    assert ids == ["ER-row3", "ER-row4"]


def test_orphan_constraint_rows_are_rejected(tmp_path):
    path = table(tmp_path, {"IN": "glucose[e]"}, {"ID": "1"})
    with pytest.raises(ValueError, match="row 3 ID: constraint row before"):
        import_raven_tasks(path, model())


def test_excel_and_mapping_for_json_are_rejected(tmp_path):
    with pytest.raises(ValueError, match="Excel"):
        import_raven_tasks(tmp_path / "tasks.xlsx", model())
    with pytest.raises(ValueError, match="only to RAVEN"):
        load_task_input(tmp_path / "suite.json", model(), mapping=TaskMapping())


def essential_model() -> cobra.Model:
    """Every metabolite named in the Essential fixture, with no reactions."""
    names = set()
    for row in read_raven_rows(ESSENTIAL):
        for column in ("IN", "OUT"):
            names.update((row.get(column) or "").split(";"))
        for side in re.split(" <=> | => ", row.get("EQU") or ""):
            names.update(
                re.sub(r"^[\d.]+ ", "", term.strip()) for term in side.split(" + ")
            )
    result = cobra.Model("essential")
    result.solver = "glpk"
    for index, text in enumerate(sorted(names)):
        match = re.fullmatch(r"(.+)\[([a-z])\]", text.strip())
        if match and not text.startswith("ALLMETSIN"):
            result.add_metabolites(
                [
                    cobra.Metabolite(
                        f"m{index}_{match[2]}", name=match[1], compartment=match[2]
                    )
                ]
            )
    return result


def test_essential_fixture_direct_and_converted_reports_match(tmp_path):
    source = essential_model()
    result = import_raven_tasks(ESSENTIAL, source)
    assert result.problems == ()
    tasks = result.suite.tasks
    assert len(tasks) == 57
    assert tasks[0].id == "ER-row4"
    assert tasks[0].description == "Aerobic rephosphorylation of ATP from glucose"
    assert tasks[0].metadata["raven_id"] == "ER"
    # Inputs, outputs, and the EQU default bounds are explicit in the JSON.
    assert all(pair == (0.0, 1000.0) for pair in tasks[0].inputs.values())
    assert tasks[0].temporary_reactions[0]["lower_bound"] == 1.0
    converted = tmp_path / "essential.json"
    convert_raven_tasks(ESSENTIAL, source, converted)
    loaded = load_task_suite(converted)
    assert loaded == result.suite
    direct = run_task_suite(source, load_task_input(ESSENTIAL, source))
    assert run_task_suite(source, loaded) == direct
    assert direct["counts"]["invalid"] == direct["counts"]["error"] == 0


def test_workflows_run_raven_tables_with_a_mapping(tmp_path):
    from thg_protocol.raven_tasks import task_input_version
    from thg_protocol.workflow._scientific import _task_results
    from thg_protocol.workflow.gapfill import _task_report

    path = table(tmp_path, {"ID": "1", "IN": "glc[e]", "OUT": "glucose[c]"})
    mapping = tmp_path / "mapping.json"
    mapping.write_text('{"metabolites": {"glc[e]": "glc_e"}}', encoding="utf-8")
    section = {"task_suite": str(path), "task_mapping": str(mapping)}
    for runner in (_task_results, _task_report):
        report = runner(model(), section)
        assert report["passed"] is True
        assert report["suite_version"] == task_input_version(path)
    unmapped = _task_report(model(), {"task_suite": str(path)})
    assert unmapped["counts"]["invalid"] == 1
