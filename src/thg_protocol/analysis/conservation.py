"""Unconserved metabolites: detect, localize, propose and apply fixes.

Detection follows Gevorgyan et al. (2008) through MEMOTE's implementation: a
metabolite is unconserved when no positive mass vector ``m`` with ``Sᵀm = 0``
over the internal reactions gives it a positive weight. Stoichiometry only is
used; bounds, directions and formulas are ignored. Localization solves one
elastic LP that gives every metabolite a positive mass and blames the few
reactions that must create or destroy mass (preferring chemically suspect ones
where several are equally cheap), then flags what is chemically
wrong with each (element or charge imbalance, non-integer coefficients,
formula disagreements). Fix proposals use the
``workflow.proposals`` records and are applied only after curator approval.
"""

from __future__ import annotations

import itertools
import math
import re
import warnings
from collections import defaultdict
from collections.abc import Iterable, Mapping
from typing import TYPE_CHECKING, Any

from optlang.interface import OPTIMAL
from optlang.symbolics import Zero

from thg_protocol.model_build.mass_balance import formula_atoms

if TYPE_CHECKING:
    from thg_protocol.workflow.proposals import Decision, Proposal

BIOMASS_SBO = "SBO:0000629"
PSEUDO_SUBSYSTEMS = frozenset({"Artificial reactions", "Pool reactions"})
EXCLUSION_NOTE = "conservation_exclusion"
STAGE = "conservation"
TOLERANCE = 1e-9
#: Relative extra cost of blaming a reaction without a chemical flag.
TIE_BREAK = 1e-3
_PSEUDO_PATTERN = re.compile(r"biomass|pool|pseudo|lumped|artificial", re.IGNORECASE)

#: Cofactor additions tried against an element residual, by metabolite name.
#: Each is also tried negated (e.g. NADH + H+ -> NAD+).
COFACTOR_FIXES: tuple[tuple[str, Mapping[str, int]], ...] = (
    ("NAD+/NADH", {"NAD+": -1, "NADH": 1, "H+": 1}),
    ("NADP+/NADPH", {"NADP+": -1, "NADPH": 1, "H+": 1}),
    ("H2O", {"H2O": 1}),
    ("CO2", {"CO2": 1}),
    ("Pi", {"Pi": 1}),
    ("CoA", {"CoA": 1}),
)

# --------------------------------------------------------------------------
# Exclusions
# --------------------------------------------------------------------------


def _sbo_terms(reaction: Any) -> set[str]:
    value = (getattr(reaction, "annotation", None) or {}).get("sbo")
    if isinstance(value, str):
        return {value}
    if isinstance(value, (list, tuple, set)):
        return {str(item) for item in value}
    return set()


def _subsystems(model: Any) -> dict[str, set[str]]:
    result: dict[str, set[str]] = defaultdict(set)
    for reaction in model.reactions:
        subsystem = getattr(reaction, "subsystem", None)
        if isinstance(subsystem, str) and subsystem:
            result[reaction.id].add(subsystem)
        elif isinstance(subsystem, (list, tuple)):
            result[reaction.id].update(str(item) for item in subsystem)
    for group in getattr(model, "groups", ()):
        for member in getattr(group, "members", ()):
            if hasattr(member, "metabolites") and getattr(group, "name", None):
                result[member.id].add(str(group.name))
    return result


def _own_exclusions(model: Any) -> dict[str, str]:
    subsystems = _subsystems(model)
    result: dict[str, str] = {}
    for reaction in model.reactions:
        if reaction.boundary:
            continue
        if BIOMASS_SBO in _sbo_terms(reaction):
            result[reaction.id] = "sbo-biomass"
        elif subsystems.get(reaction.id, set()) & PSEUDO_SUBSYSTEMS:
            result[reaction.id] = "pseudo-subsystem"
        elif EXCLUSION_NOTE in (getattr(reaction, "notes", None) or {}):
            result[reaction.id] = "model-note"
    return result


def conservation_exclusions(
    model: Any,
    *,
    input_model: Any | None = None,
    configured: Iterable[str] = (),
) -> dict[str, str]:
    """Return internal reactions excluded from conservation, with their rule.

    Rules, in order: biomass SBO term, Human-GEM's artificial/pool subsystems,
    an approved exclusion recorded in the reaction notes, excluded in the input
    model (by ID), and listed in the configuration. Boundary reactions are
    always excluded and are not listed.
    """
    result = _own_exclusions(model)
    present = {reaction.id for reaction in model.reactions if not reaction.boundary}
    if input_model is not None:
        for reaction_id in conservation_exclusions(input_model):
            if reaction_id in present:
                result.setdefault(reaction_id, "input-model")
    for reaction_id in configured:
        if reaction_id in present:
            result.setdefault(str(reaction_id), "configuration")
    return dict(sorted(result.items()))


def _memote_consistency() -> Any:
    try:
        from memote.support import consistency
    except ImportError as error:  # pragma: no cover - optional dependency path
        raise RuntimeError(
            "conservation checks require MEMOTE: pip install 'thg-protocol[memote]'"
        ) from error
    return consistency


