"""Reusable structural and solver-backed validation for COBRA models.

The validator is deliberately side-effect free: each check receives the model
owned by its caller and solver checks copy it before changing bounds.
"""

from __future__ import annotations

import itertools
from collections import Counter
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .analysis import consistency
from .gpr import ast_gpr

_STRUCTURAL = frozenset({"reference-integrity", "identifier-uniqueness", "gpr"})
# Blocked reactions are reported but never block a release: a genome-scale
# reconstruction always has reactions without flux under its default bounds.
PROFILES: dict[str, dict[str, object]] = {
    "structural-fast": {"solver": False, "blocking": _STRUCTURAL},
    "beta1-standard": {
        "solver": True,
        "blocking": _STRUCTURAL | {"objective-feasibility"},
    },
    "beta2-standard": {
        "solver": True,
        "blocking": _STRUCTURAL | {"objective-feasibility"},
    },
    "post-gapfill": {
        "solver": True,
        "blocking": _STRUCTURAL | {"objective-feasibility"},
    },
    "final-standard": {
        "solver": True,
        "blocking": _STRUCTURAL | {"objective-feasibility"},
    },
    "cell-specific-standard": {
        "solver": True,
        "blocking": _STRUCTURAL | {"objective-feasibility"},
    },
    "release-full": {
        "solver": True,
        "blocking": _STRUCTURAL
        | {"mass-balance", "charge-balance", "objective-feasibility"},
    },
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
        passed = value.get("passed") if isinstance(value, Mapping) else value
        passed = passed if isinstance(passed, bool) else None
        detail_status = value.get("status") if isinstance(value, Mapping) else None
        return CheckResult(
            check_id,
            family,
            (
                "infrastructure-error"
                if passed is None and detail_status == "infrastructure-error"
                else "not-evaluated"
                if passed is None
                else "passed"
                if passed
                else "failed"
            ),
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
            identifier
            for identifier, count in Counter(item.id for item in items).items()
            if count > 1
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


def fractional_coefficients(
    model: Any,
    *,
    reference_model: Any | None = None,
    exclusions: Iterable[str] = (),
) -> dict[str, object]:
    """List internal reactions with non-integer stoichiometric coefficients.

    Fitted coefficients (``1.2 O2``, ``1.5 product``) are a common source of
    mass creation. Boundary reactions and the reactions the conservation check
    excludes (biomass, artificial/pool, model notes, the reference model's
    exclusions and configured IDs) are skipped, since pseudo-reactions are
    fractional by design.
    """
    from .analysis.conservation import conservation_exclusions

    skipped = conservation_exclusions(
        model, input_model=reference_model, configured=exclusions
    )
    reactions = {}
    for reaction in model.reactions:
        if reaction.boundary or reaction.id in skipped:
            continue
        fractional = {
            metabolite.id: float(coefficient)
            for metabolite, coefficient in reaction.metabolites.items()
            if abs(coefficient - round(coefficient)) > 1e-6
        }
        if fractional:
            reactions[reaction.id] = {
                "coefficients": dict(sorted(fractional.items())),
                "equation": reaction.build_reaction_string(),
            }
    return {
        "reactions": dict(sorted(reactions.items())),
        "skipped": len(skipped),
        "passed": not reactions,
    }


def _base_id(metabolite: Any) -> str | None:
    """Return the metabolite ID without its compartment suffix, if it has one."""
    compartment = getattr(metabolite, "compartment", None)
    if not compartment:
        return None
    for suffix in (f"_{compartment}", str(compartment)):
        if metabolite.id.endswith(suffix) and len(metabolite.id) > len(suffix):
            return metabolite.id[: -len(suffix)]
    return None


def _formula_key(formula: object) -> tuple[tuple[str, int], ...] | None:
    from .model_build.mass_balance import formula_atoms

    atoms = formula_atoms(formula) if isinstance(formula, str) else {}
    return tuple(sorted(atoms.items())) if atoms else None


def formula_disagreement(
    model: Any, *, reference_model: Any | None = None
) -> dict[str, object]:
    """Find metabolites whose formula or charge disagrees with a counterpart.

    Compares the same metabolite across compartments (IDs equal after removing
    the compartment suffix, as ``MAM00668c``/``MAM00668m`` or ``C03024_c``)
    and, with ``reference_model``, the same ID in the reference. Formulas are
    compared as element counts, so ``CH1O2`` equals ``CHO2``. Missing formulas
    and charges are not compared.
    """
    groups: dict[str, list[Any]] = {}
    for metabolite in model.metabolites:
        base = _base_id(metabolite)
        if base is not None:
            groups.setdefault(base, []).append(metabolite)

    def differs(items: Iterable[Any], attribute: str) -> bool:
        values = {
            _formula_key(item.formula) if attribute == "formula" else item.charge
            for item in items
        }
        values.discard(None)
        return len(values) > 1

    def describe(item: Any) -> dict[str, object]:
        return {"formula": item.formula or None, "charge": item.charge}

    compartments = {}
    for base, items in sorted(groups.items()):
        fields = [name for name in ("formula", "charge") if differs(items, name)]
        if fields:
            compartments[base] = {
                "differs": fields,
                "metabolites": {item.id: describe(item) for item in items},
            }
    reference = {}
    if reference_model is not None:
        for item in model.metabolites:
            if item.id not in reference_model.metabolites:
                continue
            other = reference_model.metabolites.get_by_id(item.id)
            fields = [
                name for name in ("formula", "charge") if differs((item, other), name)
            ]
            if fields:
                reference[item.id] = {
                    "differs": fields,
                    "model": describe(item),
                    "reference": describe(other),
                }
    return {
        "across_compartments": compartments,
        "against_reference": reference,
        "reference": None if reference_model is None else reference_model.id,
        "passed": not compartments and not reference,
    }


#: Annotation namespaces compared by ``annotation_conflict``. ChEBI is left
#: out: it gives an acid and its conjugate base different IDs.
IDENTITY_ANNOTATIONS = ("kegg.compound",)
#: ``unusual_protons`` flags reactions with more protons than this
#: (Human-GEM 2022-06-21 has 63 such reactions, mostly transport chains).
PROTON_LIMIT = 10


def _identifiers(metabolite: Any) -> dict[str, set[str]]:
    annotation = getattr(metabolite, "annotation", {}) or {}
    result = {}
    for key in IDENTITY_ANNOTATIONS:
        value = annotation.get(key)
        values = set(value if isinstance(value, list) else [value]) - {None, ""}
        if values:
            result[key] = {str(item) for item in values}
    return result


def _identity_conflict(first: Any, second: Any) -> list[str]:
    """Reasons two metabolites with the same name are different compounds."""
    from .model_build.mass_balance import formulas_conflict

    reasons = []
    if formulas_conflict(first.formula, second.formula):
        reasons.append("formula")
    ours, theirs = _identifiers(first), _identifiers(second)
    reasons.extend(
        key
        for key in IDENTITY_ANNOTATIONS
        if key in ours and key in theirs and not ours[key] & theirs[key]
    )
    return reasons


def _describe_identity(metabolite: Any) -> dict[str, object]:
    return {
        "formula": metabolite.formula or None,
        **{key: sorted(value) for key, value in _identifiers(metabolite).items()},
    }


def annotation_conflict(
    model: Any, *, reference_model: Any | None = None
) -> dict[str, object]:
    """Find mislabelled metabolites: shared names and renamed reference IDs.

    Within the model, metabolites with the same name (ignoring case) but
    different IDs after removing the compartment suffix are reported when
    their formulas differ beyond hydrogen or their KEGG identifiers are
    disjoint. With ``reference_model``, a metabolite is reported as renamed
    when its ID is in the reference under another name and its new name
    belongs to a different, conflicting metabolite there. Both catch a merge
    that mapped a compound onto the wrong metabolite and overwrote its name:
    the legacy merge behind THG β1 renamed Human-GEM's ``MAM00668``
    (2-naphthol, ``C10H8O``) to icosapentaenoic acid, which ``MAM01784``
    (``C20H29O2``) already is.
    """

    def by_name(source: Any) -> dict[str, list[Any]]:
        groups: dict[str, list[Any]] = {}
        for metabolite in source.metabolites:
            if metabolite.name:
                groups.setdefault(metabolite.name.casefold(), []).append(metabolite)
        return groups

    within = {}
    for name, items in sorted(by_name(model).items()):
        bases: dict[str, Any] = {}
        for item in sorted(items, key=lambda value: value.id):
            bases.setdefault(_base_id(item) or item.id, item)
        if len(bases) < 2:
            continue
        reasons = sorted(
            {
                reason
                for first, second in itertools.combinations(bases.values(), 2)
                for reason in _identity_conflict(first, second)
            }
        )
        if reasons:
            within[name] = {
                "conflicts": reasons,
                "metabolites": {
                    item.id: _describe_identity(item)
                    for item in sorted(items, key=lambda value: value.id)
                },
            }
    renamed = {}
    if reference_model is not None:
        named = by_name(reference_model)
        for item in sorted(model.metabolites, key=lambda value: value.id):
            if item.id not in reference_model.metabolites:
                continue
            original = reference_model.metabolites.get_by_id(item.id)
            if (item.name or "").casefold() == (original.name or "").casefold():
                continue
            base = _base_id(item) or item.id
            owners = [
                other
                for other in named.get((item.name or "").casefold(), [])
                if (_base_id(other) or other.id) != base
                and _identity_conflict(item, other)
            ]
            if owners:
                renamed[item.id] = {
                    "reference_name": original.name,
                    "model_name": item.name,
                    "model": _describe_identity(item),
                    "name_belongs_to": {
                        other.id: _describe_identity(other)
                        for other in sorted(owners, key=lambda value: value.id)
                    },
                }
    return {
        "within_model": within,
        "renamed_from_reference": renamed,
        "reference": None if reference_model is None else reference_model.id,
        "passed": not within and not renamed,
    }


def unusual_protons(
    model: Any,
    *,
    reference_model: Any | None = None,
    exclusions: Iterable[str] = (),
    limit: int = PROTON_LIMIT,
) -> dict[str, object]:
    """List internal reactions with more than ``limit`` protons (H+, charge +1).

    A large proton coefficient often marks a reaction balanced against a wrong
    formula, as ``EPA-CoA + H2O -> 2 EPA + CoA + 14 H+``. Reactions the
    conservation check excludes are skipped. With ``reference_model``, a
    reaction with the same proton coefficients there is not reported, so
    inherited transport chains do not drown the new cases.
    """
    from .analysis.conservation import conservation_exclusions
    from .model_build.mass_balance import formula_atoms

    skipped = conservation_exclusions(
        model, input_model=reference_model, configured=exclusions
    )
    reactions = {}
    for reaction in model.reactions:
        if reaction.boundary or reaction.id in skipped:
            continue
        protons = {
            metabolite.id: float(coefficient)
            for metabolite, coefficient in reaction.metabolites.items()
            if formula_atoms(metabolite.formula or "") == {"H": 1}
            and metabolite.charge == 1
            and abs(coefficient) > limit
        }
        if (
            protons
            and reference_model is not None
            and reaction.id in reference_model.reactions
        ):
            original = {
                metabolite.id: float(coefficient)
                for metabolite, coefficient in reference_model.reactions.get_by_id(
                    reaction.id
                ).metabolites.items()
            }
            if all(original.get(key) == value for key, value in protons.items()):
                continue
        if protons:
            reactions[reaction.id] = {
                "protons": protons,
                "equation": reaction.build_reaction_string(),
            }
    return {
        "limit": limit,
        "reactions": dict(sorted(reactions.items())),
        "passed": not reactions,
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


def stoichiometric_consistency(
    model: Any,
    *,
    exclusions: Iterable[str] = (),
    reference_model: Any | None = None,
    identify: bool = True,
) -> dict[str, object]:
    """Name the unconserved metabolites (Gevorgyan et al. 2008).

    Uses MEMOTE's consistency functions with the model's solver. With
    ``identify=False`` only the consistency LP runs: an inconsistent model
    fails without naming its unconserved metabolites, which skips MEMOTE's
    MILP. Boundary,
    biomass (SBO:0000629), artificial/pool and configured reactions are
    excluded, as are the reactions ``reference_model`` excludes; the details
    list each exclusion with its rule. Without MEMOTE
    installed the check is reported as not evaluated.
    """
    try:
        import memote.support.consistency  # noqa: F401
    except ImportError:
        return {
            "status": "not-evaluated",
            "reason": "requires the optional 'memote' dependency",
            "passed": None,
        }
    try:
        from .analysis.conservation import find_unconserved_metabolites

        return find_unconserved_metabolites(
            model,
            input_model=reference_model,
            configured=exclusions,
            identify=identify,
        )
    except Exception as error:
        return {"status": "infrastructure-error", "error": str(error), "passed": None}


def minimal_inconsistent_sets(
    model: Any, *, maximum: int | None = None
) -> dict[str, object]:
    """Return blocked-reaction singletons, not a mathematical MIS analysis."""
    blocked = consistency.blocked_reactions(model)
    sets = [[reaction_id] for reaction_id in blocked]
    if maximum is not None:
        sets = sets[:maximum]
    return {
        "method": "blocked-reaction-singletons",
        "complete": maximum is None or maximum >= len(blocked),
        "sets": sets,
        "passed": not blocked,
    }


def load_model(path: str | Path) -> Any:
    """Load JSON or SBML and verify that the model can be traversed."""
    from thg_protocol.io.models import load_model as load_cobra_model

    model = load_cobra_model(path)
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
    conservation_exclusions: Iterable[str] = (),
    reference_model: Any | None = None,
    propose_fixes: bool = False,
) -> dict[str, object]:
    """Run an independently callable validation profile and return JSON data.

    ``reference_model`` (optional) is the model the checked one derives from:
    formulas and charges are compared against it, and the reactions it
    excludes from conservation checks stay excluded. With ``propose_fixes``
    the result also holds ``proposals`` for the failed checks a rule can fix
    and an ``index`` of the reactions and metabolites the checks mention (see
    ``validation_fixes``); a curator decides on them in the HTML report.
    """
    if profile not in PROFILES:
        raise ValueError(f"unknown validation profile: {profile}")
    solver = bool(PROFILES[profile]["solver"]) if run_solver is None else run_solver
    blocking = PROFILES[profile]["blocking"]
    # Several checks consume the same model-wide topology/solver result. Cache
    # those values for the duration of this validation pass; in particular,
    # the blocked-reaction analysis invokes an FVA sweep.
    cached: dict[str, object] = {}

    def _cached(name: str, fn: Callable[[], object]) -> object:
        if name not in cached:
            cached[name] = fn()
        return cached[name]

    def _dead_ends() -> list[str]:
        return list(
            _cached(
                "dead-end-metabolites",
                lambda: consistency.dead_end_metabolites(model),
            )
        )

    def _not_produced() -> list[str]:
        return list(
            _cached("not-produced", lambda: consistency.metabolites_not_produced(model))
        )

    def _not_consumed() -> list[str]:
        return list(
            _cached("not-consumed", lambda: consistency.metabolites_not_consumed(model))
        )

    def _blocked() -> list[str]:
        return list(
            _cached("blocked-reactions", lambda: consistency.blocked_reactions(model))
        )

    checks = [
        _check(
            "reference-integrity",
            "structural",
            lambda: _references(model),
            blocking="reference-integrity" in blocking,
        ),
        _check(
            "identifier-uniqueness",
            "structural",
            lambda: _ids(model),
            blocking="identifier-uniqueness" in blocking,
        ),
        _check("gpr", "structural", lambda: _gprs(model), blocking="gpr" in blocking),
        _check(
            "mass-balance",
            "chemical",
            lambda: _mass_balance(model),
            blocking="mass-balance" in blocking,
        ),
        _check(
            "charge-balance",
            "chemical",
            lambda: _charge_balance(model),
            blocking="charge-balance" in blocking,
        ),
        _check(
            "fractional-coefficients",
            "chemical",
            lambda: fractional_coefficients(
                model,
                reference_model=reference_model,
                exclusions=conservation_exclusions,
            ),
            blocking=False,
        ),
        _check(
            "formula-disagreement",
            "chemical",
            lambda: formula_disagreement(model, reference_model=reference_model),
            blocking=False,
        ),
        _check(
            "annotation-conflict",
            "chemical",
            lambda: annotation_conflict(model, reference_model=reference_model),
            blocking=False,
        ),
        _check(
            "unusual-protons",
            "chemical",
            lambda: unusual_protons(
                model,
                reference_model=reference_model,
                exclusions=conservation_exclusions,
            ),
            blocking=False,
        ),
        _check(
            "dead-end-topology",
            "topology",
            lambda: {
                "metabolites": _dead_ends(),
                "passed": not _dead_ends(),
            },
            blocking=False,
        ),
        _check(
            "unconserved-metabolites",
            "topology",
            lambda: {
                "not-produced": _not_produced(),
                "not-consumed": _not_consumed(),
                "passed": not (_not_produced() or _not_consumed()),
            },
            blocking=False,
        ),
        _check(
            "stoichiometric-consistency",
            "stoichiometry",
            lambda: stoichiometric_consistency(
                model,
                exclusions=conservation_exclusions,
                reference_model=reference_model,
                identify=solver,
            ),
            blocking="stoichiometric-consistency" in blocking,
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
                        "blocked": _blocked(),
                        "passed": not _blocked(),
                    },
                    blocking="flux-consistency" in blocking,
                ),
                _check(
                    "blocked-reaction-singletons",
                    "solver",
                    lambda: {
                        "method": "blocked-reaction-singletons",
                        "complete": True,
                        "sets": [[reaction_id] for reaction_id in _blocked()],
                        "passed": not _blocked(),
                    },
                    blocking=False,
                ),
                _check(
                    "objective-feasibility",
                    "solver",
                    lambda: _objective(model),
                    blocking="objective-feasibility" in blocking,
                ),
            ]
        )
    passed = all(item.passed is True for item in checks if item.release_blocking)
    records = [item.to_dict() for item in checks]
    fixes: dict[str, object] = {}
    if propose_fixes:
        from .validation_fixes import build_index, collect_fixes

        try:
            proposals = collect_fixes(model, records, reference_model=reference_model)
            fixes = {
                "proposals": proposals,
                "index": build_index(model, records, proposals),
            }
        except Exception as error:  # a failed proposal step must not hide results
            fixes = {
                "proposals": [],
                "proposal_error": f"{type(error).__name__}: {error}",
            }
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
        "checks": records,
        "solver": {"requested": solver, "configuration": solver_configuration},
        **fixes,
    }


__all__ = [
    "IDENTITY_ANNOTATIONS",
    "PROFILES",
    "PROTON_LIMIT",
    "CheckResult",
    "annotation_conflict",
    "formula_disagreement",
    "fractional_coefficients",
    "load_model",
    "minimal_inconsistent_sets",
    "stoichiometric_consistency",
    "unusual_protons",
    "validate_model",
]
