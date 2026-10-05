"""Explicit, non-mutating model merge workflow."""

from __future__ import annotations

import copy
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field, replace
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
    """Policies for the merge decisions that are a matter of preference.

    Metabolite chemistry has no policy: two metabolites merge only when their
    formula and charge are identical (see
    [`generate_merge_plan`][thg_protocol.merge.generate_merge_plan]).
    ``source_precedence`` picks the side whose names win on overlaps.
    """

    source_precedence: str = "base"
    direction: str = "strict"
    bounds: str = "report"
    gpr: str = "report"

    def __post_init__(self) -> None:
        choices = {
            "source_precedence": {"base", "incoming"},
            "direction": {"strict", "allow-reversal"},
            "bounds": {"report", "base", "incoming"},
            "gpr": {"report", "base", "incoming"},
        }
        for name, allowed in choices.items():
            if getattr(self, name) not in allowed:
                raise ValueError(f"{name} must be one of {sorted(allowed)}")


@dataclass(frozen=True)
class MergePlan:
    """Complete plan emitted before a merge mutates a copied model.

    ``renamed`` gives the new ID of each incoming metabolite that shares an ID
    with a base metabolite but is not the same species.
    """

    metabolite_map: dict[str, str]
    gene_map: dict[str, str]
    reaction_map: dict[str, str]
    decisions: tuple[MergeDecision, ...]
    policy: MergePolicy = MergePolicy()
    renamed: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "metabolite_map": dict(sorted(self.metabolite_map.items())),
            "gene_map": dict(sorted(self.gene_map.items())),
            "reaction_map": dict(sorted(self.reaction_map.items())),
            "renamed": dict(sorted(self.renamed.items())),
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
        removed = sorted(set(policy) - set(MergePolicy.__dataclass_fields__))
        if removed:
            raise ValueError(
                f"merge plan uses removed policy fields {removed}; regenerate it"
            )

        def mapping(key: str) -> dict[str, str]:
            return {
                str(name): str(value)
                for name, value in dict(payload.get(key, {})).items()
            }

        return cls(
            mapping("metabolite_map"),
            mapping("gene_map"),
            mapping("reaction_map"),
            tuple(
                MergeDecision(**dict(item))
                for item in decisions
                if isinstance(item, Mapping)
            ),
            MergePolicy(**dict(policy)),
            mapping("renamed"),
        )


#: Annotation namespaces that link metabolites across models.
METABOLITE_LINKS = ("kegg.compound", "chebi", "hmdb", "inchikey")
#: Annotation namespaces that link reactions with different IDs.
REACTION_LINKS = ("kegg.reaction", "ec-code", "bigg.reaction")
#: Suffix for incoming metabolites renamed because their ID is taken.
RENAME_SUFFIX = "__incoming"


def _annotation_values(item: Any, key: str) -> set[str]:
    value = item.annotation.get(key)
    values = value if isinstance(value, (list, tuple, set)) else [value]
    return {str(entry) for entry in values if entry not in (None, "")}