def _pruned(model: Any, exclusions: Mapping[str, str], solver: str | None) -> Any:
    """Return a copy without the excluded reactions, for MEMOTE's internals."""
    pruned = model.copy()
    with warnings.catch_warnings():
        # cobra warns while dropping removed reactions from subsystem groups.
        warnings.simplefilter("ignore", UserWarning)
        pruned.remove_reactions(
            [pruned.reactions.get_by_id(reaction_id) for reaction_id in exclusions]
        )
    if solver is not None:
        pruned.solver = solver
    return pruned


def _describe(metabolite: Any) -> dict[str, object]:
    return {
        "id": metabolite.id,
        "name": getattr(metabolite, "name", "") or "",
        "compartment": getattr(metabolite, "compartment", None),
    }


# --------------------------------------------------------------------------
# Step 1: detect
# --------------------------------------------------------------------------


def find_unconserved_metabolites(
    model: Any,
    *,
    input_model: Any | None = None,
    configured: Iterable[str] = (),
    exclusions: Mapping[str, str] | None = None,
    solver: str | None = None,
    identify: bool = True,
) -> dict[str, object]:
    """Name the metabolites no positive conservation vector can weight.

    Runs MEMOTE's ``check_stoichiometric_consistency`` (one LP) and, only when
    that fails and ``identify`` is true, ``find_unconserved_metabolites`` (one
    MILP), both on a copy of the model without the excluded reactions and with
    the model's solver unless ``solver`` is given. With ``identify=False`` an
    inconsistent model reports ``unconserved`` as ``None``. Reactions MEMOTE
    itself treats as biomass are added to the exclusions with the rule
    ``memote-biomass``.
    """
    consistency = _memote_consistency()
    from memote.support.helpers import find_biomass_reaction

    if exclusions is None:
        exclusions = conservation_exclusions(
            model, input_model=input_model, configured=configured
        )
    pruned = _pruned(model, exclusions, solver)
    excluded = dict(exclusions)
    for reaction in find_biomass_reaction(pruned):
        excluded.setdefault(reaction.id, "memote-biomass")
    base = {
        "excluded": dict(sorted(excluded.items())),
        "boundary_reactions": len(model.boundary),
        "internal_reactions": len(model.reactions)
        - len(model.boundary)
        - len(excluded),
        "solver": getattr(pruned.solver.interface, "__name__", str(pruned.solver)),
    }
    if consistency.check_stoichiometric_consistency(pruned):
        return {**base, "consistent": True, "unconserved": [], "passed": True}
    if not identify:
        return {**base, "consistent": False, "unconserved": None, "passed": False}
    unconserved = sorted(
        (_describe(item) for item in consistency.find_unconserved_metabolites(pruned)),
        key=lambda item: str(item["id"]),
    )
    return {
        **base,
        "consistent": False,
        "unconserved": unconserved,
        "passed": False,
    }


# --------------------------------------------------------------------------
# Step 2: localize
# --------------------------------------------------------------------------


def _round(value: float) -> float:
    rounded = round(float(value), 6)
    return int(rounded) if rounded == int(rounded) else rounded


def chemically_suspect(model: Any, exclusions: Mapping[str, str]) -> set[str]:
    """Internal reactions with an element or charge imbalance, a metabolite
    without formula or charge, or a non-integer coefficient."""
    suspect = set()
    for reaction in model.reactions:
        if reaction.boundary or reaction.id in exclusions:
            continue
        stoichiometry = _stoichiometry(reaction)
        if (
            fractional(stoichiometry)
            or not element_residual(stoichiometry, model)["balanced"]
            or not charge_residual(stoichiometry, model)["balanced"]
        ):
            suspect.add(reaction.id)
    return suspect


