"""Explicit, non-mutating model merge workflow."""

from __future__ import annotations

import copy
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class MergeReport:
    """Counts and output metadata produced by
    [`merge_models`][thg_protocol.merge.merge_models]."""

    added_metabolites: int
    added_reactions: int
    overlapping_metabolites: int
    overlapping_reactions: int
    removed_isolated_metabolites: int
    output_path: Path | None = None


@dataclass(frozen=True)
class MergeDecision:
    """A deterministic decision for one semantic merge conflict."""

    category: str
    left_id: str
    right_id: str
    action: str
    reason: str = ""


@dataclass(frozen=True)
class MergePolicy:
    """Explicit policies controlling semantic merge decisions."""

    source_precedence: str = "base"
    direction: str = "strict"
    proton_water: str = "strict"
    formula_charge: str = "report"
    bounds: str = "report"
    gpr: str = "report"

    def __post_init__(self) -> None:
        choices = {
            "source_precedence": {"base", "incoming"},
            "direction": {"strict", "allow-reversal"},
            "proton_water": {"strict", "ignore"},
            "formula_charge": {"report", "base", "incoming"},
            "bounds": {"report", "base", "incoming"},
            "gpr": {"report", "base", "incoming"},
        }
        for name, allowed in choices.items():
            if getattr(self, name) not in allowed:
                raise ValueError(f"{name} must be one of {sorted(allowed)}")


