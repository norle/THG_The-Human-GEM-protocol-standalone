"""Optional network-reaction compaction helpers."""

from __future__ import annotations

from collections import defaultdict
from typing import Any


def _scratch_copy(model: Any) -> Any:
    """Copy a model onto GLPK for structural edits that never solve.

    ``Model.copy`` rebuilds the whole solver problem; with Gurobi that goes
    through sympy and takes minutes on a genome-scale model.
    """
    import copy

    from cobra import Model

    result = Model(model.id)
    result.solver = "glpk"
    result.add_metabolites([metabolite.copy() for metabolite in model.metabolites])
    reactions = []
    for reaction in model.reactions:
        clone = reaction.copy()
        clone.annotation = copy.deepcopy(reaction.annotation)
        reactions.append(clone)
    result.add_reactions(reactions)
    result.objective = {
        result.reactions.get_by_id(reaction.id): reaction.objective_coefficient
        for reaction in model.reactions
        if reaction.objective_coefficient
    }
    return result


def are_reactions_proportional(
    reaction1: Any, reaction2: Any, *, tolerance: float = 1e-9
) -> tuple[bool, float, bool]:
    """Compare two reactions by stoichiometry, including reversal."""
    first = {
        getattr(metabolite, "id", metabolite): value
        for metabolite, value in reaction1.metabolites.items()
    }
    second = {
        getattr(metabolite, "id", metabolite): value
        for metabolite, value in reaction2.metabolites.items()
    }
    if set(first) != set(second) or not first:
        return False, 0.0, False
    ratios = []
    for metabolite in first:
        left, right = first[metabolite], second[metabolite]
        if abs(left) <= tolerance:
            if abs(right) > tolerance:
                return False, 0.0, False
            continue
        ratios.append(right / left)
    if not ratios or any(abs(value - ratios[0]) > tolerance for value in ratios[1:]):
        return False, 0.0, False
    return True, ratios[0], ratios[0] < 0


def combine_identical_reactions(
    model: Any, non_comp_id: set[str] | None = None
) -> tuple[Any, list[Any]]:
    """Return a copy with proportional non-boundary reactions combined."""
    result = model.copy()
    removed = _combine_parallel(result, set(non_comp_id or ()))
    return result, removed


def _members(reaction: Any) -> list[str]:
    return list(reaction.annotation.get("compaction_members", [reaction.id]))


def _combine_parallel(
    result: Any, excluded: set[str], *, same_direction_only: bool = False
) -> list[Any]:
    """Merge parallel capacities in place, including reversed stoichiometry."""
    removed: list[Any] = []
    groups: dict[frozenset[str], list[Any]] = defaultdict(list)
    for reaction in result.reactions:
        if reaction.id not in excluded and not reaction.boundary:
            groups[frozenset(met.id for met in reaction.metabolites)].append(reaction)
    for reactions in groups.values():
        # Retain one reversible path per proportional family to expose cycles.
        reserved: list[Any] = []
        if same_direction_only:
            for reaction in reactions:
                if reaction.reversibility and not any(
                    are_reactions_proportional(reaction, held)[0] for held in reserved
                ):
                    reserved.append(reaction)
        for index, base in enumerate(reactions):
            if base in reserved or not result.reactions.has_id(base.id):
                continue
            for candidate in reactions[index + 1 :]:
                if (
                    candidate.id in excluded
                    or candidate in reserved
                    or candidate.boundary
                    or not result.reactions.has_id(candidate.id)
                ):
                    continue
                proportional, factor, _ = are_reactions_proportional(base, candidate)
                if not proportional:
                    continue
                if (
                    same_direction_only
                    and factor < 0
                    and not any(
                        are_reactions_proportional(base, held)[0] for held in reserved
                    )
                ):
                    continue
                if base.gene_reaction_rule and candidate.gene_reaction_rule:
                    base.gene_reaction_rule = (
                        f"({base.gene_reaction_rule}) or "
                        f"({candidate.gene_reaction_rule})"
                    )
                elif candidate.gene_reaction_rule:
                    base.gene_reaction_rule = candidate.gene_reaction_rule
                lower, upper = sorted(bound * factor for bound in candidate.bounds)
                base.bounds = (base.lower_bound + lower, base.upper_bound + upper)
                base.annotation["compaction_members"] = sorted(
                    set(_members(base)) | set(_members(candidate))
                )
                removed.append(candidate.copy())
                result.remove_reactions([candidate])
    return removed