def blame_reactions(
    model: Any,
    *,
    exclusions: Mapping[str, str],
    prefer: Iterable[str] = (),
    solver: str | None = None,
) -> dict[str, object]:
    """Find a small set of reactions that break mass conservation, in one LP.

    Solves ``min Σ|s_j|`` subject to ``Σ_i S_ij m_i = s_j`` and ``m_i ≥ 1``
    over the non-excluded internal reactions: every metabolite gets a positive
    mass, and ``s_j`` is the mass that reaction ``j`` creates (positive) or
    destroys (negative). Reactions with ``s_j ≠ 0`` are blamed. Removing them
    always leaves a consistent model, since ``m`` then conserves every
    remaining reaction. The L1 objective keeps the set small but not provably
    minimal. Where a loop can be broken at several reactions at equal cost,
    reactions in ``prefer`` are blamed first: every other reaction costs
    ``1 + TIE_BREAK``, which decides ties but never changes the optimum by more
    than that fraction. The problem is built in the model's solver interface,
    as MEMOTE builds its consistency problems.
    """
    preferred = set(prefer)
    pruned = _pruned(model, exclusions, solver)
    reactions = [reaction for reaction in pruned.reactions if not reaction.boundary]
    if not reactions:
        return {"status": OPTIMAL, "objective": 0.0, "reactions": {}}
    problem = pruned.problem
    lp = problem.Model()
    lp.configuration = problem.Configuration.clone(
        config=pruned.solver.configuration, problem=lp
    )
    metabolites = sorted(
        {metabolite.id for reaction in reactions for metabolite in reaction.metabolites}
    )
    mass = {key: problem.Variable(f"m_{key}", lb=1) for key in metabolites}
    created = {r.id: problem.Variable(f"p_{r.id}", lb=0) for r in reactions}
    destroyed = {r.id: problem.Variable(f"n_{r.id}", lb=0) for r in reactions}
    lp.add([*mass.values(), *created.values(), *destroyed.values()])
    rows = {
        r.id: problem.Constraint(Zero, lb=0, ub=0, name=f"bal_{r.id}", sloppy=True)
        for r in reactions
    }
    lp.add(list(rows.values()), sloppy=True)
    lp.update()
    for reaction in reactions:
        terms = {
            mass[metabolite.id]: float(coefficient)
            for metabolite, coefficient in reaction.metabolites.items()
        }
        terms[created[reaction.id]] = -1.0
        terms[destroyed[reaction.id]] = 1.0
        rows[reaction.id].set_linear_coefficients(terms)
    lp.objective = problem.Objective(Zero, direction="min", sloppy=True)
    weights = {r.id: 1.0 if r.id in preferred else 1.0 + TIE_BREAK for r in reactions}
    lp.objective.set_linear_coefficients(
        {
            variable: weights[key]
            for side in (created, destroyed)
            for key, variable in side.items()
        }
    )
    status = lp.optimize()
    if status != OPTIMAL:
        return {"status": status, "objective": None, "reactions": {}}
    imbalance = {
        reaction.id: created[reaction.id].primal - destroyed[reaction.id].primal
        for reaction in reactions
    }
    return {
        "status": status,
        "objective": _round(lp.objective.value),
        "reactions": {
            key: _round(value)
            for key, value in sorted(imbalance.items())
            if abs(value) > 1e-7
        },
    }


def _stoichiometry(reaction: Any) -> dict[str, float]:
    return {
        metabolite.id: float(coefficient)
        for metabolite, coefficient in reaction.metabolites.items()
    }


def _same(left: Mapping[str, float], right: Mapping[str, float]) -> bool:
    return set(left) == set(right) and all(
        abs(left[key] - right[key]) <= TOLERANCE for key in left
    )


def reaction_origin(reaction: Any, input_model: Any | None) -> str | None:
    """Classify a reaction against the input model: added, changed or unchanged."""
    if input_model is None:
        return None
    try:
        original = input_model.reactions.get_by_id(reaction.id)
    except KeyError:
        return "added"
    return (
        "unchanged"
        if _same(_stoichiometry(reaction), _stoichiometry(original))
        else "changed"
    )


def fractional(stoichiometry: Mapping[str, float]) -> dict[str, float]:
    """Return the non-integer coefficients of a stoichiometry."""
    return {
        key: _round(value)
        for key, value in sorted(stoichiometry.items())
        if abs(value - round(value)) > 1e-6
    }


def _blamed_row(
    reaction: Any,
    imbalance: float,
    model: Any,
    input_model: Any | None,
    disagreeing: set[str],
    mislabelled: set[str] = frozenset(),
) -> dict[str, object]:
    stoichiometry = _stoichiometry(reaction)
    summary = reaction_summary(
        stoichiometry,
        model,
        input_model=input_model,
        reversible=bool(reaction.reversibility),
    )
    flags = _flags(summary, prefix="")
    odd = fractional(stoichiometry)
    if odd:
        flags.append("fractional-coefficients")
    mismatched = sorted(disagreeing & set(stoichiometry))
    if mismatched:
        flags.append("formula-disagreement")
    suspicious = sorted(mislabelled & set(stoichiometry))
    if suspicious:
        flags.append("possibly-mislabelled")
    return {
        "id": reaction.id,
        "imbalance": imbalance,
        "origin": reaction_origin(reaction, input_model),
        "equation_ids": summary["equation_ids"],
        "equation_names": summary["equation_names"],
        "elements": summary["elements"],
        "charge": summary["charge"],
        "fractional": odd,
        "formula_disagreement": mismatched,
        "mislabelled": suspicious,
        "flags": flags,
    }


