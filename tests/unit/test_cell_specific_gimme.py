import json
from pathlib import Path

import cobra
import pytest

from thg_protocol.cell_specific import (
    GimmeObjectiveRequirement,
    ReactionExpressionEvidence,
    consensus_from_gimme,
    expression_penalties,
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
            Path(__file__).parents[1] / "fixtures" / "gimme_legacy_reference.json"
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
    assert result.solver_name == model.solver.interface.__name__
    assert result.objective_maxima["out"] == pytest.approx(fixture["objective_maximum"])
    assert result.objective_requirements["out"] == pytest.approx(
        fixture["objective_requirement"]
    )
    assert result.inconsistency_score == pytest.approx(fixture["inconsistency_score"])
    assert {
        reaction_id for reaction_id, active in result.reaction_active.items() if active
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


def test_score_is_exact_only_when_the_expression_determines_it():
    exact_or = reaction_expression_evidence("R", "A or B", {"A": 0.1, "B": 5})
    assert exact_or.exact and exact_or.score == 5
    lower_bound = reaction_expression_evidence("R", "A or B", {"A": 0.1})
    assert not lower_bound.exact and lower_bound.score == 0.1
    zero_complex = reaction_expression_evidence("R", "A and B", {"A": 0})
    assert zero_complex.exact and zero_complex.score == 0
    assert not reaction_expression_evidence("R", "A and B", {"A": 3}).exact


def test_unmeasured_isozyme_is_not_penalized_as_if_absent():
    partial_or = reaction_expression_evidence("R_or", "A or B", {"A": 0.1})
    zero_and = reaction_expression_evidence("R_and", "A and B", {"A": 0})
    measured = reaction_expression_evidence("R_ok", "A", {"A": 0.25})
    assert expression_penalties([partial_or, zero_and, measured], 1.0) == {
        "R_or": 0.0,
        "R_and": 1.0,
        "R_ok": 0.75,
    }


@pytest.mark.parametrize("rule", ["(A or B) and C", "C and (A or B)"])
def test_nested_unmeasured_isozyme_does_not_prove_an_inactive_complex(rule):
    partial = reaction_expression_evidence("R", rule, {"A": 0, "C": 10})
    assert not partial.is_exact
    assert partial.missing_genes == ("B",)
    assert expression_penalties([partial], 1.0) == {"R": 0.0}
    measured = reaction_expression_evidence("R", rule, {"A": 0, "B": 10, "C": 10})
    assert measured.is_exact and measured.score == 10
    zero_subunit = reaction_expression_evidence("R", rule, {"A": 0, "C": 0})
    assert zero_subunit.is_exact and zero_subunit.score == 0
    assert expression_penalties([zero_subunit], 1.0) == {"R": 1.0}


def test_serialized_evidence_without_exact_flag_penalizes_only_measured():
    old_rows = [
        ReactionExpressionEvidence("m", 0.0, "measured", ("A",), ()),
        ReactionExpressionEvidence("p", 0.0, "partial", ("A",), ("B",)),
    ]
    assert expression_penalties(old_rows, 1.0) == {"m": 1.0, "p": 0.0}


def test_gimme_returns_the_minimal_flux_solution_among_equally_consistent_ones():
    model = cobra.Model("detour")
    a, b, c, d, x, y = (cobra.Metabolite(name) for name in "abcdxy")
    model.add_reactions(
        [
            _reaction("in", {a: 1}, (0, 10)),
            _reaction("direct", {a: -1, b: 1}),
            _reaction("d1", {a: -1, c: 1}),
            _reaction("d2", {c: -1, d: 1}),
            _reaction("d3", {d: -1, b: 1}),
            _reaction("out", {b: -1}),
            _reaction("loop1", {x: -1, y: 1}, (-1000, 1000)),
            _reaction("loop2", {y: -1, x: 1}, (-1000, 1000)),
        ]
    )
    result = run_gimme(
        model,
        reaction_expression_for_model(model, {}),
        sample_id="unpenalized",
        expression_threshold=1,
        objectives=[GimmeObjectiveRequirement("out", {"out": 1}, 1.0)],
    )
    assert result.status == "passed"
    assert result.reaction_fluxes["direct"] == pytest.approx(10)
    for detour in ("d1", "d2", "d3", "loop1", "loop2"):
        assert result.reaction_fluxes[detour] == pytest.approx(0, abs=1e-9)
    assert not result.flux_active["d2"]


def test_second_stage_does_not_trade_away_expression_consistency():
    model = _alternatives()
    result = run_gimme(
        model,
        reaction_expression_for_model(model, {"H": 10, "L": 0}),
        sample_id="one",
        expression_threshold=1,
        objectives=[GimmeObjectiveRequirement("out", {"out": 1}, 0.5)],
    )
    assert result.inconsistency_score == pytest.approx(0)
    assert result.reaction_fluxes["low"] == pytest.approx(0)