@dataclass(frozen=True)
class MergePlan:
    """Complete plan emitted before a merge mutates a copied model."""

    metabolite_map: dict[str, str]
    gene_map: dict[str, str]
    reaction_map: dict[str, str]
    decisions: tuple[MergeDecision, ...]
    policy: MergePolicy = MergePolicy()

    def to_dict(self) -> dict[str, object]:
        return {
            "metabolite_map": dict(sorted(self.metabolite_map.items())),
            "gene_map": dict(sorted(self.gene_map.items())),
            "reaction_map": dict(sorted(self.reaction_map.items())),
            "policy": copy.deepcopy(self.policy.__dict__),
            "decisions": [
                copy.deepcopy(decision.__dict__) for decision in self.decisions
            ],
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> MergePlan:
        policy = payload.get("policy", {})
        decisions = payload.get("decisions", ())
        if not isinstance(policy, Mapping) or not isinstance(decisions, (list, tuple)):
            raise ValueError("invalid merge plan payload")
        return cls(
            {
                str(key): str(value)
                for key, value in dict(payload.get("metabolite_map", {})).items()
            },
            {
                str(key): str(value)
                for key, value in dict(payload.get("gene_map", {})).items()
            },
            {
                str(key): str(value)
                for key, value in dict(payload.get("reaction_map", {})).items()
            },
            tuple(
                MergeDecision(**dict(item))
                for item in decisions
                if isinstance(item, Mapping)
            ),
            MergePolicy(**dict(policy)),
        )


def _reaction_signature(
    reaction: Any,
    metabolite_map: dict[str, str],
    *,
    ignored_species: frozenset[str] = frozenset(),
) -> tuple[tuple[str, float], ...]:
    return tuple(
        sorted(
            (
                metabolite_map.get(metabolite.id, metabolite.id),
                round(float(coefficient), 12),
            )
            for metabolite, coefficient in reaction.metabolites.items()
            if metabolite.id.lower().rsplit("_", 1)[0] not in ignored_species
        )
    )


def _reverse_signature(
    signature: tuple[tuple[str, float], ...],
) -> tuple[tuple[str, float], ...]:
    return tuple(
        sorted((identifier, -coefficient) for identifier, coefficient in signature)
    )


def generate_merge_plan(
    base_model: Any,
    incoming_model: Any,
    *,
    policy: MergePolicy | None = None,
) -> MergePlan:
    """Generate conservative, compartment-aware equivalence proposals.

    Cross-model identity uses explicit annotation identifiers when present;
    names and chemistry alone never create an equivalence.  Ambiguous matches
    are recorded as unresolved decisions.
    """

    policy = policy or MergePolicy()

    def index(objects: Any, annotation_keys: tuple[str, ...]) -> dict[str, list[str]]:
        result: dict[str, list[str]] = {}
        for item in objects:
            for key in annotation_keys:
                value = item.annotation.get(key)
                values = value if isinstance(value, list) else [value]
                for identifier in values:
                    if identifier:
                        result.setdefault(f"{key}:{identifier}", []).append(item.id)
        return result

    left = index(base_model.metabolites, ("kegg.compound", "chebi", "hmdb", "inchikey"))
    right = index(
        incoming_model.metabolites, ("kegg.compound", "chebi", "hmdb", "inchikey")
    )
    metabolite_map: dict[str, str] = {}
    decisions: list[MergeDecision] = []
    for token in sorted(set(left) & set(right)):
        targets = sorted(set(left[token]))
        candidates = sorted(set(right[token]))
        if len(targets) == len(candidates) == 1:
            target, source = targets[0], candidates[0]
            left_obj = base_model.metabolites.get_by_id(target)
            right_obj = incoming_model.metabolites.get_by_id(source)
            if left_obj.compartment == right_obj.compartment:
                metabolite_map[source] = target
                decisions.append(
                    MergeDecision(
                        "metabolite-equivalence", target, source, "map", token
                    )
                )
            else:
                decisions.append(
                    MergeDecision(
                        "compartment-conflict", target, source, "unresolved", token
                    )
                )
        else:
            decisions.append(
                MergeDecision(
                    "ambiguous-metabolite",
                    ",".join(targets),
                    ",".join(candidates),
                    "unresolved",
                    token,
                )
            )
    gene_map = {
        gene.id: gene.id
        for gene in incoming_model.genes
        if base_model.genes.has_id(gene.id)
    }
    reaction_map = {
        reaction.id: reaction.id
        for reaction in incoming_model.reactions
        if base_model.reactions.has_id(reaction.id)
    }
    # Reaction IDs are strongest.  For distinct IDs, explicit reaction
    # annotations can establish equivalence only after metabolite mapping.
    reaction_tokens: dict[str, list[str]] = {}
    for reaction in incoming_model.reactions:
        for key in ("kegg.reaction", "ec-code", "bigg.reaction"):
            value = reaction.annotation.get(key)
            values = value if isinstance(value, list) else [value]
            for identifier in values:
                if identifier:
                    reaction_tokens.setdefault(f"{key}:{identifier}", []).append(
                        reaction.id
                    )
    base_tokens: dict[str, list[str]] = {}
    for reaction in base_model.reactions:
        for key in ("kegg.reaction", "ec-code", "bigg.reaction"):
            value = reaction.annotation.get(key)
            values = value if isinstance(value, list) else [value]
            for identifier in values:
                if identifier:
                    base_tokens.setdefault(f"{key}:{identifier}", []).append(
                        reaction.id
                    )
    for token in sorted(set(reaction_tokens) & set(base_tokens)):
        sources, targets = (
            sorted(set(reaction_tokens[token])),
            sorted(set(base_tokens[token])),
        )
        if len(sources) == len(targets) == 1 and sources[0] not in reaction_map:
            source, target = sources[0], targets[0]
            ignored_species = (
                frozenset({"h", "h2o", "proton", "water"})
                if policy.proton_water == "ignore"
                else frozenset()
            )
            incoming_signature = _reaction_signature(
                incoming_model.reactions.get_by_id(source),
                metabolite_map,
                ignored_species=ignored_species,
            )
            base_signature = _reaction_signature(
                base_model.reactions.get_by_id(target),
                {},
                ignored_species=ignored_species,
            )
            if incoming_signature == base_signature:
                reaction_map[source] = target
                decisions.append(
                    MergeDecision("reaction-equivalence", target, source, "map", token)
                )
            elif incoming_signature == _reverse_signature(base_signature):
                action = "map" if policy.direction == "allow-reversal" else "unresolved"
                if action == "map":
                    reaction_map[source] = target
                decisions.append(
                    MergeDecision("direction-conflict", target, source, action, token)
                )
            else:
                decisions.append(
                    MergeDecision(
                        "reaction-stoichiometry-conflict",
                        target,
                        source,
                        "unresolved",
                        token,
                    )
                )
    decisions.extend(
        MergeDecision(
            "gene-equivalence", identifier, identifier, "map", "explicit identifier"
        )
        for identifier in sorted(gene_map)
    )
    decisions.extend(
        MergeDecision(
            "reaction-equivalence", identifier, identifier, "map", "explicit identifier"
        )
        for identifier in sorted(reaction_map)
    )
    common_reaction_ids = sorted(
        {item.id for item in base_model.reactions}
        & {item.id for item in incoming_model.reactions}
    )
    for identifier in common_reaction_ids:
        base_reaction = base_model.reactions.get_by_id(identifier)
        incoming_reaction = incoming_model.reactions.get_by_id(identifier)
        if base_reaction.bounds != incoming_reaction.bounds:
            decisions.append(
                MergeDecision(
                    "bounds-conflict",
                    identifier,
                    identifier,
                    policy.bounds,
                    "bounds differ",
                )
            )
        if base_reaction.gene_reaction_rule != incoming_reaction.gene_reaction_rule:
            decisions.append(
                MergeDecision(
                    "gpr-conflict",
                    identifier,
                    identifier,
                    policy.gpr,
                    "GPR differs",
                )
            )
        for field in ("formula", "charge"):
            base_values = {getattr(item, field) for item in base_reaction.metabolites}
            incoming_values = {
                getattr(item, field) for item in incoming_reaction.metabolites
            }
            if base_values != incoming_values:
                decisions.append(
                    MergeDecision(
                        f"{field}-conflict",
                        identifier,
                        identifier,
                        policy.formula_charge,
                        f"{field} differs",
                    )
                )
    return MergePlan(metabolite_map, gene_map, reaction_map, tuple(decisions), policy)


def apply_merge_plan(
    base_model: Any,
    incoming_model: Any,
    plan: MergePlan,
    *,
    output_path: str | Path | None = None,
) -> tuple[Any, MergeReport]:
    """Apply a reviewed plan to a copied model, preserving old merge behavior."""
    incoming = incoming_model.copy()
    for source, target in sorted(plan.metabolite_map.items()):
        if incoming.metabolites.has_id(source) and not incoming.metabolites.has_id(
            target
        ):
            incoming.metabolites.get_by_id(source).id = target
    for source, target in sorted(plan.reaction_map.items()):
        if incoming.reactions.has_id(source) and not incoming.reactions.has_id(target):
            incoming.reactions.get_by_id(source).id = target
    merged, report = merge_models(
        base_model,
        incoming,
        output_path=output_path,
        source_precedence=plan.policy.source_precedence,
        provenance=True,
    )

    # ``MergePolicy`` controls each conflict family independently.  The
    # low-level merge function intentionally exposes only a broad source
    # precedence switch, so apply the reviewed structural decisions here
    # after the copied merge has been constructed.
    for incoming_metabolite in incoming.metabolites:
        identifier = incoming_metabolite.id
        if not merged.metabolites.has_id(identifier):
            continue
        target = merged.metabolites.get_by_id(identifier)
        base = (
            base_model.metabolites.get_by_id(identifier)
            if base_model.metabolites.has_id(identifier)
            else None
        )
        if base is None:
            continue
        if plan.policy.formula_charge == "incoming":
            if incoming_metabolite.formula is not None:
                target.formula = incoming_metabolite.formula
            if incoming_metabolite.charge is not None:
                target.charge = incoming_metabolite.charge
        else:
            # ``base`` and ``report`` both retain the reviewed base value;
            # ``report`` records the conflict without silently choosing it.
            target.formula = base.formula
            target.charge = base.charge

    for incoming_reaction in incoming.reactions:
        identifier = incoming_reaction.id
        if not merged.reactions.has_id(identifier):
            continue
        target = merged.reactions.get_by_id(identifier)
        base = (
            base_model.reactions.get_by_id(identifier)
            if base_model.reactions.has_id(identifier)
            else None
        )
        if base is None:
            continue
        if plan.policy.bounds == "incoming":
            target.bounds = incoming_reaction.bounds
        else:
            target.bounds = base.bounds
        if plan.policy.gpr == "incoming":
            target.gene_reaction_rule = incoming_reaction.gene_reaction_rule
        else:
            target.gene_reaction_rule = base.gene_reaction_rule

    if output_path is not None:
        _write_model(merged, Path(output_path))
    return merged, report


def validate_merged_model(
    model: Any,
    *,
    profile: str = "final-standard",
    task_suite: Any | None = None,
) -> dict[str, object]:
    """Run the maintained validation profile and optional versioned task suite."""
    from thg_protocol.validation import validate_model

    report: dict[str, object] = {"validation": validate_model(model, profile)}
    if task_suite is None:
        from thg_protocol.tasks import TaskSuite

        task_suite = TaskSuite("final-thg-empty", "1", ())
    from thg_protocol.tasks import run_task_suite

    report["tasks"] = run_task_suite(model, task_suite)
    return report


def _merge_annotation(target: Any, source: Any) -> None:
    """Copy non-empty incoming annotations without sharing mutable values."""
    for key, value in source.annotation.items():
        if value not in (None, "", [], {}, ()):
            target.annotation[key] = copy.deepcopy(value)


def _write_model(model: Any, output_path: Path) -> None:
    from cobra.io import save_json_model, write_sbml_model

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.suffix.lower() == ".json":
        save_json_model(model, str(output_path))
    else:
        write_sbml_model(model, str(output_path))


def merge_models(
    base_model: Any,
    incoming_model: Any,
    *,
    output_path: str | Path | None = None,
    remove_isolated_metabolites: bool = False,
    source_precedence: str = "base",
    provenance: bool = False,
) -> tuple[Any, MergeReport]:
    """Merge ``incoming_model`` into a copy of ``base_model``.

    Existing objects retain their stoichiometry and bounds; incoming names,
    non-empty annotations, and missing GPRs enrich overlaps. New reactions
    and metabolites are copied by identifier, so neither input model is
    mutated and the returned model owns all of its objects.
    """
    if source_precedence not in {"base", "incoming"}:
        raise ValueError("source_precedence must be 'base' or 'incoming'")
    from cobra import Reaction

    result = base_model.copy()
    added_metabolites = 0
    overlapping_metabolites = 0
    for incoming in incoming_model.metabolites:
        if result.metabolites.has_id(incoming.id):
            target = result.metabolites.get_by_id(incoming.id)
            overlapping_metabolites += 1
            if not target.name and incoming.name:
                target.name = incoming.name
            if target.formula is None and incoming.formula:
                target.formula = incoming.formula
            if target.charge is None and incoming.charge is not None:
                target.charge = incoming.charge
            if source_precedence == "incoming":
                target.name = incoming.name or target.name
                target.formula = incoming.formula or target.formula
                if incoming.charge is not None:
                    target.charge = incoming.charge
            _merge_annotation(target, incoming)
            if provenance:
                target.annotation["thg.provenance"] = {
                    "source_model": str(incoming_model.id),
                    "role": "overlap",
                }
            continue
        result.add_metabolites([copy.deepcopy(incoming)])
        if provenance:
            result.metabolites.get_by_id(incoming.id).annotation["thg.provenance"] = {
                "source_model": str(incoming_model.id),
                "role": "added",
            }
        added_metabolites += 1

    added_reactions = 0
    overlapping_reactions = 0
    for incoming in incoming_model.reactions:
        if result.reactions.has_id(incoming.id):
            target = result.reactions.get_by_id(incoming.id)
            overlapping_reactions += 1
            if not target.name and incoming.name:
                target.name = incoming.name
            if not target.gene_reaction_rule and incoming.gene_reaction_rule:
                target.gene_reaction_rule = incoming.gene_reaction_rule
            if source_precedence == "incoming":
                target.name = incoming.name or target.name
                target.lower_bound = incoming.lower_bound
                target.upper_bound = incoming.upper_bound
                if incoming.gene_reaction_rule:
                    target.gene_reaction_rule = incoming.gene_reaction_rule
            _merge_annotation(target, incoming)
            if provenance:
                target.annotation["thg.provenance"] = {
                    "source_model": str(incoming_model.id),
                    "role": "overlap",
                }
            continue

        reaction = Reaction(
            incoming.id,
            name=incoming.name,
            lower_bound=incoming.lower_bound,
            upper_bound=incoming.upper_bound,
        )
        reaction.add_metabolites(
            {
                result.metabolites.get_by_id(metabolite.id): coefficient
                for metabolite, coefficient in incoming.metabolites.items()
            }
        )
        reaction.gene_reaction_rule = incoming.gene_reaction_rule
        reaction.annotation.update(copy.deepcopy(incoming.annotation))
        if provenance:
            reaction.annotation["thg.provenance"] = {
                "source_model": str(incoming_model.id),
                "role": "added",
            }
        result.add_reactions([reaction])
        added_reactions += 1

    removed_isolated = 0
    if remove_isolated_metabolites:
        isolated = [
            metabolite for metabolite in result.metabolites if not metabolite.reactions
        ]
        result.remove_metabolites(isolated, destructive=False)
        removed_isolated = len(isolated)

    if source_precedence == "incoming":
        # Incoming precedence is intentionally limited to non-structural
        # fields; replacing base stoichiometry would bypass the reviewed plan.
        result.annotation["thg.source_precedence"] = "incoming"
    destination = Path(output_path) if output_path is not None else None
    if destination is not None:
        _write_model(result, destination)
    return result, MergeReport(
        added_metabolites=added_metabolites,
        added_reactions=added_reactions,
        overlapping_metabolites=overlapping_metabolites,
        overlapping_reactions=overlapping_reactions,
        removed_isolated_metabolites=removed_isolated,
        output_path=destination,
    )


def merge_models_from_paths(
    base_path: str | Path,
    incoming_path: str | Path,
    output_path: str | Path,
    *,
    remove_isolated_metabolites: bool = False,
) -> tuple[Any, MergeReport]:
    """Load two SBML/JSON models and merge them to an explicit output path."""
    from cobra.io import load_json_model, read_sbml_model

    def load(path: Path) -> Any:
        return (
            load_json_model(str(path))
            if path.suffix.lower() == ".json"
            else read_sbml_model(str(path))
        )

    return merge_models(
        load(Path(base_path)),
        load(Path(incoming_path)),
        output_path=output_path,
        remove_isolated_metabolites=remove_isolated_metabolites,
    )


__all__ = [
    "MergeDecision",
    "MergePolicy",
    "MergePlan",
    "MergeReport",
    "apply_merge_plan",
    "generate_merge_plan",
    "merge_models",
    "merge_models_from_paths",
    "validate_merged_model",
]