def localize(
    model: Any,
    detection: Mapping[str, object],
    *,
    input_model: Any | None = None,
    input_detection: Mapping[str, object] | None = None,
    solver: str | None = None,
) -> dict[str, object]:
    """Blame reactions with one LP and flag what is chemically wrong with each.

    Each blamed reaction carries its element and charge balance, non-integer
    coefficients, metabolites whose formula or charge disagrees across
    compartments or with the input model, and possibly mislabelled
    metabolites (a name shared with a conflicting metabolite, or renamed from
    the input model to another compound's name). Flagged reactions come first: a
    blamed reaction with no flag is often an innocent member of a loop that the
    LP had to break somewhere. Unconserved metabolites already unconserved in
    the input model are listed as inherited.
    """
    from thg_protocol.validation import annotation_conflict, formula_disagreement

    unconserved = [str(item["id"]) for item in detection.get("unconserved", [])]
    inherited: list[str] = []
    if input_detection is not None:
        before = {str(item["id"]) for item in input_detection.get("unconserved", [])}
        inherited = [item for item in unconserved if item in before]
    new = [item for item in unconserved if item not in set(inherited)]
    exclusions = detection.get("excluded", {})
    blame = blame_reactions(
        model,
        exclusions=exclusions,
        prefer=chemically_suspect(model, exclusions),
        solver=solver,
    )
    disagreement = formula_disagreement(model, reference_model=input_model)
    disagreeing = set(disagreement["against_reference"]) | {
        key
        for group in disagreement["across_compartments"].values()
        for key in group["metabolites"]
    }
    labels = annotation_conflict(model, reference_model=input_model)
    mislabelled = set(labels["renamed_from_reference"]) | {
        key for group in labels["within_model"].values() for key in group["metabolites"]
    }
    rows = [
        _blamed_row(
            model.reactions.get_by_id(reaction_id),
            imbalance,
            model,
            input_model,
            disagreeing,
            mislabelled,
        )
        for reaction_id, imbalance in blame["reactions"].items()
    ]
    rows.sort(key=lambda row: (not row["flags"], -abs(row["imbalance"]), row["id"]))
    return {
        "unconserved": unconserved,
        "new": new,
        "inherited": inherited,
        "comparison": input_model is not None,
        "status": blame["status"],
        "objective": blame["objective"],
        "blamed": rows,
    }


# --------------------------------------------------------------------------
# Residuals and equations
# --------------------------------------------------------------------------


def _metabolite(model: Any, metabolite_id: str, input_model: Any | None) -> Any | None:
    for source in (model, input_model):
        if source is None:
            continue
        try:
            return source.metabolites.get_by_id(metabolite_id)
        except KeyError:
            continue
    return None


def element_residual(
    stoichiometry: Mapping[str, float],
    model: Any,
    *,
    input_model: Any | None = None,
    formulas: Mapping[str, str] | None = None,
) -> dict[str, object]:
    """Return products-minus-reactants element counts, or the formula gaps."""
    totals: dict[str, float] = defaultdict(float)
    missing = []
    for metabolite_id, coefficient in stoichiometry.items():
        formula = (formulas or {}).get(metabolite_id)
        if formula is None:
            metabolite = _metabolite(model, metabolite_id, input_model)
            formula = getattr(metabolite, "formula", None) or ""
        atoms = formula_atoms(formula)
        if not atoms:
            missing.append(metabolite_id)
            continue
        for element, count in atoms.items():
            totals[element] += float(coefficient) * count
    residual = {
        element: _round(value)
        for element, value in sorted(totals.items())
        if abs(value) > 1e-6
    }
    return {
        "residual": residual,
        "missing_formula": sorted(missing),
        "balanced": not missing and not residual,
    }


def charge_residual(
    stoichiometry: Mapping[str, float], model: Any, *, input_model: Any | None = None
) -> dict[str, object]:
    """Return the net charge of a stoichiometry, or the metabolites lacking one."""
    total = 0.0
    missing = []
    for metabolite_id, coefficient in stoichiometry.items():
        charge = getattr(_metabolite(model, metabolite_id, input_model), "charge", None)
        if charge is None:
            missing.append(metabolite_id)
        else:
            total += float(coefficient) * float(charge)
    residual = _round(total) if abs(total) > 1e-6 else 0
    return {
        "residual": residual,
        "missing_charge": sorted(missing),
        "balanced": not missing and residual == 0,
    }


def _format_side(items: list[tuple[str, float]]) -> str:
    return " + ".join(
        (f"{_round(abs(coefficient))} " if abs(coefficient) != 1 else "") + label
        for label, coefficient in items
    )


def equation(
    stoichiometry: Mapping[str, float],
    labels: Mapping[str, str] | None = None,
    *,
    reversible: bool = True,
) -> str:
    """Render ``reactants <=> products`` with IDs, or with ``labels`` if given."""
    labelled = [
        ((labels or {}).get(key, key), value)
        for key, value in sorted(stoichiometry.items())
    ]
    left = _format_side([item for item in labelled if item[1] < 0])
    right = _format_side([item for item in labelled if item[1] > 0])
    return f"{left} {'<=>' if reversible else '=>'} {right}".strip()


