"""Native COBRApy/optlang GIMME implementation."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from math import isfinite

from .gpr import ReactionExpressionEvidence


@dataclass(frozen=True)
class GimmeObjectiveRequirement:
    id: str
    coefficients: dict[str, float]
    minimum_fraction_of_optimum: float


@dataclass(frozen=True)
class GimmeResult:
    sample_id: str
    status: str
    inconsistency_score: float | None
    reaction_fluxes: dict[str, float]
    flux_active: dict[str, bool]
    expression_supported: dict[str, bool]
    reaction_active: dict[str, bool]
    penalties: dict[str, float]
    objective_maxima: dict[str, float]
    objective_requirements: dict[str, float]
    objective_achieved: dict[str, float]
    solver_name: str
    warnings: tuple[str, ...] = ()


def expression_penalties(
    evidence: Sequence[ReactionExpressionEvidence], threshold: float
) -> dict[str, float]:
    """Return GIMME penalties for scores the expression data fixes exactly.

    Unknown and no-GPR evidence is unpenalized, and so is a score that only
    bounds the truth from below (an OR with an unmeasured isozyme): that
    isozyme might support the reaction fully.
    """
    if not isfinite(threshold):
        raise ValueError("expression_threshold must be finite")
    return {
        item.reaction_id: (
            max(0.0, threshold - item.score)
            if item.score is not None and item.is_exact
            else 0.0
        )
        for item in evidence
    }


def _solver_name(model) -> str:
    return str(getattr(getattr(model.solver, "interface", None), "__name__", "unknown"))


def _objective_expression(model, coefficients: Mapping[str, float]):
    if not coefficients:
        raise ValueError("GIMME objective coefficients cannot be empty")
    return sum(
        float(coefficient) * model.reactions.get_by_id(reaction_id).flux_expression
        for reaction_id, coefficient in coefficients.items()
    )


def run_gimme(
    model,
    evidence: Sequence[ReactionExpressionEvidence],
    *,
    sample_id: str,
    expression_threshold: float,
    objectives: Sequence[GimmeObjectiveRequirement],
    flux_activity_tolerance: float = 1e-7,
) -> GimmeResult:
    """Solve one non-mutating GIMME reconstruction problem.

    A failed reference or GIMME optimization is returned as explicit evidence,
    never converted into an all-zero activity vector.
    """
    penalties = expression_penalties(evidence, expression_threshold)
    solver = _solver_name(model)

    def empty(status, warning, maxima=None, required=None):
        return GimmeResult(
            sample_id,
            status,
            None,
            {},
            {},
            {},
            {},
            penalties,
            maxima or {},
            required or {},
            {},
            solver,
            (warning,),
        )

    if flux_activity_tolerance <= 0 or not isfinite(flux_activity_tolerance):
        return empty("invalid-input", "flux_activity_tolerance must be positive")
    if not objectives:
        return empty("invalid-input", "at least one objective requirement is required")
    try:
        working = model.copy()
        maxima: dict[str, float] = {}
        requirements: dict[str, float] = {}
        for requirement in objectives:
            if not 0 < requirement.minimum_fraction_of_optimum <= 1:
                return empty("invalid-input", "objective fraction must be in (0, 1]")
            reference = model.copy()
            reference_expression = _objective_expression(
                reference, requirement.coefficients
            )
            reference.objective = reference_expression
            reference.objective_direction = "max"
            solution = reference.optimize()
            if str(solution.status) != "optimal":
                return empty(
                    "objective-infeasible",
                    f"reference objective {requirement.id} is {solution.status}",
                    maxima,
                    requirements,
                )
            maximum = float(solution.objective_value or 0.0)
            if maximum <= flux_activity_tolerance:
                return empty(
                    "objective-infeasible",
                    f"reference objective {requirement.id} is not positive",
                    maxima,
                    requirements,
                )
            maxima[requirement.id] = maximum
            requirements[requirement.id] = (
                maximum * requirement.minimum_fraction_of_optimum
            )
            expression = _objective_expression(working, requirement.coefficients)
            working.add_cons_vars(
                working.problem.Constraint(
                    expression,
                    lb=requirements[requirement.id],
                    name=f"gimme_requirement_{requirement.id}",
                )
            )
        objective = sum(
            penalties.get(reaction.id, 0.0)
            * (reaction.forward_variable + reaction.reverse_variable)
            for reaction in working.reactions
        )
        working.objective = objective
        working.objective_direction = "min"
        solution = working.optimize()
        if str(solution.status) != "optimal":
            return empty(
                "solver-failed",
                f"GIMME optimization is {solution.status}",
                maxima,
                requirements,
            )
        inconsistency = float(solution.objective_value or 0.0)
        warnings: tuple[str, ...] = ()
        # The penalty optimum is rarely unique, and reactions without a penalty
        # may carry arbitrary flux (detours, loops). Hold the optimum and take
        # the minimal-total-flux solution so "active" does not depend on the
        # solver's starting basis.
        working.add_cons_vars(
            working.problem.Constraint(
                objective,
                ub=inconsistency + max(1e-7, 1e-6 * inconsistency),
                name="gimme_penalty_optimum",
            )
        )
        working.objective = sum(
            reaction.forward_variable + reaction.reverse_variable
            for reaction in working.reactions
        )
        working.objective_direction = "min"
        parsimonious = working.optimize()
        if str(parsimonious.status) == "optimal":
            solution = parsimonious
        else:
            warnings = (
                f"minimal-flux refinement is {parsimonious.status}; "
                "reporting the unrefined GIMME solution",
            )
        fluxes = {
            reaction.id: float(solution.fluxes[reaction.id])
            for reaction in working.reactions
        }
        evidence_by_id = {item.reaction_id: item for item in evidence}
        flux_active = {
            key: abs(value) > flux_activity_tolerance for key, value in fluxes.items()
        }
        supported = {
            reaction.id: bool(
                (item := evidence_by_id.get(reaction.id))
                and item.score is not None
                and item.score >= expression_threshold
            )
            for reaction in working.reactions
        }
        active = {
            reaction.id: supported[reaction.id]
            or evidence_by_id.get(
                reaction.id,
                ReactionExpressionEvidence(reaction.id, None, "no-gpr", (), ()),
            ).status
            in {"unknown", "no-gpr"}
            or flux_active[reaction.id]
            for reaction in working.reactions
        }
        achieved = {
            requirement.id: sum(
                coefficient * fluxes[reaction_id]
                for reaction_id, coefficient in requirement.coefficients.items()
            )
            for requirement in objectives
        }
        return GimmeResult(
            sample_id,
            "passed",
            inconsistency,
            fluxes,
            flux_active,
            supported,
            active,
            penalties,
            maxima,
            requirements,
            achieved,
            solver,
            warnings,
        )
    except Exception as error:
        return empty("solver-failed", f"{type(error).__name__}: {error}")


__all__ = [
    "GimmeObjectiveRequirement",
    "GimmeResult",
    "expression_penalties",
    "run_gimme",
]
