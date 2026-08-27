import json

import cobra
import pytest

from thg_protocol.database_workflow import harvest_snapshot, normalize_records
from thg_protocol.merge import (
    MergePlan,
    MergePolicy,
    apply_merge_plan,
    generate_merge_plan,
)
from thg_protocol.runtime.stage import StageResult
from thg_protocol.workflow.final_thg import FinalTHGStage


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


def test_final_thg_validation_rejects_failed_nested_report(tmp_path):
    report = tmp_path / "validation.json"
    report.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="validation failed"):
        FinalTHGStage("validate-final-thg").validate(
            StageResult(
                (("validation", report),),
                {"validation": {"passed": False}, "tasks": {"passed": True}},
            )
        )
