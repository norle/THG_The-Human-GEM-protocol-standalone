import json

import cobra
from cobra.io import save_json_model

from thg_protocol.database_workflow import harvest_snapshot, normalize_records
from thg_protocol.merge import (
    MergePlan,
    MergePolicy,
    apply_merge_plan,
    bounded_repair,
    generate_merge_plan,
    validate_merged_model,
)
from thg_protocol.workflow.config import RunSettings, WorkflowConfig
from thg_protocol.workflow.phase4_stages import FinalTHGStage
from thg_protocol.workflow.stages import StageContext


class Adapter:
    release = "fixture-1"

    def fetch(self, key):
        return {"key": key, "value": 1}


def test_harvest_snapshot_is_cached_and_records_manifest(tmp_path):
    responses, errors = harvest_snapshot(["b", "a"], Adapter(), tmp_path / "cache")
    assert not errors
    assert sorted(responses) == ["a", "b"]
    second, second_errors = harvest_snapshot(["a"], Adapter(), tmp_path / "cache")
    assert second == {"a": {"key": "a", "value": 1}}
    assert not second_errors
    manifest = json.loads((tmp_path / "cache" / "cache-manifest.json").read_text())
    assert manifest["adapter_release"] == "fixture-1"


def test_harvest_snapshot_refetches_when_adapter_release_changes(tmp_path):
    calls = []

    class AdapterV1:
        release = "fixture-1"

        def fetch(self, key):
            calls.append((self.release, key))
            return {"release": self.release}

    class AdapterV2:
        release = "fixture-2"

        def fetch(self, key):
            calls.append((self.release, key))
            return {"release": self.release}

    cache = tmp_path / "cache"
    harvest_snapshot(["a"], AdapterV1(), cache)
    responses, errors = harvest_snapshot(["a"], AdapterV2(), cache)

    assert not errors
    assert responses == {"a": {"release": "fixture-2"}}
    assert calls == [("fixture-1", "a"), ("fixture-2", "a")]


def test_normalized_records_are_versioned_and_deterministic():
    records = normalize_records(
        {
            "schema_version": 1,
            "metabolites": [{"id": "a_c", "compartment": "c"}],
            "reactions": [],
        }
    )
    assert records.to_dict()["schema_version"] == 1
    assert normalize_records(records.to_dict()) == records


def test_merge_plan_maps_explicit_cross_ids_but_not_chemistry_only():
    left = cobra.Model("left")
    a = cobra.Metabolite("a_c", compartment="c")
    a.annotation["chebi"] = "CHEBI:1"
    left.add_metabolites([a])
    right = cobra.Model("right")
    b = cobra.Metabolite("b_c", compartment="c")
    b.annotation["chebi"] = "CHEBI:1"
    right.add_metabolites([b])
    plan = generate_merge_plan(left, right)
    assert plan.metabolite_map == {"b_c": "a_c"}
    assert plan.decisions[0].action == "map"
    assert MergePlan.from_dict(plan.to_dict()) == plan


def test_merge_policy_reports_conflicts_and_apply_adds_provenance():
    left = cobra.Model("left")
    a = cobra.Metabolite("a_c", compartment="c", formula="C", charge=0)
    a.annotation["chebi"] = "CHEBI:1"
    left.add_metabolites([a])
    r_left = cobra.Reaction("R", lower_bound=0, upper_bound=1)
    r_left.add_metabolites({a: -1})
    left.add_reactions([r_left])
    right = cobra.Model("right")
    b = cobra.Metabolite("b_c", compartment="c", formula="C2", charge=1)
    b.annotation["chebi"] = "CHEBI:1"
    right.add_metabolites([b])
    r_right = cobra.Reaction("R", lower_bound=-2, upper_bound=3)
    r_right.add_metabolites({b: -1})
    r_right.gene_reaction_rule = "G1"
    right.add_reactions([r_right])
    plan = generate_merge_plan(
        left,
        right,
        policy=MergePolicy(
            bounds="incoming", formula_charge="incoming", gpr="incoming"
        ),
    )
    categories = {decision.category for decision in plan.decisions}
    assert {
        "bounds-conflict",
        "formula-conflict",
        "charge-conflict",
        "gpr-conflict",
    } <= categories
    merged, _ = apply_merge_plan(left, right, plan)
    assert merged.reactions.R.annotation["thg.provenance"]["source_model"] == "right"
    assert merged.reactions.R.bounds == (-2, 3)
    assert merged.reactions.R.gene_reaction_rule == "G1"
    assert merged.metabolites.a_c.formula == "C2"
    assert merged.metabolites.a_c.charge == 1