def _combine_linear(model: Any, excluded: set[str], tolerance: float) -> list[Any]:
    loops: list[Any] = []
    while True:
        changed = False
        for metabolite in list(model.metabolites):
            reactions = sorted(metabolite.reactions, key=lambda rxn: rxn.id)
            if len(reactions) != 2 or any(rxn.id in excluded for rxn in reactions):
                continue
            base, other = reactions
            # base + scale * other cancels the shared intermediate.
            scale = -base.metabolites[metabolite] / other.metabolites[metabolite]
            lower, upper = sorted(bound / scale for bound in other.bounds)
            bounds = (max(base.lower_bound, lower), min(base.upper_bound, upper))
            if bounds[0] > bounds[1] or max(abs(x) for x in bounds) <= tolerance:
                continue
            members = sorted(set(_members(base)) | set(_members(other)))
            base.add_metabolites(
                {
                    met: coefficient * scale
                    for met, coefficient in other.metabolites.items()
                }
            )
            base.add_metabolites(
                {
                    met: -value
                    for met, value in base.metabolites.items()
                    if abs(value) <= tolerance
                }
            )
            base.bounds = bounds
            rules = [
                rxn.gene_reaction_rule
                for rxn in (base, other)
                if rxn.gene_reaction_rule
            ]
            base.gene_reaction_rule = " and ".join(f"({rule})" for rule in rules)
            base.annotation["compaction_members"] = members
            model.remove_reactions([other])
            if not base.metabolites:
                loops.append(base.copy())
                model.remove_reactions([base])
            changed = True
        if not changed:
            return loops


def full_compaction(
    model: Any,
    *,
    non_comp_id: set[str] | None = None,
    no_blocked_reactions: bool = True,
    tolerance: float = 1e-9,
) -> tuple[Any, list[Any]]:
    """Collapse linear/parallel pathways and return empty loop reactions.

    Blocked-reaction filtering is solver-dependent and imported only when
    explicitly requested. The default operation is deterministic and offline.
    """
    result = _scratch_copy(model)
    if not no_blocked_reactions:
        try:
            from cobra.flux_analysis import find_blocked_reactions

            result.remove_reactions(find_blocked_reactions(result))
        except ImportError as error:  # pragma: no cover - optional COBRA path
            raise RuntimeError("blocked-reaction filtering requires COBRA") from error
    excluded = set(non_comp_id or ()) | {rxn.id for rxn in result.boundary}
    excluded.update(rxn.id for rxn in result.reactions if rxn.objective_coefficient)
    for reaction in result.reactions:
        if reaction.id not in excluded and reaction.upper_bound <= 0:
            reaction *= -1
    loops: list[Any] = []
    while True:
        count = len(result.reactions)
        loops.extend(_combine_linear(result, excluded, tolerance))
        # Keep opposing paths separate so the next linear pass can expose a loop.
        _combine_parallel(result, excluded, same_direction_only=True)
        if len(result.reactions) == count:
            break
    return result, loops


def detect_infeasible_loops(
    model: Any, *, blocked_reactions: list[str] | None = None
) -> dict[str, object]:
    """Identify obligatory loops on a copy; this is not exhaustive loop detection."""
    if blocked_reactions is None:
        from cobra.flux_analysis import find_blocked_reactions

        blocked_reactions = find_blocked_reactions(model)
    working = _scratch_copy(model)
    for reaction in working.reactions:
        reaction.annotation["compaction_members"] = [reaction.id]
        # Merging concatenates GPRs, which cobra re-parses on every edit; the
        # rules grow without bound and detection only needs reaction members.
        reaction.gene_reaction_rule = ""
    working.remove_reactions(blocked_reactions)
    _, collapsed = full_compaction(working)
    loops = sorted(_members(rxn) for rxn in collapsed)
    reactions = sorted({identifier for loop in loops for identifier in loop})
    return {
        "method": "linear-parallel-compaction",
        "scope": "obligatory loops; not exhaustive",
        "loops": loops,
        "reactions": reactions,
        "blocked_reactions_excluded": sorted(blocked_reactions),
        "passed": not loops,
    }


def remove_infeasible_loops(
    model: Any, *, stage: str = "loop-removal"
) -> tuple[Any, dict[str, object], list[dict[str, object]]]:
    """Remove only detected original reactions, returning auditable ledger entries."""
    from thg_protocol.workflow.proposals import Proposal, apply_proposals, proposal_id

    report = detect_infeasible_loops(model)
    result = model.copy()
    proposals = []
    for identifier in report["reactions"]:
        reaction = model.reactions.get_by_id(identifier)
        before = {
            "name": reaction.name,
            "subsystem": reaction.subsystem,
            "annotation": reaction.annotation,
            "stoichiometry": {
                met.id: value for met, value in reaction.metabolites.items()
            },
            "bounds": list(reaction.bounds),
            "gpr": reaction.gene_reaction_rule,
        }
        proposals.append(
            Proposal(
                proposal_id=proposal_id(
                    operation="remove-reaction",
                    object_type="reaction",
                    object_id=identifier,
                    before=before,
                    after=None,
                ),
                operation="remove-reaction",
                object_type="reaction",
                object_id=identifier,
                before=before,
                after=None,
                evidence=("obligatory-loops",),
                confidence="structural",
                policy="explicit-loop-removal",
                stage=stage,
                reason="Obligatory loop identified by compaction",
                metadata={
                    "loops": [loop for loop in report["loops"] if identifier in loop]
                },
            )
        )
    _, ledger = apply_proposals(
        proposals,
        apply=lambda proposal, _: result.remove_reactions([proposal.object_id]),
    )
    return result, report, list(ledger)


__all__ = [
    "are_reactions_proportional",
    "combine_identical_reactions",
    "full_compaction",
    "detect_infeasible_loops",
    "remove_infeasible_loops",
]
