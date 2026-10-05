"""Fix proposals and a lookup index for the validation report.

Runs after the checks: each failed check whose problems a rule can fix gets
proposals from ``analysis.conservation`` (the same records the conservation
workflow writes), and the report gets the reactions and metabolites the checks
mention so it can show them on demand. Nothing here changes the model.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

#: Checks whose unbalanced or odd reactions get the per-reaction fix rules.
_REACTION_CHECKS = {
    "mass-balance": lambda details: details.get("unbalanced", []),
    "charge-balance": lambda details: details.get("unbalanced", []),
    "fractional-coefficients": lambda details: list(details.get("reactions", {})),
    "unusual-protons": lambda details: list(details.get("reactions", {})),
}
#: Detail keys that list every reaction, not only the problems.
_UNINDEXED = {"statuses", "excluded"}
#: Reactions listed per metabolite in the index.
_REACTIONS_PER_METABOLITE = 40


def _failed(check: Mapping[str, object]) -> bool:
    return check.get("passed") is False and isinstance(check.get("details"), Mapping)


def _blamed_rows(localization: Mapping[str, object]) -> list[dict[str, object]]:
    rows = []
    for row in localization.get("blamed", []):
        rows.append(
            {
                "id": row["id"],
                "origin": row.get("origin") or "-",
                "imbalance": row.get("imbalance"),
                "flags": list(row.get("flags", [])),
                "equation": row.get("equation_ids"),
            }
        )
    return rows


def collect_fixes(
    model: Any,
    checks: list[dict[str, object]],
    *,
    reference_model: Any | None = None,
) -> list[dict[str, object]]:
    """Return fix proposals for the failed checks, as report records.

    Each record is ``Proposal.to_dict()`` plus ``checks``, the IDs of the
    checks that produced it. A fix produced by several checks (same operation,
    object, before and after) is one record. The stoichiometric-consistency
    check's details gain the blamed reactions, split by chemical flag.
    """
    from thg_protocol.analysis import conservation

    by_id: dict[str, dict[str, object]] = {}

    def add(check_id: str, proposals: Iterable[Any]) -> None:
        for proposal in proposals:
            record = by_id.get(proposal.proposal_id)
            if record is None:
                record = proposal.to_dict()
                record["checks"] = []
                by_id[proposal.proposal_id] = record
            else:
                record["evidence"] = sorted(
                    set(record["evidence"]) | set(proposal.evidence)
                )
            if check_id not in record["checks"]:
                record["checks"].append(check_id)

    names = None
    for check in checks:
        if not _failed(check):
            continue
        check_id = str(check["id"])
        details = check["details"]
        if check_id == "stoichiometric-consistency":
            if not isinstance(details.get("unconserved"), list):
                continue
            localization = conservation.localize(
                model, details, input_model=reference_model
            )
            rows = _blamed_rows(localization)
            details["blamed_with_flag"] = [row for row in rows if row["flags"]]
            details["blamed_without_flag"] = [row for row in rows if not row["flags"]]
            add(
                check_id,
                conservation.propose_fixes(
                    model,
                    localization,
                    exclusions=details.get("excluded", {}),
                    input_model=reference_model,
                ),
            )
        elif check_id == "formula-disagreement":
            add(
                check_id,
                conservation.formula_fixes(
                    model, details, reference_model=reference_model
                ),
            )
        elif check_id in _REACTION_CHECKS:
            if names is None:
                names = conservation._by_name(model)
            for reaction_id in _REACTION_CHECKS[check_id](details):
                try:
                    reaction = model.reactions.get_by_id(str(reaction_id))
                except KeyError:
                    continue
                add(
                    check_id,
                    conservation.reaction_fixes(
                        reaction,
                        model,
                        input_model=reference_model,
                        names=names,
                        evidence=[f"{check_id}:{reaction.id}"],
                        exclude_pseudo=False,
                    ),
                )
    return sorted(
        by_id.values(), key=lambda item: (item["object_id"], item["proposal_id"])
    )


def _strings(value: object) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, Mapping):
        for key, item in value.items():
            if key in _UNINDEXED:
                continue
            yield str(key)
            yield from _strings(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _strings(item)


def _subsystem(reaction: Any) -> str:
    value = getattr(reaction, "subsystem", "") or ""
    if isinstance(value, (list, tuple)):
        return "; ".join(map(str, value))
    return str(value)


def build_index(
    model: Any,
    checks: Iterable[Mapping[str, object]],
    proposals: Iterable[Mapping[str, object]] = (),
) -> dict[str, dict[str, object]]:
    """Return the reactions and metabolites the checks and proposals mention.

    Reactions carry their equation (IDs and names), subsystem and bounds;
    metabolites their name, formula, charge, compartment and up to
    ``_REACTIONS_PER_METABOLITE`` reactions, which are indexed too.
    """
    reaction_ids = {reaction.id for reaction in model.reactions}
    metabolite_ids = {metabolite.id for metabolite in model.metabolites}
    mentioned = set()
    for check in checks:
        mentioned.update(_strings(check.get("details")))
    for proposal in proposals:
        mentioned.add(str(proposal.get("object_id")))
        for key in ("before", "after"):
            value = proposal.get(key)
            if isinstance(value, Mapping):
                mentioned.update(map(str, value))
    metabolites: dict[str, object] = {}
    wanted_reactions = mentioned & reaction_ids
    for metabolite_id in sorted(mentioned & metabolite_ids):
        metabolite = model.metabolites.get_by_id(metabolite_id)
        reactions = sorted(reaction.id for reaction in metabolite.reactions)
        wanted_reactions.update(reactions[:_REACTIONS_PER_METABOLITE])
        metabolites[metabolite_id] = {
            "name": metabolite.name or "",
            "formula": metabolite.formula or None,
            "charge": metabolite.charge,
            "compartment": metabolite.compartment,
            "reactions": reactions[:_REACTIONS_PER_METABOLITE],
            "reaction_count": len(reactions),
        }
    reactions: dict[str, object] = {}
    for reaction_id in sorted(wanted_reactions):
        reaction = model.reactions.get_by_id(reaction_id)
        reactions[reaction_id] = {
            "name": reaction.name or "",
            "equation": reaction.build_reaction_string(),
            "equation_names": reaction.build_reaction_string(use_metabolite_names=True),
            "subsystem": _subsystem(reaction),
            "bounds": [reaction.lower_bound, reaction.upper_bound],
        }
    return {"reactions": reactions, "metabolites": metabolites}


__all__ = ["build_index", "collect_fixes"]