def reaction_summary(
    stoichiometry: Mapping[str, float],
    model: Any,
    *,
    input_model: Any | None = None,
    reversible: bool = True,
    formulas: Mapping[str, str] | None = None,
) -> dict[str, object]:
    """Equation (IDs and names), element balance and charge balance."""
    names = {
        key: getattr(_metabolite(model, key, input_model), "name", None) or key
        for key in stoichiometry
    }
    for key in stoichiometry:
        compartment = getattr(_metabolite(model, key, input_model), "compartment", None)
        if compartment:
            names[key] = f"{names[key]}[{compartment}]"
    return {
        "stoichiometry": {
            key: _round(value) for key, value in sorted(stoichiometry.items())
        },
        "equation_ids": equation(stoichiometry, reversible=reversible),
        "equation_names": equation(stoichiometry, names, reversible=reversible),
        "elements": element_residual(
            stoichiometry, model, input_model=input_model, formulas=formulas
        ),
        "charge": charge_residual(stoichiometry, model, input_model=input_model),
    }


def _input_reaction(input_model: Any | None, reaction_id: str) -> Any | None:
    if input_model is None:
        return None
    try:
        return input_model.reactions.get_by_id(reaction_id)
    except KeyError:
        return None


def _input_context(input_model: Any | None, reaction_id: str) -> dict[str, object]:
    original = _input_reaction(input_model, reaction_id)
    if input_model is None:
        return {"compared": False}
    if original is None:
        return {"compared": True, "present": False}
    return {
        "compared": True,
        "present": True,
        "equation_ids": equation(
            _stoichiometry(original), reversible=bool(original.reversibility)
        ),
    }


# --------------------------------------------------------------------------
# Step 3: propose
# --------------------------------------------------------------------------


def hill_formula(atoms: Mapping[str, int]) -> str:
    """Format element counts in Hill order (C, H, then alphabetical)."""
    counts = {key: int(value) for key, value in atoms.items() if int(value)}
    order = [key for key in ("C", "H") if key in counts] if "C" in counts else []
    order += sorted(key for key in counts if key not in order)
    return "".join(f"{key}{counts[key] if counts[key] != 1 else ''}" for key in order)


def infer_formula(
    model: Any, metabolite_id: str, *, exclusions: Mapping[str, str]
) -> str | None:
    """Return the single formula that balances every reaction of a metabolite.

    Every non-excluded internal reaction containing the metabolite must have
    formulas for all its other metabolites and must imply the same
    non-negative integer formula; otherwise ``None``.
    """
    metabolite = model.metabolites.get_by_id(metabolite_id)
    implied: set[tuple[tuple[str, int], ...]] = set()
    for reaction in metabolite.reactions:
        if reaction.boundary or reaction.id in exclusions:
            continue
        others = {
            key: value
            for key, value in _stoichiometry(reaction).items()
            if key != metabolite_id
        }
        balance = element_residual(others, model)
        if balance["missing_formula"]:
            return None
        coefficient = float(reaction.metabolites[metabolite])
        counts: dict[str, int] = {}
        for element, value in balance["residual"].items():
            count = -float(value) / coefficient
            if count < -1e-6 or abs(count - round(count)) > 1e-6:
                return None
            if round(count):
                counts[element] = int(round(count))
        implied.add(tuple(sorted(counts.items())))
    if len(implied) != 1:
        return None
    formula = hill_formula(dict(next(iter(implied))))
    return formula or None


def _by_name(model: Any) -> dict[tuple[str, str], Any]:
    result: dict[tuple[str, str], Any] = {}
    for metabolite in sorted(model.metabolites, key=lambda item: item.id):
        key = (getattr(metabolite, "name", "") or "", metabolite.compartment or "")
        result.setdefault(key, metabolite)
    return result


def _merge(
    stoichiometry: Mapping[str, float], addition: Mapping[str, float]
) -> dict[str, float]:
    merged = dict(stoichiometry)
    for key, value in addition.items():
        merged[key] = merged.get(key, 0.0) + value
    return {key: value for key, value in merged.items() if abs(value) > TOLERANCE}


def cofactor_candidates(
    reaction: Any, model: Any, *, names: Mapping[tuple[str, str], Any] | None = None
) -> list[dict[str, object]]:
    """Return cofactor additions whose element delta cancels the residual."""
    stoichiometry = _stoichiometry(reaction)
    balance = element_residual(stoichiometry, model)
    if balance["missing_formula"] or not balance["residual"]:
        return []
    target = {key: -float(value) for key, value in balance["residual"].items()}
    names = _by_name(model) if names is None else names
    compartments = sorted(
        {
            metabolite.compartment
            for metabolite in reaction.metabolites
            if metabolite.compartment
        }
    )
    candidates = []
    for compartment in compartments:
        for label, template in COFACTOR_FIXES:
            for sign in (1, -1):
                addition: dict[str, float] = {}
                for name, coefficient in template.items():
                    metabolite = names.get((name, compartment))
                    if metabolite is None:
                        break
                    addition[metabolite.id] = sign * float(coefficient)
                else:
                    delta = element_residual(addition, model)
                    if delta["missing_formula"]:
                        continue
                    if delta["residual"] == {
                        key: _round(value) for key, value in target.items()
                    }:
                        candidates.append(
                            {
                                "label": label if sign == 1 else f"{label} (reverse)",
                                "compartment": compartment,
                                "addition": addition,
                                "after": _merge(stoichiometry, addition),
                            }
                        )
    return candidates


