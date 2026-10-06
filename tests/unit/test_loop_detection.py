import json
from html import unescape

import cobra
import pytest
from cobra.io import load_json_model, save_json_model

from thg_protocol.analysis.compaction import (
    combine_identical_reactions,
    detect_infeasible_loops,
    remove_infeasible_loops,
)
from thg_protocol.analysis.model_signature import model_signature
from thg_protocol.validation import validate_model
from thg_protocol.validation_report import render_validation_html
from thg_protocol.workflow.runner import get_status, resume, start


def loop_model(*, parallel=False, reverse=False):
    model = cobra.Model("loops")
    a, b, c, x, y = [
        cobra.Metabolite(name, compartment="c", formula="H2O", charge=0)
        for name in ("a", "b", "c", "x", "y")
    ]
    equations = [
        ("source", {a: 1}),
        ("use", {a: -1, b: 1}),
        ("sink", {b: -1}),
        ("first(@)#" + "long" * 30, {a: -2, c: 2}),
        ("back", {c: -1, a: 1}),
        ("blocked", {x: -1, y: 1}),
    ]
    if parallel:
        equations.append(("parallel", {a: -3, c: 3}))
    for identifier, stoichiometry in equations:
        reaction = cobra.Reaction(identifier, upper_bound=10)
        reaction.add_metabolites(stoichiometry)
        reaction.gene_reaction_rule = "G1" if identifier == "back" else ""
        model.add_reactions([reaction])
    if reverse:
        model.reactions.back *= -1
    model.objective = "sink"
    return model


@pytest.mark.parametrize(
    "parallel,reverse", [(False, False), (True, False), (False, True), (True, True)]
)
def test_detects_scaled_linear_parallel_and_reversed_loops_without_mutation(
    parallel, reverse
):
    model = loop_model(parallel=parallel, reverse=reverse)
    before = model_signature(model)
    report = detect_infeasible_loops(model)
    expected = {rxn.id for rxn in model.reactions if rxn.id.startswith("first")}
    expected.add("back")
    if parallel:
        expected.add("parallel")
    assert set(report["reactions"]) == expected
    assert report["loops"] == [sorted(expected)]
    assert report["blocked_reactions_excluded"] == ["blocked"]
    assert model_signature(model) == before


def test_validation_detects_by_default_and_disabled_detection_is_explicit():
    model = loop_model()
    before = model_signature(model)
    report = validate_model(model, "final-standard", propose_fixes=True)
    check = next(item for item in report["checks"] if item["id"] == "obligatory-loops")
    assert check["passed"] is False and check["release_blocking"] is False
    assert report["passed"] is True
    assert "Obligatory infeasible loops" in render_validation_html(report)
    assert model_signature(model) == before
    report = validate_model(model, run_loop_detection=False)
    check = next(item for item in report["checks"] if item["id"] == "obligatory-loops")
    assert check["status"] == "not-evaluated" and check["passed"] is None


def test_loop_detection_errors_do_not_claim_no_loops(monkeypatch):
    def fail(_):
        raise RuntimeError("solver unavailable")

    monkeypatch.setattr("thg_protocol.analysis.consistency.blocked_reactions", fail)
    report = validate_model(loop_model())
    check = next(item for item in report["checks"] if item["id"] == "obligatory-loops")
    assert check["status"] == "infrastructure-error"
    assert check["passed"] is None


def test_removal_preserves_other_reactions_and_flux_and_records_original_ids():
    model = loop_model(parallel=True)
    before = model_signature(model)
    result, report, ledger = remove_infeasible_loops(model, stage="test")
    assert {rxn.id for rxn in result.reactions} == {"source", "use", "sink", "blocked"}
    assert {row["object_id"] for row in ledger} == set(report["reactions"])
    assert all(row["status"] == "applied" and row["before"] for row in ledger)
    assert result.slim_optimize() == model.slim_optimize()
    assert detect_infeasible_loops(result)["passed"] is True
    assert model_signature(model) == before


def test_valid_pathways_blocked_cycles_and_objective_reactions_are_protected():
    model = loop_model()
    model.reactions.back.bounds = (0, 0)
    assert detect_infeasible_loops(model)["passed"] is True
    model.reactions.back.bounds = (0, 10)
    model.objective = "back"
    assert detect_infeasible_loops(model)["passed"] is True


@pytest.mark.parametrize("source", ["original", "A & B", "A < B", "A &lt; B"])
def test_sbml_preserves_nested_provenance_without_mutating_model(tmp_path, source):
    from thg_protocol.io.models import save_sbml

    model = loop_model()
    model.metabolites.a.annotation["thg.provenance"] = {"source_model": source}
    before = model_signature(model)
    path = save_sbml(model, tmp_path / "model.xml")
    loaded = cobra.io.read_sbml_model(path)
    note = loaded.metabolites.a.notes["thg.annotation.thg.provenance"]
    assert json.loads(unescape(note)) == {"source_model": source}
    assert model_signature(model) == before


def test_parallel_merging_preserves_scaled_reversed_capacity():
    model = loop_model()
    forward = model.reactions.use
    reverse = forward.copy()
    reverse.id = "reverse"
    reverse *= -2
    reverse.bounds = (0, 7)
    model.add_reactions([reverse])
    compacted, _ = combine_identical_reactions(model)
    assert compacted.reactions.use.bounds == (-14, 10)


