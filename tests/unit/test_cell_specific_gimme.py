import json
from pathlib import Path

import cobra
import pytest

from thg_protocol.cell_specific import (
    GimmeObjectiveRequirement,
    consensus_from_gimme,
    reaction_expression_evidence,
    reaction_expression_for_model,
    run_gimme,
)


def _reaction(identifier, stoichiometry, bounds=(0, 1000), rule=""):
    reaction = cobra.Reaction(identifier, lower_bound=bounds[0], upper_bound=bounds[1])
    reaction.add_metabolites(stoichiometry)
    reaction.gene_reaction_rule = rule
    return reaction


def _alternatives():
    model = cobra.Model("alternatives")
    a, b, c = cobra.Metabolite("a"), cobra.Metabolite("b"), cobra.Metabolite("c")
    model.add_reactions(
        [
            _reaction("in", {a: 1}, (0, 10)),
            _reaction("high", {a: -1, b: 1}, rule="H"),
            _reaction("low", {a: -1, b: 1}, rule="L"),
            _reaction("out", {b: -1}),
            _reaction("low_required", {a: -1, c: 1}, rule="L"),
            _reaction("out_required", {c: -1}),
        ]
    )
    return model


def test_gpr_scores_keep_zero_and_unknown_distinct():
    assert reaction_expression_evidence("R", "A and B", {"A": 0, "B": 100}).score == 0
    partial = reaction_expression_evidence("R", "A and B", {"A": 0})
    assert (
        partial.score == 0
        and partial.status == "partial"
        and partial.missing_genes == ("B",)
    )
    assert reaction_expression_evidence("R", "A or B", {"A": 10}).score == 10
    assert reaction_expression_evidence("R", "A and B", {"A": 10}).status == "unknown"
    assert reaction_expression_evidence("R", "", {}).status == "no-gpr"


def test_gimme_prefers_high_expression_path_and_does_not_mutate_model():
    model = _alternatives()
    result = run_gimme(
        model,
        reaction_expression_for_model(model, {"H": 10, "L": 0}),
        sample_id="one",
        expression_threshold=1,
        objectives=[GimmeObjectiveRequirement("out", {"out": 1}, 0.5)],
    )
    assert result.status == "passed"
    assert result.reaction_fluxes["high"] > 0
    assert result.reaction_fluxes["low"] == pytest.approx(0)
    assert model.reactions.low.lower_bound == 0


def test_native_gimme_matches_frozen_compatibility_fixture():
    fixture = json.loads(
        (
            Path(__file__).parents[1]
            / "fixtures"
            / "gimme_legacy_reference.json"
        ).read_text()
    )
    model = _alternatives()
    objective = fixture["objective"]
    result = run_gimme(
        model,
        reaction_expression_for_model(model, fixture["expression"]),
        sample_id="fixture",
        expression_threshold=fixture["expression_threshold"],
        objectives=[
            GimmeObjectiveRequirement(
                objective["id"],
                objective["coefficients"],
                objective["minimum_fraction_of_optimum"],
            )
        ],
    )
    assert "glpk" in result.solver_name.lower()
    assert result.objective_maxima["out"] == pytest.approx(
        fixture["objective_maximum"]
    )
    assert result.objective_requirements["out"] == pytest.approx(
        fixture["objective_requirement"]
    )
    assert result.inconsistency_score == pytest.approx(fixture["inconsistency_score"])
    assert {
        reaction_id
        for reaction_id, active in result.reaction_active.items()
        if active
    } == set(fixture["active_reactions"])


def test_gimme_keeps_required_low_expression_and_uses_absolute_reversible_flux():
    model = _alternatives()
    result = run_gimme(
        model,
        reaction_expression_for_model(model, {"H": 10, "L": 0}),
        sample_id="one",
        expression_threshold=1,
        objectives=[
            GimmeObjectiveRequirement("out", {"out": 1}, 0.5),
            GimmeObjectiveRequirement("required", {"out_required": 1}, 0.5),
        ],
    )
    assert result.status == "passed"
    assert result.reaction_fluxes["low_required"] >= 5
    assert result.reaction_active["low_required"]

    reversible = cobra.Model("reverse")
    a, b = cobra.Metabolite("a"), cobra.Metabolite("b")
    reversible.add_reactions(
        [
            _reaction("in_b", {b: 1}, (0, 10)),
            _reaction("reverse", {a: -1, b: 1}, (-1000, 0), "L"),
            _reaction("out_a", {a: -1}),
        ]
    )
    reverse = run_gimme(
        reversible,
        reaction_expression_for_model(reversible, {"L": 0}),
        sample_id="reverse",
        expression_threshold=1,
        objectives=[GimmeObjectiveRequirement("out", {"out_a": 1}, 0.5)],
    )
    assert reverse.status == "passed"
    assert reverse.reaction_fluxes["reverse"] <= -5
    assert reverse.inconsistency_score == pytest.approx(
        abs(reverse.reaction_fluxes["reverse"])
    )


def test_consensus_excludes_failed_samples_from_denominator():
    model = _alternatives()
    good = run_gimme(
        model,
        reaction_expression_for_model(model, {"H": 10}),
        sample_id="good",
        expression_threshold=1,
        objectives=[GimmeObjectiveRequirement("out", {"out": 1}, 0.5)],
    )
    bad = run_gimme(
        model,
        (),
        sample_id="bad",
        expression_threshold=1,
        objectives=(),
    )
    consensus = consensus_from_gimme(
        [good, bad], presence_threshold=0, minimum_successful_sample_fraction=0.5
    )
    assert consensus.support["high"] == 1
    assert consensus.failed_samples == ("bad",)