def _flags(summary: Mapping[str, object], prefix: str = "after-") -> list[str]:
    flags = []
    elements = summary["elements"]
    charge = summary["charge"]
    if elements["residual"]:
        flags.append(f"{prefix}unbalanced-elements")
    if elements["missing_formula"]:
        flags.append(f"{prefix}missing-formula")
    if charge["residual"]:
        flags.append(f"{prefix}unbalanced-charge")
    if charge["missing_charge"]:
        flags.append(f"{prefix}missing-charge")
    return flags


def integer_candidates(
    reaction: Any, model: Any, *, limit: int = 6
) -> list[dict[str, float]]:
    """Round each non-integer coefficient down or up; keep element-balanced results.

    Fitted coefficients such as ``1.2 O2 -> 1.5 product`` usually stand for a
    small integer stoichiometry. Coefficients are never rounded to zero.
    Reactions with more than ``limit`` non-integer coefficients are skipped.
    """
    stoichiometry = _stoichiometry(reaction)
    odd = fractional(stoichiometry)
    if not odd or len(odd) > limit:
        return []
    choices = []
    for key in odd:
        value = stoichiometry[key]
        sizes = {math.floor(abs(value)), math.ceil(abs(value))} - {0}
        choices.append([math.copysign(size, value) for size in sorted(sizes)])
    candidates = []
    for combination in itertools.product(*choices):
        after = {**stoichiometry, **dict(zip(odd, combination, strict=True))}
        if element_residual(after, model)["balanced"]:
            candidates.append(
                {key: _round(value) for key, value in sorted(after.items())}
            )
    return candidates


def _proposal(
    *,
    operation: str,
    object_type: str,
    object_id: str,
    before: object,
    after: object,
    policy: str,
    confidence: str,
    evidence: Iterable[str],
    metadata: Mapping[str, object],
    status: str = "proposed",
    reason: str = "",
) -> Proposal:
    from thg_protocol.workflow.proposals import Proposal, proposal_id

    return Proposal(
        proposal_id=proposal_id(
            operation=operation,
            object_type=object_type,
            object_id=object_id,
            before=before,
            after=after,
        ),
        operation=operation,
        object_type=object_type,
        object_id=object_id,
        before=before,
        after=after,
        evidence=tuple(sorted(set(evidence))),
        confidence=confidence,
        policy=policy,
        stage=STAGE,
        status=status,
        reason=reason,
        metadata=dict(metadata),
    )


def _is_pseudo(reaction: Any) -> bool:
    return bool(
        _PSEUDO_PATTERN.search(reaction.id)
        or _PSEUDO_PATTERN.search(getattr(reaction, "name", "") or "")
    )


