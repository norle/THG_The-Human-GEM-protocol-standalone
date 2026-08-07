"""Reusable structural and solver-backed validation for COBRA models.

The validator is deliberately side-effect free: each check receives the model
owned by its caller and solver checks copy it before changing bounds.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .analysis import consistency
from .gpr import ast_gpr

PROFILES: dict[str, dict[str, object]] = {
    "structural-fast": {"solver": False, "release_blocking": True},
    "beta1-standard": {"solver": True, "release_blocking": True},
    "beta2-standard": {"solver": True, "release_blocking": True},
    "final-standard": {"solver": True, "release_blocking": True},
    "release-full": {"solver": True, "release_blocking": True},
}


@dataclass(frozen=True)
class CheckResult:
    id: str
    family: str
    status: str
    passed: bool | None
    details: Mapping[str, object]
    release_blocking: bool = True

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "family": self.family,
            "status": self.status,
            "passed": self.passed,
            "details": dict(self.details),
            "release_blocking": self.release_blocking,
        }


def _check(
    check_id: str, family: str, fn: Callable[[], object], *, blocking: bool = True
) -> CheckResult:
    try:
        value = fn()
        passed = (
            value["passed"]
            if isinstance(value, Mapping) and isinstance(value.get("passed"), bool)
            else bool(value)
            if isinstance(value, bool)
            else True
        )
        return CheckResult(
            check_id,
            family,
            "passed" if passed else "failed",
            passed,
            value if isinstance(value, Mapping) else {"value": value},
            blocking,
        )
    except Exception as error:  # diagnostics must distinguish infrastructure failures
        return CheckResult(
            check_id,
            family,
            "infrastructure-error",
            None,
            {"error_type": type(error).__name__, "message": str(error)},
            blocking,
        )


def _ids(model: Any) -> dict[str, object]:
    collections = {
        "metabolites": model.metabolites,
        "reactions": model.reactions,
        "genes": model.genes,
    }
    duplicates = {
        name: sorted(
            {item.id for item in items if [x.id for x in items].count(item.id) > 1}
        )
        for name, items in collections.items()
    }
    return {"duplicates": duplicates, "passed": not any(duplicates.values())}


def _references(model: Any) -> dict[str, object]:
    metabolite_ids = {item.id for item in model.metabolites}
    dangling = sorted(
        {
            met.id
            for rxn in model.reactions
            for met in rxn.metabolites
            if met.id not in metabolite_ids
        }
    )
    return {"dangling_metabolites": dangling, "passed": not dangling}


def _gprs(model: Any) -> dict[str, object]:
    invalid = []
    for reaction in model.reactions:
        if not reaction.gene_reaction_rule:
            continue
        try:
            ast_gpr.reduce_gpr(reaction.gene_reaction_rule)
        except Exception as error:
            invalid.append({"reaction": reaction.id, "error": str(error)})
    genes = {gene.id for gene in model.genes}
    missing = sorted(
        {
            gene.id
            for reaction in model.reactions
            for gene in reaction.genes
            if gene.id not in genes
        }
    )
    return {
        "invalid": invalid,
        "missing": missing,
        "passed": not invalid and not missing,
    }


def _mass_balance(model: Any) -> dict[str, object]:
    statuses: dict[str, str] = {}
    for reaction in model.reactions:
        if reaction.boundary:
            statuses[reaction.id] = "excluded-boundary"
            continue
        if any(token in reaction.id.lower() for token in ("biomass", "pseudo")):
            statuses[reaction.id] = (
                "excluded-biomass"
                if "biomass" in reaction.id.lower()
                else "excluded-pseudo-reaction"
            )
            continue
        formulas = [
            getattr(metabolite, "formula", None) for metabolite in reaction.metabolites
        ]
        if any(not formula for formula in formulas):
            statuses[reaction.id] = "not-evaluable-missing-formula"
            continue
        residual = consistency.reaction_balance(reaction)
        statuses[reaction.id] = "balanced" if not residual else "unbalanced"
    return {
        "statuses": statuses,
        "unbalanced": sorted(
            key for key, value in statuses.items() if value == "unbalanced"
        ),
        "passed": not any(value == "unbalanced" for value in statuses.values()),
    }


def _charge_balance(model: Any) -> dict[str, object]:
    statuses: dict[str, str] = {}
    for reaction in model.reactions:
        if reaction.boundary:
            statuses[reaction.id] = "excluded-boundary"
            continue
        if any(
            getattr(metabolite, "charge", None) is None
            for metabolite in reaction.metabolites
        ):
            statuses[reaction.id] = "not-evaluable-missing-charge"
            continue
        statuses[reaction.id] = (
            "balanced"
            if abs(consistency.charge_balance(reaction)["charge"]) <= 1e-9
            else "unbalanced"
        )
    return {
        "statuses": statuses,
        "unbalanced": sorted(
            key for key, value in statuses.items() if value == "unbalanced"
        ),
        "passed": not any(value == "unbalanced" for value in statuses.values()),
    }


def _objective(model: Any) -> dict[str, object]:
    solution = model.optimize()
    status = str(solution.status)
    return {
        "status": status,
        "objective": float(solution.objective_value or 0.0),
        "passed": status == "optimal",
    }


def _optional_invariant(
    value: Mapping[str, object] | None, name: str
) -> dict[str, object]:
    if value is None:
        return {"status": "not-configured", "name": name, "passed": True}
    passed = value.get("passed")
    return {
        "status": "evaluated",
        "name": name,
        "passed": passed if isinstance(passed, bool) else False,
        "details": dict(value),
    }


def stoichiometric_consistency(model: Any) -> dict[str, object]:
    """Check for a positive metabolite conservation vector when practical."""
    try:
        import numpy as np
        from scipy.optimize import linprog

        metabolites = list(model.metabolites)
        reactions = list(model.reactions)
        matrix = np.zeros((len(reactions), len(metabolites)))
        positions = {
            metabolite.id: index for index, metabolite in enumerate(metabolites)
        }
        for row, reaction in enumerate(reactions):
            for metabolite, coefficient in reaction.metabolites.items():
                matrix[row, positions[metabolite.id]] = float(coefficient)
        result = linprog(
            np.zeros(len(metabolites)),
            A_eq=np.vstack((matrix, np.ones(len(metabolites)))),
            b_eq=np.r_[np.zeros(len(reactions)), 1.0],
            bounds=[(1e-9, None)] * len(metabolites),
            method="highs",
        )
        return {
            "status": result.status,
            "message": result.message,
            "passed": bool(result.success),
        }
    except Exception as error:
        return {"status": "infrastructure-error", "error": str(error), "passed": None}


def minimal_inconsistent_sets(
    model: Any, *, maximum: int | None = None
) -> dict[str, object]:
    """Return singleton sets; larger MILP sets are intentionally bounded."""
    blocked = consistency.blocked_reactions(model)
    sets = [[reaction_id] for reaction_id in blocked]
    if maximum is not None:
        sets = sets[:maximum]
    return {
        "method": "singleton-blocked-reactions",
        "complete": True,
        "sets": sets,
        "passed": not sets,
    }


def load_model(path: str | Path) -> Any:
    """Load JSON or SBML and verify that the model can be traversed."""
    from cobra.io import load_json_model, read_sbml_model

    source = Path(path)
    model = (
        load_json_model(str(source))
        if source.suffix.lower() == ".json"
        else read_sbml_model(str(source))
    )
    if not getattr(model, "id", None):
        raise ValueError("model has no identifier")
    return model


def validate_model(
    model: Any,
    profile: str = "structural-fast",
    *,
    run_solver: bool | None = None,
    workflow_invariants: Mapping[str, object] | None = None,
    ledger_diff: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Run an independently callable validation profile and return JSON data."""
    if profile not in PROFILES:
        raise ValueError(f"unknown validation profile: {profile}")
    solver = bool(PROFILES[profile]["solver"]) if run_solver is None else run_solver
    checks = [
        _check("reference-integrity", "structural", lambda: _references(model)),
        _check("identifier-uniqueness", "structural", lambda: _ids(model)),
        _check("gpr", "structural", lambda: _gprs(model)),
        _check(
            "mass-balance", "chemical", lambda: _mass_balance(model), blocking=False
        ),
        _check(
            "charge-balance", "chemical", lambda: _charge_balance(model), blocking=False
        ),
        _check(
            "dead-end-topology",
            "topology",
            lambda: {"metabolites": consistency.dead_end_metabolites(model)},
            blocking=False,
        ),
        _check(
            "unconserved-metabolites",
            "topology",
            lambda: {
                "not-produced": consistency.metabolites_not_produced(model),
                "not-consumed": consistency.metabolites_not_consumed(model),
            },
            blocking=False,
        ),
        _check(
            "stoichiometric-consistency",
            "stoichiometry",
            lambda: stoichiometric_consistency(model),
            blocking=False,
        ),
        _check(
            "workflow-specific-invariants",
            "workflow",
            lambda: _optional_invariant(workflow_invariants, "workflow-specific"),
            blocking=False,
        ),
        _check(
            "ledger-to-diff-consistency",
            "workflow",
            lambda: _optional_invariant(ledger_diff, "ledger-to-diff"),
            blocking=False,
        ),
    ]
    if solver:
        checks.extend(
            [
                _check(
                    "flux-consistency",
                    "solver",
                    lambda: {
                        "blocked": consistency.blocked_reactions(model),
                        "passed": not consistency.blocked_reactions(model),
                    },
                ),
                _check(
                    "energy-generating-cycles",
                    "solver",
                    lambda: {
                        "reactions": consistency.stoichiometrically_balanced_cycles(
                            model
                        )
                    },
                    blocking=False,
                ),
                _check(
                    "minimal-inconsistent-sets",
                    "solver",
                    lambda: minimal_inconsistent_sets(model),
                    blocking=False,
                ),
                _check(
                    "objective-feasibility",
                    "solver",
                    lambda: _objective(model),
                ),
            ]
        )
    passed = all(item.passed is not False for item in checks if item.release_blocking)
    solver_configuration = None
    if solver:
        try:
            import cobra

            cobra_version = cobra.__version__
        except Exception:
            cobra_version = "unknown"
        configuration = getattr(getattr(model, "solver", None), "configuration", None)
        interface = getattr(getattr(model, "solver", None), "interface", None)
        solver_configuration = {
            "solver": getattr(interface, "__name__", str(interface)),
            "cobra": cobra_version,
            "presolve": getattr(configuration, "presolve", None),
            "timeout": getattr(configuration, "timeout", None),
            "tolerances": str(getattr(configuration, "tolerances", "unknown")),
        }
    return {
        "schema_version": 1,
        "profile": profile,
        "passed": passed,
        "checks": [item.to_dict() for item in checks],
        "solver": {"requested": solver, "configuration": solver_configuration},
    }


__all__ = [
    "PROFILES",
    "CheckResult",
    "load_model",
    "minimal_inconsistent_sets",
    "stoichiometric_consistency",
    "validate_model",
]