def _index(objects: Any, keys: tuple[str, ...]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for item in objects:
        for key in keys:
            for identifier in sorted(_annotation_values(item, key)):
                result.setdefault(f"{key}:{identifier}", []).append(item.id)
    return result


def _chemistry(metabolite: Any) -> tuple[object, object]:
    """Element counts (with hydrogen) and charge; ``None`` where unknown."""
    from thg_protocol.model_build.mass_balance import formula_atoms

    atoms = formula_atoms(metabolite.formula or "")
    charge = metabolite.charge
    return (
        tuple(sorted(atoms.items())) if atoms else None,
        None if charge is None else float(charge),
    )


def _metabolite_conflict(first: Any, second: Any) -> tuple[str, str] | None:
    """Why two linked metabolites are not the same species, or None.

    Returns the decision category and a description. Formula and charge must
    be identical, hydrogen included: a protonation difference changes the
    stoichiometry of every reaction written for either form.
    """
    if first.compartment != second.compartment:
        return (
            "compartment-conflict",
            f"compartment {first.compartment} vs {second.compartment}",
        )
    ours, theirs = _chemistry(first), _chemistry(second)
    if ours != theirs:
        detail = (
            f"formula {first.formula or '-'} vs {second.formula or '-'}, "
            f"charge {first.charge} vs {second.charge}"
        )
        if None in ours or None in theirs:
            category = "missing-chemistry"
        elif ours[0] == theirs[0]:
            category = "charge-conflict"
        elif dict(ours[0]).keys() - {"H"} == dict(theirs[0]).keys() - {"H"} and all(
            count == dict(theirs[0])[element]
            for element, count in ours[0]
            if element != "H"
        ):
            category = "protonation-conflict"
        else:
            category = "formula-conflict"
        return category, detail
    # Same chemistry is not the same compound (glucose and fructose share
    # C6H12O6): disjoint KEGG compound IDs mean a mis-annotation.
    from thg_protocol.validation import IDENTITY_ANNOTATIONS

    for key in IDENTITY_ANNOTATIONS:
        left, right = _annotation_values(first, key), _annotation_values(second, key)
        if left and right and not left & right:
            return "identifier-conflict", f"{key} {sorted(left)} vs {sorted(right)}"
    return None


def species_ignored(identifier: str, ignore: Iterable[str]) -> bool:
    """Whether ``identifier`` is one of the ``ignore`` species (or its compartments)."""
    lowered = str(identifier).lower()
    return any(
        lowered == str(item).lower() or lowered.startswith(f"{str(item).lower()}_")
        for item in ignore
    )


def reaction_stoichiometry(
    reaction: Any,
    metabolite_map: Mapping[str, str] | None = None,
    *,
    ignore: Iterable[str] = (),
) -> dict[str, float]:
    """Metabolite ID -> coefficient, the identity of a reaction's chemistry.

    ``metabolite_map`` renames metabolites first (coefficients of metabolites
    that map to one ID add up). Every species counts, H+ and H2O included:
    two reactions that differ only in protons or water are different
    reactions. ``ignore`` names species to leave out, matched by ID or ID
    prefix before the compartment (``"atp"`` skips ``atp_c``); only a caller
    that asks for it drops anything.
    """
    result: dict[str, float] = {}
    for metabolite, coefficient in reaction.metabolites.items():
        identifier = (metabolite_map or {}).get(metabolite.id, metabolite.id)
        if species_ignored(identifier, ignore):
            continue
        result[identifier] = result.get(identifier, 0.0) + float(coefficient)
    rounded = {key: round(value, 12) for key, value in result.items()}
    return {key: value for key, value in sorted(rounded.items()) if value}


def _reverse(stoichiometry: Mapping[str, float]) -> dict[str, float]:
    return {key: -value for key, value in stoichiometry.items()}


def _link_metabolites(
    base_model: Any, incoming_model: Any
) -> tuple[dict[tuple[str, str], list[str]], dict[tuple[str, str], list[str]]]:
    """Return linked (base, incoming) pairs and ambiguous groups, with tokens.

    A link is the same metabolite ID. Metabolites whose ID is not in the other
    model are linked by a shared annotation identifier in the same
    compartment (ATP in the cytosol and in mitochondria share a KEGG ID but
    are different species). A metabolite linked to more than one on the
    other side is ambiguous.
    """

    def compartment(model: Any, metabolite_id: str) -> str:
        return model.metabolites.get_by_id(metabolite_id).compartment or ""

    pairs: dict[tuple[str, str], list[str]] = {}
    ambiguous: dict[tuple[str, str], list[str]] = {}
    for metabolite in incoming_model.metabolites:
        if base_model.metabolites.has_id(metabolite.id):
            pairs.setdefault((metabolite.id, metabolite.id), []).append("metabolite ID")
    left = _index(base_model.metabolites, METABOLITE_LINKS)
    right = _index(incoming_model.metabolites, METABOLITE_LINKS)
    for token in sorted(set(left) & set(right)):
        targets = sorted(
            {
                item
                for item in left[token]
                if not incoming_model.metabolites.has_id(item)
            }
        )
        candidates = sorted(
            {item for item in right[token] if not base_model.metabolites.has_id(item)}
        )
        if not targets or not candidates:
            continue
        if len(targets) == len(candidates) == 1:
            pairs.setdefault((targets[0], candidates[0]), []).append(token)
            continue
        places = {compartment(base_model, item) for item in targets} & {
            compartment(incoming_model, item) for item in candidates
        }
        for place in sorted(places):
            here = [item for item in targets if compartment(base_model, item) == place]
            there = [
                item
                for item in candidates
                if compartment(incoming_model, item) == place
            ]
            group = pairs if len(here) == len(there) == 1 else ambiguous
            group.setdefault((",".join(here), ",".join(there)), []).append(token)

    targets_of: dict[str, set[str]] = {}
    sources_of: dict[str, set[str]] = {}
    for target, source in pairs:
        targets_of.setdefault(source, set()).add(target)
        sources_of.setdefault(target, set()).add(source)
    unique: dict[tuple[str, str], list[str]] = {}
    for (target, source), tokens in pairs.items():
        if len(targets_of[source]) > 1 or len(sources_of[target]) > 1:
            key = (
                ",".join(sorted(targets_of[source])),
                ",".join(sorted(sources_of[target])),
            )
            ambiguous.setdefault(key, []).extend(tokens)
        else:
            unique[(target, source)] = tokens
    return unique, ambiguous


def generate_merge_plan(
    base_model: Any,
    incoming_model: Any,
    *,
    policy: MergePolicy | None = None,
) -> MergePlan:
    """Plan a merge: which metabolites, reactions and genes are the same.

    Metabolites are linked by the same ID or, when their ID is not in the
    other model, by a shared annotation identifier (KEGG, ChEBI, HMDB,
    InChIKey) in the same compartment. A
    linked pair is merged only when it is the same species: identical
    formula (element counts, hydrogen included) and charge, and no disjoint
    KEGG compound IDs. Every other linked pair is kept separate with a
    decision naming why (``protonation-conflict``, ``formula-conflict``,
    ``charge-conflict``, ``missing-chemistry``, ``identifier-conflict``,
    ``compartment-conflict`` or ``ambiguous-metabolite``); an incoming
    metabolite kept separate from a base metabolite with its ID is renamed
    with the ``__incoming`` suffix, so each model's reactions stay balanced
    against their own chemistry.

    Reactions with the same ID are the same reaction; when their
    stoichiometry differs (after mapping and renaming), the base reaction is
    kept and the difference reported. Reactions with different IDs merge
    when they share an annotation identifier and have exactly the same
    stoichiometry, H+ and H2O included.
    """
    policy = policy or MergePolicy()
    decisions: list[MergeDecision] = []

    pairs, ambiguous = _link_metabolites(base_model, incoming_model)
    metabolite_map: dict[str, str] = {}
    kept_separate: list[tuple[str, str, str, str, str]] = []
    for (target, source), tokens in sorted(pairs.items()):
        conflict = _metabolite_conflict(
            base_model.metabolites.get_by_id(target),
            incoming_model.metabolites.get_by_id(source),
        )
        if conflict is None:
            metabolite_map[source] = target
            decisions.append(
                MergeDecision(
                    "metabolite-equivalence", target, source, "map", ", ".join(tokens)
                )
            )
        else:
            kept_separate.append((*conflict, target, source, ", ".join(tokens)))

    taken = {item.id for item in base_model.metabolites} | {
        item.id for item in incoming_model.metabolites
    }
    renamed: dict[str, str] = {}
    for metabolite in sorted(incoming_model.metabolites, key=lambda item: item.id):
        if base_model.metabolites.has_id(metabolite.id) and (
            metabolite_map.get(metabolite.id) != metabolite.id
        ):
            new_id, counter = f"{metabolite.id}{RENAME_SUFFIX}", 1
            while new_id in taken:
                counter += 1
                new_id = f"{metabolite.id}{RENAME_SUFFIX}{counter}"
            taken.add(new_id)
            renamed[metabolite.id] = new_id

    def note(source_ids: str) -> str:
        names = [renamed[item] for item in source_ids.split(",") if item in renamed]
        return f"; incoming renamed to {', '.join(names)}" if names else ""

    for category, detail, target, source, token in kept_separate:
        decisions.append(
            MergeDecision(
                category,
                target,
                source,
                "keep-separate",
                f"{token}; {detail}{note(source)}",
            )
        )
    decisions.extend(
        MergeDecision(
            "ambiguous-metabolite",
            targets,
            candidates,
            "keep-separate",
            ", ".join(sorted(set(tokens))) + note(candidates),
        )
        for (targets, candidates), tokens in sorted(ambiguous.items())
    )

    incoming_ids = {**metabolite_map, **renamed}
    gene_map = {
        gene.id: gene.id
        for gene in incoming_model.genes
        if base_model.genes.has_id(gene.id)
    }
    reaction_map: dict[str, str] = {}
    for reaction in sorted(incoming_model.reactions, key=lambda item: item.id):
        if not base_model.reactions.has_id(reaction.id):
            continue
        reaction_map[reaction.id] = reaction.id
        base_signature = reaction_stoichiometry(
            base_model.reactions.get_by_id(reaction.id)
        )
        signature = reaction_stoichiometry(reaction, incoming_ids)
        if signature == base_signature:
            decisions.append(
                MergeDecision(
                    "reaction-equivalence",
                    reaction.id,
                    reaction.id,
                    "map",
                    "reaction ID",
                )
            )
        else:
            category = (
                "direction-conflict"
                if signature == _reverse(base_signature)
                else "reaction-stoichiometry-conflict"
            )
            decisions.append(
                MergeDecision(
                    category,
                    reaction.id,
                    reaction.id,
                    "keep-base",
                    "reaction ID; stoichiometry differs",
                )
            )

    incoming_tokens = _index(incoming_model.reactions, REACTION_LINKS)
    base_tokens = _index(base_model.reactions, REACTION_LINKS)
    for token in sorted(set(incoming_tokens) & set(base_tokens)):
        sources = sorted(set(incoming_tokens[token]))
        targets = sorted(set(base_tokens[token]))
        if len(sources) != 1 or len(targets) != 1:
            continue
        source, target = sources[0], targets[0]
        if source in reaction_map or target in reaction_map.values():
            continue
        signature = reaction_stoichiometry(
            incoming_model.reactions.get_by_id(source), incoming_ids
        )
        base_signature = reaction_stoichiometry(base_model.reactions.get_by_id(target))
        if signature == base_signature:
            reaction_map[source] = target
            decisions.append(
                MergeDecision("reaction-equivalence", target, source, "map", token)
            )
        elif signature == _reverse(base_signature):
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
    for identifier in sorted(
        key for key, value in reaction_map.items() if key == value
    ):
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
    return MergePlan(
        metabolite_map, gene_map, reaction_map, tuple(decisions), policy, renamed
    )


def apply_merge_plan(
    base_model: Any,
    incoming_model: Any,
    plan: MergePlan,
    *,
    output_path: str | Path | None = None,
    provenance: bool = True,
) -> tuple[Any, MergeReport]:
    """Apply a reviewed plan to copies of both models.

    Incoming metabolites are renamed and mapped as planned, so a mapped
    metabolite takes the base ID (its chemistry is identical by
    construction). Overlapping reactions keep the base stoichiometry; bounds
    and GPRs follow the plan's policy, and names follow its source
    precedence.
    """
    incoming = incoming_model.copy()
    for source, target in sorted(plan.renamed.items()):
        if incoming.metabolites.has_id(source):
            incoming.metabolites.get_by_id(source).id = target
    for source, target in sorted(plan.metabolite_map.items()):
        if (
            source != target
            and incoming.metabolites.has_id(source)
            and not incoming.metabolites.has_id(target)
        ):
            incoming.metabolites.get_by_id(source).id = target
    for source, target in sorted(plan.reaction_map.items()):
        if (
            source != target
            and incoming.reactions.has_id(source)
            and not incoming.reactions.has_id(target)
        ):
            incoming.reactions.get_by_id(source).id = target
    merged, report = _combine(
        base_model,
        incoming,
        source_precedence=plan.policy.source_precedence,
        provenance=provenance,
    )
    for incoming_reaction in incoming.reactions:
        identifier = incoming_reaction.id
        if not base_model.reactions.has_id(identifier):
            continue
        target = merged.reactions.get_by_id(identifier)
        base = base_model.reactions.get_by_id(identifier)
        source = incoming_reaction if plan.policy.bounds == "incoming" else base
        target.bounds = source.bounds
        target.gene_reaction_rule = (
            incoming_reaction.gene_reaction_rule
            if plan.policy.gpr == "incoming"
            else base.gene_reaction_rule
        )
    if output_path is not None:
        _write_model(merged, Path(output_path))
        report = replace(report, output_path=Path(output_path))
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
    from thg_protocol.io.models import save_model

    save_model(model, output_path)


def _combine(
    base_model: Any,
    incoming_model: Any,
    *,
    source_precedence: str,
    provenance: bool,
) -> tuple[Any, MergeReport]:
    """Add the incoming objects to a copy of the base model, by ID.

    Called with an incoming model already renamed and mapped by a plan, so
    an overlapping metabolite has the same chemistry on both sides. Overlaps
    keep the base formula, charge, stoichiometry and bounds; names follow
    ``source_precedence``, non-empty annotations are added and missing GPRs
    filled.
    """
    from cobra import Reaction

    result = base_model.copy()
    added_metabolites = 0
    overlapping_metabolites = 0
    for incoming in incoming_model.metabolites:
        if result.metabolites.has_id(incoming.id):
            target = result.metabolites.get_by_id(incoming.id)
            overlapping_metabolites += 1
            if incoming.name and (source_precedence == "incoming" or not target.name):
                target.name = incoming.name
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
            if incoming.name and (source_precedence == "incoming" or not target.name):
                target.name = incoming.name
            if not target.gene_reaction_rule and incoming.gene_reaction_rule:
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

    return result, MergeReport(
        added_metabolites=added_metabolites,
        added_reactions=added_reactions,
        overlapping_metabolites=overlapping_metabolites,
        overlapping_reactions=overlapping_reactions,
        removed_isolated_metabolites=0,
    )


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

    Plans the merge with
    [`generate_merge_plan`][thg_protocol.merge.generate_merge_plan] and
    applies it, so metabolites merge only when they are the same species.
    Neither input model is mutated.
    """
    plan = generate_merge_plan(
        base_model,
        incoming_model,
        policy=MergePolicy(source_precedence=source_precedence),
    )
    merged, report = apply_merge_plan(
        base_model, incoming_model, plan, provenance=provenance
    )
    if remove_isolated_metabolites:
        isolated = [
            metabolite for metabolite in merged.metabolites if not metabolite.reactions
        ]
        merged.remove_metabolites(isolated, destructive=False)
        report = replace(report, removed_isolated_metabolites=len(isolated))
    if output_path is not None:
        _write_model(merged, Path(output_path))
        report = replace(report, output_path=Path(output_path))
    return merged, report


def merge_models_from_paths(
    base_path: str | Path,
    incoming_path: str | Path,
    output_path: str | Path,
    *,
    remove_isolated_metabolites: bool = False,
) -> tuple[Any, MergeReport]:
    """Load two SBML/JSON models and merge them to an explicit output path."""
    from thg_protocol.io.models import load_model

    def load(path: Path) -> Any:
        return load_model(path)

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