def propose_fixes(
    model: Any,
    localization: Mapping[str, object],
    *,
    exclusions: Mapping[str, str],
    input_model: Any | None = None,
) -> list[Proposal]:
    """Turn blamed reactions into fix proposals where a rule supports one.

    Rules, per blamed reaction: biomass/pool/lumped reactions are excluded; a
    reaction whose stoichiometry differs from the input model is restored;
    non-integer coefficients are rounded to the integer stoichiometries that
    balance the elements; an element residual matching a cofactor pair gets
    that pair (all fitting candidates when ambiguous). A formula-less added
    metabolite in a blamed reaction gets the one formula that balances all its
    reactions. A blamed reaction no rule covers yields an ``unresolved``
    removal proposal for manual curation. Each proposal records the blamed
    reactions it targets, so the re-check can tell whether it worked.
    """
    blamed = [row for row in localization.get("blamed", []) if row.get("id")]
    rows = {str(row["id"]): row for row in blamed}
    names = _by_name(model)
    proposals: list[Proposal] = []
    covered: set[str] = set()

    def evidence(reaction_ids: Iterable[str]) -> list[str]:
        return [
            f"blamed:{key} (imbalance {rows[key]['imbalance']:g})"
            for key in sorted(reaction_ids)
        ]

    def reaction_metadata(reaction: Any, after: Mapping[str, float] | None, rule: str):
        reversible = bool(reaction.reversibility)
        before_summary = reaction_summary(
            _stoichiometry(reaction),
            model,
            input_model=input_model,
            reversible=reversible,
        )
        after_summary = (
            reaction_summary(
                after, model, input_model=input_model, reversible=reversible
            )
            if after is not None
            else None
        )
        row = rows[reaction.id]
        return {
            "rule": rule,
            "reaction": {"before": before_summary, "after": after_summary},
            "input_model": _input_context(input_model, reaction.id),
            "origin": row.get("origin"),
            "imbalance": row.get("imbalance"),
            "blamed_flags": list(row.get("flags", [])),
            "targets": [reaction.id],
            "flags": _flags(after_summary) if after_summary else [],
        }

    def alternatives(group: list[Proposal]) -> list[Proposal]:
        ids = [item.proposal_id for item in group]
        for item in group:
            item.metadata["alternatives"] = [x for x in ids if x != item.proposal_id]
        return group

    for row in blamed:
        reaction = model.reactions.get_by_id(str(row["id"]))
        before = {k: _round(v) for k, v in sorted(_stoichiometry(reaction).items())}
        original = _input_reaction(input_model, reaction.id)
        group: list[Proposal] = []
        if _is_pseudo(reaction):
            group.append(
                _proposal(
                    operation="exclude-reaction",
                    object_type="reaction",
                    object_id=reaction.id,
                    before={"excluded": False},
                    after={"excluded": True},
                    policy="exclude-pseudo-reaction",
                    confidence="medium",
                    evidence=evidence([reaction.id]),
                    metadata=reaction_metadata(
                        reaction, None, "exclude-pseudo-reaction"
                    ),
                    reason="biomass, pool or lumped reaction; unbalanced by design",
                )
            )
        elif original is not None and row.get("origin") == "changed":
            after = {k: _round(v) for k, v in sorted(_stoichiometry(original).items())}
            metadata = reaction_metadata(reaction, after, "restore-input-stoichiometry")
            group.append(
                _proposal(
                    operation="set-stoichiometry",
                    object_type="reaction",
                    object_id=reaction.id,
                    before=before,
                    after=after,
                    policy="restore-input-stoichiometry",
                    confidence="medium" if metadata["flags"] else "high",
                    evidence=evidence([reaction.id]),
                    metadata=metadata,
                    reason="stoichiometry differs from the input model",
                )
            )
        else:
            candidates = integer_candidates(reaction, model)
            for after in candidates:
                metadata = reaction_metadata(reaction, after, "integer-stoichiometry")
                group.append(
                    _proposal(
                        operation="set-stoichiometry",
                        object_type="reaction",
                        object_id=reaction.id,
                        before=before,
                        after=after,
                        policy="integer-stoichiometry",
                        confidence="medium" if len(candidates) == 1 else "low",
                        evidence=evidence([reaction.id]),
                        metadata=metadata,
                        reason="non-integer coefficients; this integer "
                        "stoichiometry balances the elements",
                    )
                )
            if not group:
                cofactors = cofactor_candidates(reaction, model, names=names)
                for candidate in cofactors:
                    after = {
                        k: _round(v) for k, v in sorted(candidate["after"].items())
                    }
                    metadata = reaction_metadata(reaction, after, "cofactor-pair")
                    metadata["cofactor"] = candidate["label"]
                    metadata["compartment"] = candidate["compartment"]
                    group.append(
                        _proposal(
                            operation="set-stoichiometry",
                            object_type="reaction",
                            object_id=reaction.id,
                            before=before,
                            after=after,
                            policy="cofactor-pair",
                            confidence="medium" if len(cofactors) == 1 else "low",
                            evidence=evidence([reaction.id]),
                            metadata=metadata,
                            reason=f"element residual matches {candidate['label']}",
                        )
                    )
        if group:
            proposals.extend(alternatives(group))
            covered.add(reaction.id)

    # Formula-less metabolites in blamed reactions (only added ones with an input).
    seen: set[str] = set()
    for row in blamed:
        reaction = model.reactions.get_by_id(str(row["id"]))
        for metabolite in sorted(reaction.metabolites, key=lambda item: item.id):
            if metabolite.id in seen or formula_atoms(metabolite.formula or ""):
                continue
            seen.add(metabolite.id)
            if _metabolite(input_model, metabolite.id, None) is not None:
                continue
            formula = infer_formula(model, metabolite.id, exclusions=exclusions)
            if formula is None:
                continue
            targets = sorted(
                item.id for item in metabolite.reactions if item.id in rows
            )
            details = []
            for item in sorted(metabolite.reactions, key=lambda r: r.id):
                if item.boundary or item.id in exclusions:
                    continue
                stoichiometry = _stoichiometry(item)
                reversible = bool(item.reversibility)
                before_summary = reaction_summary(
                    stoichiometry, model, input_model=input_model, reversible=reversible
                )
                after_summary = reaction_summary(
                    stoichiometry,
                    model,
                    input_model=input_model,
                    reversible=reversible,
                    formulas={metabolite.id: formula},
                )
                details.append(
                    {
                        "id": item.id,
                        "before": before_summary,
                        "after": after_summary,
                        "input_model": _input_context(input_model, item.id),
                        "flags": _flags(after_summary),
                    }
                )
            flags = sorted({flag for item in details for flag in item["flags"]})
            proposals.append(
                _proposal(
                    operation="set-formula",
                    object_type="metabolite",
                    object_id=metabolite.id,
                    before=metabolite.formula or "",
                    after=formula,
                    policy="infer-formula",
                    confidence="medium" if flags else "high",
                    evidence=evidence(targets),
                    metadata={
                        "rule": "infer-formula",
                        "metabolite": _describe(metabolite),
                        "reactions": details,
                        "targets": targets,
                        "flags": flags,
                    },
                    reason="one formula balances all reactions of this metabolite",
                )
            )
            covered.update(targets)

    for row in blamed:
        if row["id"] in covered:
            continue
        reaction = model.reactions.get_by_id(str(row["id"]))
        proposals.append(
            _proposal(
                operation="remove-reaction",
                object_type="reaction",
                object_id=reaction.id,
                before={
                    k: _round(v) for k, v in sorted(_stoichiometry(reaction).items())
                },
                after=None,
                policy="unresolved",
                confidence="low",
                evidence=evidence([reaction.id]),
                metadata=reaction_metadata(reaction, None, "unresolved"),
                status="unresolved",
                reason="no rule applies; left for manual curation",
            )
        )
    unique: dict[str, Proposal] = {}
    for item in proposals:
        unique.setdefault(item.proposal_id, item)
    return list(unique.values())