def test_final_thg_fingerprint_includes_direct_input_content(tmp_path):
    beta2 = tmp_path / "beta2.json"
    database = tmp_path / "database.json"
    beta2.write_text("beta2-v1", encoding="utf-8")
    database.write_text("database-v1", encoding="utf-8")
    config = WorkflowConfig(
        workflow="final-thg",
        run=RunSettings("final", tmp_path / "run"),
        sections={
            "final_thg": {
                "beta2_model": str(beta2),
                "database_model": str(database),
            }
        },
    )
    stage = FinalTHGStage("final-thg-load")
    context = StageContext(config, tmp_path / "run", {"steps": {}})

    first = stage.fingerprint_data(context)
    beta2.write_text("beta2-v2", encoding="utf-8")
    second = stage.fingerprint_data(context)

    assert first["inputs"]["beta2_model"] != second["inputs"]["beta2_model"]


def test_final_thg_apply_reuses_persisted_merge_plan(tmp_path, monkeypatch):
    left = cobra.Model("left")
    a = cobra.Metabolite("a_c", formula="C", charge=0, compartment="c")
    b = cobra.Metabolite("b_c", formula="C", charge=0, compartment="c")
    left.add_metabolites([a, b])
    forward = cobra.Reaction("R_FORWARD")
    forward.add_metabolites({a: -1, b: 1})
    reverse = cobra.Reaction("R_REVERSE")
    reverse.add_metabolites({b: -1, a: 1})
    left.add_reactions([forward, reverse])
    right = cobra.Model("right")

    run_dir = tmp_path / "run"
    load_dir = run_dir / "artifacts" / "final-thg-load" / "attempt-0001"
    plan_dir = run_dir / "artifacts" / "final-thg-plan" / "attempt-0001"
    load_dir.mkdir(parents=True)
    plan_dir.mkdir(parents=True)
    left_path = load_dir / "beta2.json"
    right_path = load_dir / "database.json"
    save_json_model(left, left_path)
    save_json_model(right, right_path)
    plan = generate_merge_plan(left, right)
    plan_path = plan_dir / "merge-plan.json"
    plan_path.write_text(json.dumps(plan.to_dict()), encoding="utf-8")

    config = WorkflowConfig(
        workflow="final-thg",
        run=RunSettings("final", run_dir),
        sections={"final_thg": {"validation_profile": "structural-fast"}},
    )
    context = StageContext(
        config,
        run_dir,
        {
            "steps": {
                "final-thg-load": {
                    "outputs": [
                        {"role": "beta2", "path": str(left_path.relative_to(run_dir))},
                        {
                            "role": "database",
                            "path": str(right_path.relative_to(run_dir)),
                        },
                    ]
                },
                "final-thg-plan": {
                    "outputs": [
                        {
                            "role": "merge-plan",
                            "path": str(plan_path.relative_to(run_dir)),
                        }
                    ]
                },
            }
        },
    )
    work_dir = tmp_path / "work"
    work_dir.mkdir()

    def unexpected_plan(*args, **kwargs):
        raise AssertionError("merge plan should have been reused")

    monkeypatch.setattr("thg_protocol.merge.generate_merge_plan", unexpected_plan)
    result = FinalTHGStage("final-thg-apply", ("final-thg-plan",)).run(
        context, work_dir
    )

    assert (
        json.loads((work_dir / "merge-plan.json").read_text())["plan"]
        == plan.to_dict()
    )
    assert {role for role, _ in result.outputs} == {"model", "merge-plan"}


def test_bounded_repair_has_explicit_stop_conditions_and_validation():
    model = cobra.Model("repair")
    repaired, report = bounded_repair(
        model, max_iterations=2, repair=lambda item: (item, [])
    )
    assert repaired is not model
    assert report.stop_reason == "no-changes"
    validation = validate_merged_model(model, profile="structural-fast")
    assert "validation" in validation