@pytest.mark.parametrize("all_reversible", [False, True])
@pytest.mark.parametrize(
    "reversed_ids", [(), ("back",), ("parallel",), ("back", "parallel")]
)
def test_reversible_parallel_loops_are_independent_of_orientation(
    all_reversible, reversed_ids
):
    model = loop_model(parallel=True)
    members = {rxn.id for rxn in model.reactions if rxn.id.startswith("first")}
    members.update(("back", "parallel"))
    model.reactions.back *= -1
    for identifier in members:
        if all_reversible or identifier == "back":
            model.reactions.get_by_id(identifier).bounds = (-10, 10)
    for identifier in reversed_ids:
        reaction = model.reactions.get_by_id(identifier)
        reaction *= -1
    before = model_signature(model)
    result, report, ledger = remove_infeasible_loops(model)
    assert report["loops"] == [sorted(members)]
    assert {row["object_id"] for row in ledger} == members
    assert {rxn.id for rxn in result.reactions} == {"source", "use", "sink", "blocked"}
    assert result.slim_optimize() == model.slim_optimize()
    assert model_signature(model) == before


@pytest.mark.parametrize("length", [3, 6])
def test_multistep_scaled_cycle_collapses_to_original_members(length):
    model = loop_model()
    model.remove_reactions(
        [
            rxn
            for rxn in model.reactions
            if rxn.id.startswith("first") or rxn.id == "back"
        ]
    )
    metabolites = [model.metabolites.a] + [
        cobra.Metabolite(f"intermediate{i}", compartment="c") for i in range(length - 1)
    ]
    for index in range(length):
        reaction = cobra.Reaction(f"step{index}")
        scale = index + 2
        reaction.add_metabolites(
            {metabolites[index]: -scale, metabolites[(index + 1) % length]: scale}
        )
        model.add_reactions([reaction])
    report = detect_infeasible_loops(model)
    assert report["loops"] == [[f"step{i}" for i in range(length)]]


@pytest.mark.parametrize("workflow", ["gapfill", "final-thg"])
@pytest.mark.parametrize("remove", [False, True])
def test_pipeline_removal_requires_explicit_option_and_revalidates(
    tmp_path, workflow, remove
):
    model = loop_model(parallel=True)
    source = tmp_path / "model.json"
    save_json_model(model, source)
    source_bytes = source.read_bytes()
    if workflow == "gapfill":
        section = "gapfill"
        options = {
            "input_model": str(source),
            "external_input": True,
            "method": "greedy",
            "max_additions": 1,
            "allowed_connections": [],
            "candidate_types": ["A", "B", "C"],
            "validation_profile": "final-standard",
        }
        mutation, validation, export = (
            "apply-gapfill",
            "validate-gapfill",
            "export-gapfilled-reference",
        )
    else:
        section = "final_thg"
        options = {
            "beta2_model": str(source),
            "database_model": str(source),
            "validation_profile": "final-standard",
        }
        mutation, validation, export = (
            "final-thg-merge",
            "validate-final-thg",
            "export-final-thg",
        )
    if remove:
        options["remove_infeasible_loops"] = True
    from thg_protocol.tasks import MetabolicTask, TaskObjective, TaskSuite

    tasks = tmp_path / "tasks.json"
    tasks.write_text(
        json.dumps(
            TaskSuite(
                "productive",
                "1",
                (
                    MetabolicTask(
                        "productive",
                        medium="model",
                        objective=TaskObjective("sink", "max", threshold=1),
                    ),
                ),
            ).to_dict()
        )
    )
    options["task_suite"] = str(tasks)
    config = tmp_path / "config.json"
    config.write_text(
        json.dumps(
            {
                "workflow": workflow,
                "run": {"name": "loops", "output_dir": str(tmp_path / "run")},
                section: options,
            }
        )
    )
    run = start(config)
    status = get_status(run)

    def artifact(stage, role):
        return run / next(
            item["path"]
            for item in status["steps"][stage]["outputs"]
            if item["role"] == role
        )

    result = load_json_model(artifact(export, "model"))
    assert ("back" not in result.reactions) is remove
    report = json.loads(artifact(validation, "validation").read_text())
    check = next(
        item
        for item in report["validation"]["checks"]
        if item["id"] == "obligatory-loops"
    )
    assert check["passed"] is remove
    assert report["tasks"]["passed"] is True
    role = "ledger" if workflow == "gapfill" else "loop-removal-ledger"
    ledger = [
        json.loads(line) for line in artifact(mutation, role).read_text().splitlines()
    ]
    removed = {
        item["object_id"] for item in ledger if item["operation"] == "remove-reaction"
    }
    assert ("back" in removed) is remove
    assert source.read_bytes() == source_bytes
    resume(run)
    assert get_status(run)["overall_status"] == "completed"


@pytest.mark.parametrize("key", ["remove_infeasible_loops", "run_loop_detection"])
def test_pipeline_loop_options_reject_non_boolean_values(tmp_path, key):
    from thg_protocol.workflow.config import ConfigError, load_workflow_config

    path = tmp_path / "config.json"
    path.write_text(
        json.dumps(
            {
                "workflow": "gapfill",
                "run": {"name": "invalid", "output_dir": str(tmp_path / "run")},
                "gapfill": {key: "false"},
            }
        )
    )
    with pytest.raises(ConfigError, match="must be a boolean"):
        load_workflow_config(path)


def test_gapfill_gate_accepts_only_declared_loop_deletions():
    from thg_protocol.analysis.model_signature import diff_model_signatures
    from thg_protocol.workflow.gapfill import _model_diff_is_clean

    model = loop_model()
    model.add_groups([cobra.core.Group("pathway", members=list(model.reactions))])
    original = model_signature(model)
    cleaned, report, _ = remove_infeasible_loops(model)
    diff = diff_model_signatures(original, model_signature(cleaned))
    assert not _model_diff_is_clean(diff)
    assert _model_diff_is_clean(diff, set(report["reactions"]))
    cleaned.reactions.use.bounds = (0, 1)
    diff = diff_model_signatures(original, model_signature(cleaned))
    assert not _model_diff_is_clean(diff, set(report["reactions"]))