# --------------------------------------------------------------------------
# Step 5: apply and re-check
# --------------------------------------------------------------------------


def apply_conservation_fixes(
    model: Any,
    proposals: Iterable[Proposal],
    decisions: Iterable[Decision] = (),
    *,
    input_model: Any | None = None,
) -> tuple[Any, tuple[Proposal, ...], tuple[dict[str, object], ...]]:
    """Apply approved or replaced proposals to a copy of ``model``.

    Returns the modified copy, the applied proposals and the ledger entries.
    The input model is never changed. Two applied fixes on the same object are
    rejected, since alternatives (e.g. NAD vs NADP) are mutually exclusive.
    """
    from thg_protocol.workflow.proposals import ProposalError, apply_proposals

    result = model.copy()
    targets: set[tuple[str, str]] = set()

    def apply(proposal: Proposal, value: object) -> None:
        key = (proposal.object_type, proposal.object_id)
        if key in targets:
            raise ProposalError(
                f"more than one approved fix for {proposal.object_type} "
                f"{proposal.object_id}"
            )
        targets.add(key)
        if proposal.operation == "set-formula":
            if not isinstance(value, str) or not formula_atoms(value):
                raise ProposalError(
                    f"invalid formula for {proposal.object_id}: {value!r}"
                )
            result.metabolites.get_by_id(proposal.object_id).formula = value
            return
        reaction = result.reactions.get_by_id(proposal.object_id)
        if proposal.operation == "exclude-reaction":
            reaction.notes[EXCLUSION_NOTE] = proposal.proposal_id
        elif proposal.operation == "remove-reaction":
            result.remove_reactions([reaction])
        elif proposal.operation == "set-stoichiometry":
            if not isinstance(value, Mapping) or not value:
                raise ProposalError(
                    f"stoichiometry for {proposal.object_id} must be a non-empty object"
                )
            new: dict[Any, float] = {}
            for metabolite_id, coefficient in value.items():
                try:
                    metabolite = result.metabolites.get_by_id(metabolite_id)
                except KeyError:
                    source = _metabolite(input_model, str(metabolite_id), None)
                    if source is None:
                        raise ProposalError(
                            f"unknown metabolite in fix for {proposal.object_id}: "
                            f"{metabolite_id}"
                        ) from None
                    metabolite = source.copy()
                    result.add_metabolites([metabolite])
                new[metabolite] = float(coefficient)
            reaction.subtract_metabolites(dict(reaction.metabolites), combine=True)
            reaction.add_metabolites(new)
        else:
            raise ProposalError(f"unknown conservation operation: {proposal.operation}")

    applied, ledger = apply_proposals(
        proposals, mode="user-approved-only", decisions=decisions, apply=apply
    )
    return result, applied, ledger


def compare_detections(
    before: Mapping[str, object],
    after: Mapping[str, object],
    applied: Iterable[Proposal] = (),
    still_blamed: Iterable[str] = (),
) -> dict[str, object]:
    """Report unconserved metabolites before and after, and ineffective fixes.

    A fix is ineffective when a reaction it targets is still blamed by
    ``blame_reactions`` on the fixed model.
    """
    before_ids = {str(item["id"]) for item in before.get("unconserved", [])}
    after_ids = {str(item["id"]) for item in after.get("unconserved", [])}
    resolved = before_ids - after_ids
    remaining = set(still_blamed)
    ineffective = [
        item.proposal_id
        for item in applied
        if set(item.metadata.get("targets", [])) & remaining
    ]
    return {
        "before": sorted(before_ids),
        "after": sorted(after_ids),
        "resolved": sorted(resolved),
        "introduced": sorted(after_ids - before_ids),
        "ineffective_fixes": ineffective,
        "consistent": not after_ids,
    }


__all__ = [
    "BIOMASS_SBO",
    "COFACTOR_FIXES",
    "EXCLUSION_NOTE",
    "PSEUDO_SUBSYSTEMS",
    "TIE_BREAK",
    "apply_conservation_fixes",
    "blame_reactions",
    "charge_residual",
    "chemically_suspect",
    "cofactor_candidates",
    "compare_detections",
    "conservation_exclusions",
    "element_residual",
    "equation",
    "find_unconserved_metabolites",
    "fractional",
    "hill_formula",
    "infer_formula",
    "integer_candidates",
    "localize",
    "propose_fixes",
    "reaction_origin",
    "reaction_summary",
]
