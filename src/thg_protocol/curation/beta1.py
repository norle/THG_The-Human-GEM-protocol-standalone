"""Deterministic, proposal-driven curation of an existing human GEM.

This module intentionally keeps service access outside the curation core.  A
caller supplies normalized candidates or explicit corrections, so the same
pipeline works with recorded evidence, injected clients, and offline tests.
All mutating operations begin with a model copy and produce auditable records.
"""

from __future__ import annotations

import ast
import json
import re
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from thg_protocol.analysis.consistency import reaction_balance
from thg_protocol.analysis.model_signature import model_signature
from thg_protocol.model_build.mass_balance import formula_atoms
from thg_protocol.workflow.hashing import sha256_file
from thg_protocol.workflow.parallel import parallel_map
from thg_protocol.workflow.proposals import (
    Decision,
    Proposal,
    apply_proposals,
    proposal_id,
    write_proposals,
)

SANCTIONED_BETA1_INPUT_SHA256 = (
    "d980f0e58bb1623fc43631f96ad6bf3b55ed8cb649ec691c27b7e37972fa1421"
)

REACTION_CLASSES = (
    "boundary",
    "exchange",
    "demand",
    "sink",
    "biomass",
    "transport",
    "spontaneous",
    "pseudo",
    "internal",
    "unknown",
)
BALANCE_STATUSES = (
    "balanced",
    "unbalanced",
    "not-evaluable-missing-formula",
    "not-evaluable-missing-charge",
    "not-evaluable-generic-formula",
    "excluded-boundary",
    "excluded-biomass",
    "excluded-pseudo-reaction",
    "excluded-generic-formula",
)

GENERIC_FORMULA_POLICIES = {"flag", "exclude"}
DEFAULT_FORMULA_POLICY = {
    "generic-group": "exclude",
    "glycan": "exclude",
    "polymer": "exclude",
    "r-group": "exclude",
    "x-group": "exclude",
}
DEFAULT_BALANCE_STRATEGY = "proton-water"

IDENTITY_NAMESPACE_PRIORITY = (
    "inchikey",
    "inchi",
    "smiles",
    "chebi",
    "kegg",
    "hmdb",
    "pubchem",
    "metanetx.chemical",
    "bigg.metabolite",
    "vmhmetabolite",
    "lipidmaps",
)
NON_CHEMICAL_IDENTITY_NAMESPACES = {"sbo", "ontology"}


def _json(value: object) -> object:
    """Make common COBRA values JSON-safe without depending on pandas."""
    if isinstance(value, Mapping):
        return {str(k): _json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_json(v) for v in value]
    if hasattr(value, "item") and callable(value.item):
        return _json(value.item())
    return value


def _annotation_values(obj: Any) -> Iterable[tuple[str, str]]:
    annotation = getattr(obj, "annotation", {}) or {}
    if not isinstance(annotation, Mapping):
        return ()
    values: list[tuple[str, str]] = []
    for key, value in annotation.items():
        if isinstance(value, (list, tuple, set, frozenset)):
            values.extend((str(key), str(item)) for item in value)
        else:
            values.append((str(key), str(value)))
    return values


def _merge_annotations(first: object, second: object) -> dict[str, object]:
    """Merge annotation namespaces without losing either object's evidence."""
    result = dict(first) if isinstance(first, Mapping) else {}
    if not isinstance(second, Mapping):
        return result
    for namespace, value in second.items():
        existing = result.get(namespace)
        left = (
            list(existing)
            if isinstance(existing, (list, tuple, set, frozenset))
            else ([existing] if existing is not None else [])
        )
        right = (
            list(value) if isinstance(value, (list, tuple, set, frozenset)) else [value]
        )
        unique = {
            json.dumps(_json(item), sort_keys=True): _json(item)
            for item in left + right
        }
        result[str(namespace)] = [unique[key] for key in sorted(unique)]
    return result


def _annotation_identity_exists(
    annotation: object, namespace: str, identity: str
) -> bool:
    if not isinstance(annotation, Mapping):
        return False
    value = annotation.get(namespace)
    values = value if isinstance(value, (list, tuple, set, frozenset)) else (value,)
    normalized = normalize_namespace(identity, namespace)[1]
    return any(
        normalize_namespace(str(item), namespace)[1] == normalized
        for item in values
        if item is not None
    )


def classify_reaction(reaction: Any) -> str:
    """Classify a reaction using explicit COBRA semantics and stable fallbacks."""
    if bool(getattr(reaction, "boundary", False)):
        rid = str(getattr(reaction, "id", "")).lower()
        if rid.startswith("ex_") or "exchange" in rid:
            return "exchange"
        if rid.startswith("dm_") or "demand" in rid:
            return "demand"
        if rid.startswith("sk_") or "sink" in rid:
            return "sink"
        return "boundary"
    rid = str(getattr(reaction, "id", "")).lower()
    name = str(getattr(reaction, "name", "") or "").lower()
    if "biomass" in rid or "biomass" in name:
        return "biomass"
    if any(token in rid for token in ("transport", "tr_")) or rid.endswith("_t"):
        return "transport"
    compartments = {
        str(getattr(metabolite, "compartment", ""))
        for metabolite in getattr(reaction, "metabolites", {})
    }
    if len(compartments) > 1:
        return "transport"
    if not getattr(reaction, "gene_reaction_rule", "") and (
        "spontaneous" in rid or "spontaneous" in name
    ):
        return "spontaneous"
    if any(token in rid for token in ("pseudo", "pseudoreaction")):
        return "pseudo"
    return "internal" if getattr(reaction, "metabolites", {}) else "unknown"


@dataclass(frozen=True)
class InventoryReport:
    model_id: str
    input_sha256: str | None
    source_version: str | None
    counts: Mapping[str, int]
    compartments: Mapping[str, int]
    reaction_classes: Mapping[str, int]
    missing_formula: tuple[str, ...]
    missing_charge: tuple[str, ...]
    invalid_gpr: tuple[str, ...]
    orphan_metabolites: tuple[str, ...]
    orphan_genes: tuple[str, ...]
    duplicate_ids: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    objective: object = field(default_factory=list)
    software_versions: Mapping[str, str] = field(default_factory=dict)
    identifier_coverage: Mapping[str, int] = field(default_factory=dict)
    missing_gpr: tuple[str, ...] = ()
    invalid_references: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "model_id": self.model_id,
            "input_sha256": self.input_sha256,
            "source_version": self.source_version,
            "counts": dict(self.counts),
            "compartments": dict(self.compartments),
            "reaction_classes": dict(self.reaction_classes),
            "missing_formula": list(self.missing_formula),
            "missing_charge": list(self.missing_charge),
            "invalid_gpr": list(self.invalid_gpr),
            "orphan_metabolites": list(self.orphan_metabolites),
            "orphan_genes": list(self.orphan_genes),
            "duplicate_ids": {k: list(v) for k, v in self.duplicate_ids.items()},
            "objective": _json(self.objective),
            "software_versions": dict(self.software_versions),
            "identifier_coverage": dict(self.identifier_coverage),
            "missing_gpr": list(self.missing_gpr),
            "invalid_references": list(self.invalid_references),
        }


def inventory_model(
    model: Any, *, input_path: str | Path | None = None
) -> InventoryReport:
    """Inspect a model without changing it and return a machine-readable report."""
    metabolites = tuple(model.metabolites)
    reactions = tuple(model.reactions)
    genes = tuple(model.genes)
    used_genes = {gene.id for reaction in reactions for gene in reaction.genes}
    ids = {
        "metabolites": tuple(str(item.id) for item in metabolites),
        "reactions": tuple(str(item.id) for item in reactions),
        "genes": tuple(str(item.id) for item in genes),
    }
    duplicates = {
        kind: tuple(
            sorted(
                identifier for identifier, count in Counter(values).items() if count > 1
            )
        )
        for kind, values in ids.items()
        if any(count > 1 for count in Counter(values).values())
    }
    invalid_gpr: list[str] = []
    missing_gpr: list[str] = []
    for reaction in reactions:
        rule = str(getattr(reaction, "gene_reaction_rule", "") or "").strip()
        if not rule:
            missing_gpr.append(str(reaction.id))
        else:
            try:
                parse_gpr(rule)
            except ValueError:
                invalid_gpr.append(str(reaction.id))
    identifier_coverage = Counter(
        namespace
        for metabolite in metabolites
        for namespace, value in _annotation_values(metabolite)
        if str(value).strip()
    )
    invalid_references: list[str] = []
    metabolite_ids = {str(item.id) for item in metabolites}
    reaction_ids = {str(item.id) for item in reactions}
    gene_ids = {str(item.id) for item in genes}
    for reaction in reactions:
        for metabolite in getattr(reaction, "metabolites", {}):
            if str(getattr(metabolite, "id", "")) not in metabolite_ids:
                invalid_references.append(
                    "reaction:{}->metabolite:{}".format(
                        reaction.id, getattr(metabolite, "id", "")
                    )
                )
        for gene in getattr(reaction, "genes", ()):
            if str(getattr(gene, "id", "")) not in gene_ids:
                invalid_references.append(
                    f"reaction:{reaction.id}->gene:{getattr(gene, 'id', '')}"
                )
    for group in getattr(model, "groups", ()):
        for member in getattr(group, "members", ()):
            member_id = str(getattr(member, "id", ""))
            if member_id not in metabolite_ids | reaction_ids | gene_ids:
                invalid_references.append(
                    f"group:{getattr(group, 'id', '')}->{member_id}"
                )
    compartments = Counter(
        str(getattr(item, "compartment", "")) for item in metabolites
    )
    classes = Counter(classify_reaction(item) for item in reactions)
    objective = model_signature(model).get("objective", [])
    return InventoryReport(
        model_id=str(getattr(model, "id", "")),
        input_sha256=sha256_file(input_path) if input_path is not None else None,
        source_version=(
            str(model.version) if getattr(model, "version", None) is not None else None
        ),
        counts={
            "metabolites": len(metabolites),
            "reactions": len(reactions),
            "genes": len(genes),
        },
        compartments=dict(sorted(compartments.items())),
        reaction_classes={key: classes.get(key, 0) for key in REACTION_CLASSES},
        missing_formula=tuple(
            sorted(
                str(item.id)
                for item in metabolites
                if not str(getattr(item, "formula", "") or "").strip()
            )
        ),
        missing_charge=tuple(
            sorted(
                str(item.id)
                for item in metabolites
                if getattr(item, "charge", None) is None
            )
        ),
        invalid_gpr=tuple(sorted(invalid_gpr)),
        orphan_metabolites=tuple(
            sorted(str(item.id) for item in metabolites if not item.reactions)
        ),
        orphan_genes=tuple(
            sorted(str(item.id) for item in genes if str(item.id) not in used_genes)
        ),
        duplicate_ids=duplicates,
        objective=objective,
        software_versions=_software_versions(),
        identifier_coverage=dict(sorted(identifier_coverage.items())),
        missing_gpr=tuple(sorted(missing_gpr)),
        invalid_references=tuple(sorted(invalid_references)),
    )


@dataclass(frozen=True)
class MetaboliteCandidate:
    identity: str
    namespace: str
    evidence: tuple[str, ...] = ()
    score: float = 0.0
    reason: str = ""
    name: str | None = None
    formula: str | None = None
    charge: int | None = None
    structural_identifiers: tuple[str, ...] = ()
    compartment: str | None = None


def normalize_namespace(
    identifier: str, namespace: str | None = None
) -> tuple[str | None, str]:
    """Normalize common annotation namespaces without changing chemical identity."""
    value = str(identifier).strip()
    if not value:
        return namespace, value
    prefix, separator, local = value.partition(":")
    if separator and (namespace is None or prefix.lower() == str(namespace).lower()):
        namespace, value = (prefix.lower() if namespace is None else namespace), local
    aliases = {"kegg.compound": "kegg", "chebi": "chebi", "pubchem.compound": "pubchem"}
    return aliases.get((namespace or "").lower(), namespace), value


def resolve_metabolite_identity(
    candidates: Iterable[MetaboliteCandidate | Mapping[str, object]],
    *,
    errors: Iterable[str] = (),
    reference_name: str | None = None,
    reference_formula: str | None = None,
    reference_charge: int | None = None,
    reference_structural_identifiers: Iterable[str] = (),
) -> dict[str, object]:
    """Select a canonical candidate while retaining all cross-references.

    Different databases normally describe the same metabolite. A score tie is
    therefore broken by stable namespace precedence; only competing IDs
    within the same namespace remain ambiguous.
    """
    service_errors = tuple(str(error) for error in errors)
    if service_errors:
        return {
            "status": "service-failure",
            "selected": None,
            "candidates": [],
            "errors": list(service_errors),
            "evidence": [],
            "reason": "evidence collection failed",
        }
    items = []
    for candidate in candidates:
        if isinstance(candidate, MetaboliteCandidate):
            item = candidate
        else:
            item = MetaboliteCandidate(
                identity=str(candidate["identity"]),
                namespace=str(candidate.get("namespace", "")),
                evidence=tuple(str(x) for x in candidate.get("evidence", ())),
                score=float(candidate.get("score", 0.0)),
                reason=str(candidate.get("reason", "")),
                name=(
                    str(candidate["name"])
                    if candidate.get("name") is not None
                    else None
                ),
                formula=(
                    str(candidate["formula"])
                    if candidate.get("formula") is not None
                    else None
                ),
                charge=(
                    int(candidate["charge"])
                    if candidate.get("charge") is not None
                    else None
                ),
                structural_identifiers=tuple(
                    str(item) for item in candidate.get("structural_identifiers", ())
                ),
                compartment=(
                    str(candidate["compartment"])
                    if candidate.get("compartment") is not None
                    else None
                ),
            )
        original_namespace = str(item.namespace)
        namespace, identity = normalize_namespace(item.identity, item.namespace)
        if (
            original_namespace.casefold() in NON_CHEMICAL_IDENTITY_NAMESPACES
            or (namespace or "").casefold() in NON_CHEMICAL_IDENTITY_NAMESPACES
        ):
            namespace, identity = original_namespace, item.identity
        calculated_score, calculated_reason = score_metabolite_candidate(
            item,
            reference_name=reference_name,
            reference_formula=reference_formula,
            reference_charge=reference_charge,
            reference_structural_identifiers=reference_structural_identifiers,
        )
        items.append(
            MetaboliteCandidate(
                identity,
                namespace or "",
                item.evidence,
                item.score if item.score else calculated_score,
                item.reason or calculated_reason,
                item.name,
                item.formula,
                item.charge,
                item.structural_identifiers,
                item.compartment,
            )
        )
    ordered = sorted(
        items, key=lambda item: (-item.score, item.namespace, item.identity)
    )
    if not ordered:
        return {
            "status": "no-match",
            "selected": None,
            "candidates": [],
            "errors": [],
            "evidence": [],
            "reason": "no candidate was supplied",
        }
    usable = [
        item
        for item in ordered
        if item.namespace.casefold() not in NON_CHEMICAL_IDENTITY_NAMESPACES
    ]
    if not usable:
        return {
            "status": "no-match",
            "selected": None,
            "candidates": [_json(item.__dict__) for item in ordered],
            "errors": [],
            "evidence": sorted(
                {evidence for item in ordered for evidence in item.evidence}
            ),
            "reason": "only non-chemical ontology annotations were supplied",
        }
    top_score = usable[0].score
    tied = [item for item in usable if item.score == top_score]
    priority = {
        namespace: index
        for index, namespace in enumerate(IDENTITY_NAMESPACE_PRIORITY)
    }
    best_priority = min(
        priority.get(item.namespace.casefold(), len(priority)) for item in tied
    )
    preferred = [
        item
        for item in tied
        if priority.get(item.namespace.casefold(), len(priority)) == best_priority
    ]
    if len({(item.namespace, item.identity) for item in preferred}) > 1:
        return {
            "status": "ambiguous",
            "selected": None,
            "candidates": [_json(item.__dict__) for item in ordered],
            "errors": [],
            "evidence": sorted(
                {evidence for item in preferred for evidence in item.evidence}
            ),
            "reason": "top candidates conflict within the preferred namespace",
        }
    top = preferred[0]
    return {
        "status": "matched",
        "selected": _json(top.__dict__),
        "candidates": [_json(item.__dict__) for item in ordered],
        "errors": [],
        "evidence": sorted(
            {evidence for item in usable for evidence in item.evidence}
        ),
        "reason": top.reason,
    }


def score_metabolite_candidate(
    candidate: MetaboliteCandidate,
    *,
    reference_name: str | None = None,
    reference_formula: str | None = None,
    reference_charge: int | None = None,
    reference_structural_identifiers: Iterable[str] = (),
) -> tuple[float, str]:
    """Score normalized chemical evidence without conflating compartments."""
    structural = {str(item) for item in reference_structural_identifiers}
    if structural and structural.intersection(candidate.structural_identifiers):
        return 100.0, "curated structural identifier mapping"
    if candidate.evidence and any(
        token.lower() in {"curated", "database", "existing-identifier"}
        for token in candidate.evidence
    ):
        return 80.0, "existing high-quality database identifier"
    formula_match = bool(
        reference_formula
        and candidate.formula
        and reference_formula == candidate.formula
    )
    charge_match = (
        reference_charge is not None
        and candidate.charge is not None
        and reference_charge == candidate.charge
    )
    if formula_match and charge_match:
        return 60.0, "formula and charge compatible"
    if formula_match:
        return 50.0, "formula compatible"
    if (
        reference_name
        and candidate.name
        and reference_name.casefold() == candidate.name.casefold()
    ):
        return 10.0, "curated synonym/name support"
    return 0.0, "supporting evidence is insufficient"


def protonation_relation(
    first: MetaboliteCandidate,
    second: MetaboliteCandidate,
) -> dict[str, object]:
    """Describe a protonation/charge-state relationship explicitly."""
    same_structure = bool(
        set(first.structural_identifiers)
        and set(first.structural_identifiers).intersection(
            second.structural_identifiers
        )
    )
    charge_delta = (
        second.charge - first.charge
        if first.charge is not None and second.charge is not None
        else None
    )
    return {
        "same_chemical_scaffold": same_structure,
        "charge_delta": charge_delta,
        "relationship": "protonation-state"
        if same_structure and charge_delta
        else "unresolved",
        "compartments": [first.compartment, second.compartment],
    }


@dataclass(frozen=True)
class GPRExpression:
    kind: str
    value: str | None = None
    children: tuple[GPRExpression, ...] = ()
    subunit_stoichiometry: tuple[tuple[str, float], ...] = ()

    def to_dict(self) -> dict[str, object]:
        if self.kind == "gene":
            result: dict[str, object] = {"gene": self.value}
            if self.subunit_stoichiometry:
                result["subunit_stoichiometry"] = {
                    gene: coefficient
                    for gene, coefficient in self.subunit_stoichiometry
                }
            return result
        return {self.kind: [child.to_dict() for child in self.children]}


def parse_gpr(expression: str) -> GPRExpression:
    """Parse a Boolean GPR into a canonicalizable AST."""
    text = str(expression).strip()
    if not text:
        raise ValueError("GPR is empty")
    from cobra.core.gene import GPR

    def convert(node: ast.AST) -> GPRExpression:
        if isinstance(node, ast.Name):
            return GPRExpression("gene", node.id)
        if isinstance(node, ast.BoolOp):
            kind = "and" if isinstance(node.op, ast.And) else "or"
            return GPRExpression(kind, children=tuple(map(convert, node.values)))
        raise ValueError(f"unsupported GPR node: {type(node).__name__}")

    body = GPR.from_string(text).body
    if body is None:
        raise ValueError("invalid GPR")
    return canonicalize_gpr(convert(body))


def canonicalize_gpr(expression: GPRExpression | str) -> GPRExpression:
    """Flatten and sort commutative GPR operators while preserving semantics."""
    node = parse_gpr(expression) if isinstance(expression, str) else expression
    if node.kind == "gene":
        return node
    children = [canonicalize_gpr(child) for child in node.children]
    flattened: list[GPRExpression] = []
    for child in children:
        flattened.extend(child.children if child.kind == node.kind else (child,))
    unique = {json.dumps(child.to_dict(), sort_keys=True): child for child in flattened}
    values = tuple(unique[key] for key in sorted(unique))
    return values[0] if len(values) == 1 else GPRExpression(node.kind, children=values)


def with_subunit_stoichiometry(
    expression: GPRExpression | str,
    stoichiometry: Mapping[str, float],
) -> GPRExpression:
    """Attach optional S-GPR subunit counts without changing Boolean meaning."""
    node = canonicalize_gpr(expression)
    normalized = tuple(
        (str(gene), float(coefficient))
        for gene, coefficient in sorted(
            stoichiometry.items(), key=lambda item: str(item[0])
        )
        if float(coefficient) > 0
    )
    if len(normalized) != len(stoichiometry):
        raise ValueError("S-GPR subunit stoichiometry must be positive")
    if node.kind == "gene":
        return GPRExpression(
            "gene",
            value=node.value,
            subunit_stoichiometry=tuple(
                (gene, coefficient)
                for gene, coefficient in normalized
                if gene == str(node.value)
            ),
        )
    return GPRExpression(
        node.kind,
        children=tuple(
            with_subunit_stoichiometry(child, stoichiometry) for child in node.children
        ),
    )


def serialize_s_gpr(
    expression: GPRExpression | str,
    stoichiometry: Mapping[str, float] | None = None,
) -> dict[str, object]:
    """Return a stable Boolean GPR plus optional subunit metadata."""
    node = (
        with_subunit_stoichiometry(expression, stoichiometry)
        if stoichiometry
        else canonicalize_gpr(expression)
    )
    return {"gpr": serialize_gpr(node), "ast": node.to_dict()}


def serialize_gpr(expression: GPRExpression | str) -> str:
    """Serialize a GPR AST deterministically for COBRA import/export."""
    node = canonicalize_gpr(expression)

    def render(value: GPRExpression, parent: str = "") -> str:
        if value.kind == "gene":
            return str(value.value)
        precedence = {"or": 1, "and": 2}
        rendered = f" {value.kind} ".join(
            render(child, value.kind) for child in value.children
        )
        if parent and precedence[value.kind] < precedence[parent]:
            return f"({rendered})"
        return rendered

    return render(node)


def rewrite_gpr(expression: GPRExpression | str, mapping: Mapping[str, str]) -> str:
    node = canonicalize_gpr(expression)
    if node.kind == "gene":
        return str(mapping.get(str(node.value), node.value))
    return serialize_gpr(
        GPRExpression(
            node.kind,
            children=tuple(
                parse_gpr(rewrite_gpr(child, mapping)) for child in node.children
            ),
        )
    )


def normalize_gene_mapping(mapping: Mapping[str, str]) -> dict[str, str]:
    """Normalize aliases to stable gene IDs and reject mapping cycles."""
    direct = {
        str(alias).strip(): str(target).strip() for alias, target in mapping.items()
    }
    if any(not alias or not target for alias, target in direct.items()):
        raise ValueError("gene aliases and targets must be non-empty")
    result: dict[str, str] = {}
    for alias in sorted(direct):
        current = alias
        seen: set[str] = set()
        while current in direct:
            if current in seen:
                raise ValueError(f"gene mapping cycle includes '{current}'")
            seen.add(current)
            current = direct[current]
        result[alias] = current
    return result


def generate_curation_proposals(
    model: Any,
    *,
    metabolite_identities: Mapping[str, Mapping[str, object]] = {},
    gene_mapping: Mapping[str, str] = {},
    reaction_identities: Mapping[str, Mapping[str, object]] = {},
    subunit_stoichiometry: Mapping[str, Mapping[str, float]] = {},
    canonical_gprs: Mapping[str, Mapping[str, object]] | None = None,
) -> tuple[Proposal, ...]:
    """Generate identity, GPR, and explicit balance proposals as one set.

    ``metabolite_identities`` contains the result of
    ``resolve_metabolite_identity``. The selected candidate is canonical for
    reporting, while all supplied cross-references are merged into the model.
    Ambiguous and failed resolutions are deliberately left out of the mutation
    set.
    """
    proposals: list[Proposal] = []
    for metabolite_id, resolution in sorted(metabolite_identities.items()):
        if resolution.get("status") != "matched":
            continue
        selected = resolution.get("selected")
        if not isinstance(selected, Mapping):
            continue
        references = [
            candidate
            for candidate in resolution.get("candidates", [])
            if isinstance(candidate, Mapping)
        ] or [selected]
        metabolite = model.metabolites.get_by_id(metabolite_id)
        before = _json(getattr(metabolite, "annotation", {}) or {})
        additions: dict[str, list[str]] = {}
        for candidate in references:
            namespace = str(candidate.get("namespace", ""))
            identity = str(candidate.get("identity", ""))
            if (
                namespace
                and identity
                and namespace.casefold() not in NON_CHEMICAL_IDENTITY_NAMESPACES
                and not _annotation_identity_exists(before, namespace, identity)
            ):
                additions.setdefault(namespace, []).append(identity)
        after = _merge_annotations(before, additions)
        namespace = str(selected.get("namespace", ""))
        identity = str(selected.get("identity", ""))
        if not namespace or not identity or after == before:
            continue
        proposals.append(
            Proposal(
                proposal_id=proposal_id(
                    operation="annotate-identity",
                    object_type="metabolite",
                    object_id=metabolite_id,
                    before=before,
                    after=after,
                ),
                operation="annotate-identity",
                object_type="metabolite",
                object_id=metabolite_id,
                before=before,
                after=after,
                evidence=tuple(
                    str(x)
                    for x in (
                        resolution.get("evidence", [])
                        or selected.get("evidence", [])
                    )
                ),
                confidence=str(selected.get("score", "matched")),
                policy="identity-precedence",
                stage="beta1-resolve-metabolite-identities",
                reason=str(selected.get("reason", "selected normalized identity")),
            )
        )
    normalized_genes = normalize_gene_mapping(gene_mapping)
    for reaction in sorted(model.reactions, key=lambda item: str(item.id)):
        rule = str(getattr(reaction, "gene_reaction_rule", "") or "").strip()
        if not rule:
            continue
        curated_record = (canonical_gprs or {}).get(str(reaction.id), {})
        after = (
            str(curated_record.get("after"))
            if isinstance(curated_record, Mapping)
            and isinstance(curated_record.get("after"), str)
            else rewrite_gpr(rule, normalized_genes)
        )
        if after != rule:
            proposals.append(
                Proposal(
                    proposal_id=proposal_id(
                        operation="rewrite-gpr",
                        object_type="reaction",
                        object_id=str(reaction.id),
                        before=rule,
                        after=after,
                    ),
                    operation="rewrite-gpr",
                    object_type="reaction",
                    object_id=str(reaction.id),
                    before=rule,
                    after=after,
                    evidence=tuple(
                        f"gene-mapping:{key}"
                        for key in sorted(normalized_genes)
                        if key in rule
                    ),
                    confidence="configured",
                    policy="canonical-gpr",
                    stage="beta1-curate-gprs",
                    reason="rewrote aliases through canonical gene mapping",
                )
            )
        subunits = subunit_stoichiometry.get(str(reaction.id), {})
        if subunits:
            normalized_subunits = {
                str(gene): float(count)
                for gene, count in sorted(
                    subunits.items(), key=lambda item: str(item[0])
                )
            }
            if any(count <= 0 for count in normalized_subunits.values()):
                raise ValueError("S-GPR subunit stoichiometry must be positive")
            before = _json(getattr(reaction, "annotation", {}) or {})
            after = dict(before) if isinstance(before, Mapping) else {}
            record = serialize_s_gpr(after if after else rule, normalized_subunits)
            after["thg_s_gpr"] = record
            if after != before:
                proposals.append(
                    Proposal(
                        proposal_id=proposal_id(
                            operation="annotate-s-gpr",
                            object_type="reaction",
                            object_id=str(reaction.id),
                            before=before,
                            after=after,
                        ),
                        operation="annotate-s-gpr",
                        object_type="reaction",
                        object_id=str(reaction.id),
                        before=before,
                        after=after,
                        evidence=tuple(
                            f"subunit-stoichiometry:{gene}"
                            for gene in normalized_subunits
                        ),
                        confidence="configured",
                        policy="s-gpr",
                        stage="beta1-curate-gprs",
                        reason="preserved optional complex subunit stoichiometry",
                    )
                )
    for reaction_id, identity in sorted(reaction_identities.items()):
        identity_status = str(identity.get("status", "unresolved"))
        if identity_status not in {"equivalent-reversed", "conflict", "no-match"}:
            continue
        reaction = model.reactions.get_by_id(reaction_id)
        before = _json(getattr(reaction, "annotation", {}) or {})
        after = dict(before) if isinstance(before, Mapping) else {}
        annotation_key = (
            "thg_directionality"
            if identity_status == "equivalent-reversed"
            else "thg_identity"
        )
        after[annotation_key] = {
            "status": identity_status,
            "reversed": identity_status == "equivalent-reversed",
            "reason": str(
                identity.get("reason", "reaction identity remains unresolved")
            ),
            "normalization_policy": str(identity.get("normalization_policy", "strict")),
        }
        if after == before:
            continue
        proposals.append(
            Proposal(
                proposal_id=proposal_id(
                    operation=(
                        "flag-reaction-directionality"
                        if identity_status == "equivalent-reversed"
                        else "flag-reaction-identity"
                    ),
                    object_type="reaction",
                    object_id=reaction_id,
                    before=before,
                    after=after,
                ),
                operation=(
                    "flag-reaction-directionality"
                    if identity_status == "equivalent-reversed"
                    else "flag-reaction-identity"
                ),
                object_type="reaction",
                object_id=reaction_id,
                before=before,
                after=after,
                evidence=tuple(str(item) for item in identity.get("evidence", ())),
                confidence="reference-reversed",
                policy="flag-only",
                stage="beta1-resolve-reaction-identities",
                reason=(
                    "reference stoichiometry is reversed; directionality is flagged"
                    if identity_status == "equivalent-reversed"
                    else "reaction identity conflict is flagged without resolving it"
                ),
                metadata={
                    "normalization_policy": str(
                        identity.get("normalization_policy", "strict")
                    ),
                    "semantic_impact": "annotation only; no stoichiometry is mutated",
                },
            )
        )
    return tuple(proposals)


@dataclass(frozen=True)
class ReactionIdentity:
    status: str
    normalized: Mapping[str, float]
    reversed: bool = False
    reason: str = ""
    normalization_policy: str = "strict"


def normalized_stoichiometry(
    reaction: Any,
    metabolite_mapping: Mapping[str, str] | None = None,
    *,
    proton_water_policy: str = "strict",
    normalization_species: Iterable[str] = (),
) -> dict[str, float]:
    if proton_water_policy not in {"strict", "ignore"}:
        raise ValueError("proton_water_policy must be 'strict' or 'ignore'")
    result: defaultdict[str, float] = defaultdict(float)
    mapping = metabolite_mapping or {}
    ignored = {str(item) for item in normalization_species}
    if proton_water_policy == "ignore":
        ignored.update({"h", "h2o", "proton", "water"})
    for metabolite, coefficient in reaction.metabolites.items():
        identifier = mapping.get(str(metabolite.id), str(metabolite.id))
        normalized_identifier = str(identifier).lower()
        if normalized_identifier in ignored or any(
            normalized_identifier.startswith(f"{item.lower()}_") for item in ignored
        ):
            continue
        result[identifier] += float(coefficient)
    return {key: value for key, value in sorted(result.items()) if abs(value) > 1e-12}


def compare_reaction_identity(
    reaction: Any,
    target: Mapping[str, float],
    *,
    metabolite_mapping: Mapping[str, str] | None = None,
    allow_reversal: bool = True,
    proton_water_policy: str = "strict",
    normalization_species: Iterable[str] = (),
) -> ReactionIdentity:
    observed = normalized_stoichiometry(
        reaction,
        metabolite_mapping,
        proton_water_policy=proton_water_policy,
        normalization_species=normalization_species,
    )
    ignored = {str(item).lower() for item in normalization_species}
    if proton_water_policy == "ignore":
        ignored.update({"h", "h2o", "proton", "water"})
    expected = {
        str(k): float(v)
        for k, v in target.items()
        if abs(float(v)) > 1e-12
        and str(k).lower() not in ignored
        and not any(str(k).lower().startswith(f"{item}_") for item in ignored)
    }
    if observed == expected:
        return ReactionIdentity(
            "exact",
            observed,
            False,
            "normalized stoichiometry matches",
            proton_water_policy,
        )
    reversed_target = {key: -value for key, value in expected.items()}
    if allow_reversal and observed == reversed_target:
        return ReactionIdentity(
            "equivalent-reversed",
            observed,
            True,
            "normalized stoichiometry is reversed",
            proton_water_policy,
        )
    if set(observed) == set(expected):
        return ReactionIdentity(
            "conflict",
            observed,
            False,
            "species match but coefficients differ",
            proton_water_policy,
        )
    return ReactionIdentity(
        "no-match",
        observed,
        False,
        f"normalized species differ; policy={proton_water_policy}",
        proton_water_policy,
    )


def _compare_reaction_identity_payload(
    payload: tuple[
        tuple[object, ...],
        Mapping[str, float],
        Mapping[str, str],
        str,
        tuple[str, ...],
    ]
) -> ReactionIdentity:
    reaction, target, metabolite_mapping, proton_water_policy, normalization_species = (
        payload
    )
    return compare_reaction_identity(
        _reaction_from_payload(reaction),
        target,
        metabolite_mapping=metabolite_mapping,
        proton_water_policy=proton_water_policy,
        normalization_species=normalization_species,
    )


def reaction_identity_key(
    reaction: Any, *, metabolite_mapping: Mapping[str, str] | None = None
) -> tuple[tuple[str, float], ...]:
    return tuple(normalized_stoichiometry(reaction, metabolite_mapping).items())


def duplicate_reaction_groups(
    model: Any, *, metabolite_mapping: Mapping[str, str] | None = None
) -> tuple[tuple[str, ...], ...]:
    """Return deterministic groups of reactions with identical chemistry.

    Bounds, GPRs, and annotations are intentionally not part of this key:
    this helper identifies duplicate chemistry, while cleanup decides whether
    two records are safe to consolidate.
    """
    groups: dict[tuple[tuple[str, float], ...], list[str]] = defaultdict(list)
    for reaction in model.reactions:
        groups[
            reaction_identity_key(reaction, metabolite_mapping=metabolite_mapping)
        ].append(str(reaction.id))
    return tuple(
        tuple(sorted(ids))
        for ids in sorted(groups.values(), key=lambda values: tuple(sorted(values)))
        if len(ids) > 1
    )


@dataclass(frozen=True)
class BalanceAudit:
    reaction_id: str
    reaction_class: str
    mass_status: str
    charge_status: str
    mass_residual: Mapping[str, float]
    charge_residual: float | None
    missing_formula: tuple[str, ...] = ()
    missing_charge: tuple[str, ...] = ()
    invalid_formula: tuple[str, ...] = ()
    formula_classes: tuple[str, ...] = ()
    formula_policy: Mapping[str, str] = field(default_factory=dict)

    @property
    def status(self) -> str:
        return (
            self.mass_status if self.mass_status != "balanced" else self.charge_status
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "reaction_id": self.reaction_id,
            "reaction_class": self.reaction_class,
            "mass_status": self.mass_status,
            "charge_status": self.charge_status,
            "status": self.status,
            "mass_residual": dict(self.mass_residual),
            "charge_residual": self.charge_residual,
            "missing_formula": list(self.missing_formula),
            "missing_charge": list(self.missing_charge),
            "invalid_formula": list(self.invalid_formula),
            "formula_classes": list(self.formula_classes),
            "formula_policy": dict(self.formula_policy),
        }


def is_unresolved_balance(audit: BalanceAudit) -> bool:
    """Return whether an audit needs an exception or further curation."""
    excluded = {
        "excluded-boundary",
        "excluded-biomass",
        "excluded-pseudo-reaction",
        "excluded-generic-formula",
    }
    return audit.mass_status not in {
        "balanced",
        *excluded,
    } or audit.charge_status not in {"balanced", *excluded}


def formula_class(metabolite: Any) -> str | None:
    """Classify generic chemical notation for an explicit audit policy."""
    annotation = getattr(metabolite, "annotation", {}) or {}
    if isinstance(annotation, Mapping):
        declared = annotation.get("thg_formula_class") or annotation.get(
            "formula_class"
        )
        if declared:
            return str(declared).strip().lower()
    name = str(getattr(metabolite, "name", "") or "").lower()
    formula = str(getattr(metabolite, "formula", "") or "")
    if "glycan" in name or "oligosaccharide" in name:
        return "glycan"
    if (
        "polymer" in name
        or "polysaccharide" in name
        or "*" in formula
        or re.search(r"[0-9)]n$", formula)
    ):
        return "polymer"
    if re.search(r"(?:^|\d)R(?:\d|$)", formula):
        return "r-group"
    if re.search(r"(?:^|\d)X(?:\d|$)", formula):
        return "x-group"
    if re.search(r"(?:^|\d)(?:R|X)(?:\d|$)", formula):
        return "generic-group"
    return None


def audit_reaction(
    reaction: Any,
    *,
    formula_policy: Mapping[str, str] | None = None,
) -> BalanceAudit:
    reaction_class = classify_reaction(reaction)
    excluded = {
        "boundary": "excluded-boundary",
        "exchange": "excluded-boundary",
        "demand": "excluded-boundary",
        "sink": "excluded-boundary",
        "biomass": "excluded-biomass",
        "pseudo": "excluded-pseudo-reaction",
    }
    if reaction_class in excluded:
        return BalanceAudit(
            str(reaction.id),
            reaction_class,
            excluded[reaction_class],
            excluded[reaction_class],
            {},
            None,
        )
    missing_formula = tuple(
        sorted(
            str(m.id)
            for m in reaction.metabolites
            if not str(getattr(m, "formula", "") or "").strip()
        )
    )
    generic = tuple(
        sorted(
            str(m.id)
            for m in reaction.metabolites
            if re.search(
                r"(?:^|\d)(?:R|X)(?:\d|$)", str(getattr(m, "formula", "") or "")
            )
        )
    )
    formula_classes = tuple(
        sorted(
            {
                item
                for metabolite in reaction.metabolites
                for item in (
                    formula_class(metabolite),
                    "r-group"
                    if re.search(
                        r"(?:^|\d)R(?:\d|$)",
                        str(getattr(metabolite, "formula", "") or ""),
                    )
                    else None,
                    "x-group"
                    if re.search(
                        r"(?:^|\d)X(?:\d|$)",
                        str(getattr(metabolite, "formula", "") or ""),
                    )
                    else None,
                )
                if item is not None
            }
        )
    )
    selected_policy = (
        {
            str(key): str(value) for key, value in formula_policy.items()
        }
        if formula_policy is not None
        else dict(DEFAULT_FORMULA_POLICY)
    )
    invalid_policies = set(selected_policy.values()) - GENERIC_FORMULA_POLICIES
    if invalid_policies:
        raise ValueError(
            "generic formula policies must be 'flag' or 'exclude': "
            + ", ".join(sorted(invalid_policies))
        )
    invalid_formula = tuple(
        sorted(
            str(m.id)
            for m in reaction.metabolites
            if str(getattr(m, "formula", "") or "").strip()
            and not formula_atoms(str(getattr(m, "formula", "")))
        )
    )
    missing_charge = tuple(
        sorted(
            str(m.id)
            for m in reaction.metabolites
            if getattr(m, "charge", None) is None
        )
    )
    excluded_generic = tuple(
        item for item in formula_classes if selected_policy.get(item) == "exclude"
    )
    if missing_formula:
        mass_status = "not-evaluable-missing-formula"
    elif excluded_generic:
        mass_status = "excluded-generic-formula"
    elif generic or invalid_formula:
        mass_status = "not-evaluable-generic-formula"
    else:
        residual = reaction_balance(reaction)
        mass_status = "balanced" if not residual else "unbalanced"
    if missing_charge:
        charge_status = "not-evaluable-missing-charge"
        charge_residual = None
    else:
        charge_residual = sum(
            float(coefficient) * float(metabolite.charge)
            for metabolite, coefficient in reaction.metabolites.items()
        )
        charge_status = "balanced" if abs(charge_residual) <= 1e-9 else "unbalanced"
    residual = reaction_balance(reaction) if mass_status == "unbalanced" else {}
    return BalanceAudit(
        str(reaction.id),
        reaction_class,
        mass_status,
        charge_status,
        residual,
        charge_residual,
        missing_formula,
        missing_charge,
        invalid_formula,
        formula_classes,
        selected_policy,
    )


class _MetaboliteView:
    __slots__ = ("id", "name", "formula", "charge", "compartment", "annotation")

    def __init__(
        self,
        identifier: str,
        name: str,
        formula: str,
        charge: int | None,
        compartment: str,
        annotation: Mapping[str, object],
    ) -> None:
        self.id = identifier
        self.name = name
        self.formula = formula
        self.charge = charge
        self.compartment = compartment
        self.annotation = dict(annotation)

    __hash__ = object.__hash__


def _reaction_payload(reaction: Any) -> tuple[object, ...]:
    return (
        str(reaction.id),
        str(getattr(reaction, "name", "") or ""),
        bool(getattr(reaction, "boundary", False)),
        str(getattr(reaction, "gene_reaction_rule", "") or ""),
        tuple(
            (
                str(metabolite.id),
                str(getattr(metabolite, "name", "") or ""),
                str(getattr(metabolite, "formula", "") or ""),
                getattr(metabolite, "charge", None),
                str(getattr(metabolite, "compartment", "") or ""),
                dict(getattr(metabolite, "annotation", {}) or {}),
                float(coefficient),
            )
            for metabolite, coefficient in reaction.metabolites.items()
        ),
    )


def _reaction_from_payload(payload: tuple[object, ...]) -> SimpleNamespace:
    identifier, name, boundary, gene_reaction_rule, metabolite_payloads = payload
    metabolites = {}
    for (
        metabolite_id,
        metabolite_name,
        formula,
        charge,
        compartment,
        annotation,
        coefficient,
    ) in metabolite_payloads:
        metabolite = _MetaboliteView(
            str(metabolite_id),
            str(metabolite_name),
            str(formula),
            charge,
            str(compartment),
            annotation,
        )
        metabolites[metabolite] = float(coefficient)
    return SimpleNamespace(
        id=str(identifier),
        name=str(name),
        boundary=bool(boundary),
        gene_reaction_rule=str(gene_reaction_rule),
        metabolites=metabolites,
    )


def _audit_reaction_payload(
    payload: tuple[tuple[object, ...], Mapping[str, str]],
) -> BalanceAudit:
    reaction, formula_policy = payload
    return audit_reaction(
        _reaction_from_payload(reaction), formula_policy=formula_policy
    )


def audit_model(
    model: Any,
    *,
    formula_policy: Mapping[str, str] | None = None,
    n_jobs: int = 1,
) -> tuple[BalanceAudit, ...]:
    if isinstance(n_jobs, bool) or not isinstance(n_jobs, int) or n_jobs < 1:
        raise ValueError("n_jobs must be a positive integer")
    reactions = tuple(sorted(model.reactions, key=lambda item: str(item.id)))
    if n_jobs == 1:
        return tuple(
            audit_reaction(reaction, formula_policy=formula_policy)
            for reaction in reactions
        )
    selected_policy = (
        DEFAULT_FORMULA_POLICY if formula_policy is None else formula_policy
    )
    payloads = tuple(
        (_reaction_payload(reaction), dict(selected_policy))
        for reaction in reactions
    )
    del reactions, model
    return parallel_map(_audit_reaction_payload, payloads, n_jobs=n_jobs)


def _affected_audits(model: Any, metabolite_id: str) -> list[dict[str, object]]:
    return [
        audit_reaction(reaction).to_dict()
        for reaction in sorted(
            model.metabolites.get_by_id(metabolite_id).reactions,
            key=lambda item: str(item.id),
        )
    ]


def _reaction_audit_view(
    reaction: Any, stoichiometry: Mapping[str, float], model: Any
) -> Any:
    """Build a lightweight reaction view for proposal-only balance audits."""
    metabolites = {
        model.metabolites.get_by_id(str(metabolite_id)): float(coefficient)
        for metabolite_id, coefficient in stoichiometry.items()
    }
    return SimpleNamespace(
        id=str(reaction.id),
        name=getattr(reaction, "name", ""),
        boundary=bool(getattr(reaction, "boundary", False)),
        gene_reaction_rule=getattr(reaction, "gene_reaction_rule", ""),
        metabolites=metabolites,
    )


def _corrected_model(
    model: Any,
    *,
    formula: Mapping[str, str] | None = None,
    charge: Mapping[str, int] | None = None,
) -> Any:
    copied = model.copy()
    for metabolite_id, value in (formula or {}).items():
        copied.metabolites.get_by_id(metabolite_id).formula = str(value)
    for metabolite_id, value in (charge or {}).items():
        copied.metabolites.get_by_id(metabolite_id).charge = int(value)
    return copied


def generate_balance_proposals(
    model: Any,
    *,
    corrections: Mapping[str, Mapping[str, float]] | None = None,
    formula_corrections: Mapping[str, str] | None = None,
    charge_corrections: Mapping[str, int] | None = None,
    strategy: str = DEFAULT_BALANCE_STRATEGY,
) -> tuple[Proposal, ...]:
    """Create balance proposals using only verified proton/water repairs by default."""
    if strategy not in {"explicit-only", "proton-water"}:
        raise ValueError("strategy must be 'explicit-only' or 'proton-water'")
    proposals: list[Proposal] = []
    species_by_compartment: dict[str, tuple[Any | None, Any | None]] = {}
    if strategy == "proton-water":
        water_candidates: defaultdict[str, list[Any]] = defaultdict(list)
        proton_candidates: defaultdict[str, list[Any]] = defaultdict(list)
        for metabolite in model.metabolites:
            compartment = str(getattr(metabolite, "compartment", ""))
            atoms = formula_atoms(str(getattr(metabolite, "formula", "") or ""))
            if atoms == {"H": 2, "O": 1} and getattr(metabolite, "charge", None) == 0:
                water_candidates[compartment].append(metabolite)
            elif atoms == {"H": 1} and getattr(metabolite, "charge", None) in {-1, 1}:
                proton_candidates[compartment].append(metabolite)
        for compartment in set(water_candidates) | set(proton_candidates):
            water = min(
                water_candidates.get(compartment, ()),
                key=lambda item: str(item.id),
                default=None,
            )
            proton = min(
                proton_candidates.get(compartment, ()),
                key=lambda item: str(item.id),
                default=None,
            )
            species_by_compartment[compartment] = (water, proton)
    for reaction in sorted(model.reactions, key=lambda item: str(item.id)):
        rid = str(reaction.id)
        if strategy == "proton-water" and not corrections:
            automatic = _proton_water_correction(
                model, reaction, species_by_compartment=species_by_compartment
            )
            if automatic is not None:
                (
                    before,
                    after,
                    trial_reaction,
                    changed_species,
                    before_audit,
                    after_audit,
                ) = automatic
                proposals.append(
                    Proposal(
                        proposal_id=proposal_id(
                            operation="adjust-stoichiometry",
                            object_type="reaction",
                            object_id=rid,
                            before=before,
                            after=after,
                        ),
                        operation="adjust-stoichiometry",
                        object_type="reaction",
                        object_id=rid,
                        before=before,
                        after=after,
                        evidence=(f"configured-strategy:{strategy}",),
                        confidence="configured-chemical-strategy",
                        policy=strategy,
                        stage="beta1-balance-proposals",
                        reason="added only proton/water species required by residuals",
                        metadata={
                            "imbalance_before": before_audit.to_dict(),
                            "imbalance_after": after_audit.to_dict(),
                            "changed_species": changed_species,
                            "semantic_impact": (
                                "stoichiometry and solver behavior may change"
                            ),
                        },
                    )
                )
        if corrections and rid in corrections:
            before = normalized_stoichiometry(reaction)
            after = dict(before)
            for metabolite_id, coefficient in corrections[rid].items():
                after[metabolite_id] = after.get(metabolite_id, 0.0) + float(
                    coefficient
                )
                if abs(after[metabolite_id]) <= 1e-12:
                    del after[metabolite_id]
            trial_reaction = _reaction_audit_view(reaction, after, model)
            proposals.append(
                Proposal(
                    proposal_id=proposal_id(
                        operation="adjust-stoichiometry",
                        object_type="reaction",
                        object_id=rid,
                        before=before,
                        after=after,
                    ),
                    operation="adjust-stoichiometry",
                    object_type="reaction",
                    object_id=rid,
                    before=before,
                    after=after,
                    evidence=(f"explicit-correction:{rid}",),
                    confidence="configured",
                    policy=strategy,
                    stage="beta1-balance-proposals",
                    reason="configured chemical correction",
                    metadata={
                        "imbalance_before": audit_reaction(reaction).to_dict(),
                        "imbalance_after": audit_reaction(trial_reaction).to_dict(),
                        "changed_species": sorted(set(before) | set(after)),
                        "semantic_impact": (
                            "stoichiometry and solver behavior may change"
                        ),
                    },
                )
            )
    for metabolite_id, formula in sorted((formula_corrections or {}).items()):
        metabolite = model.metabolites.get_by_id(metabolite_id)
        before, after = getattr(metabolite, "formula", None), str(formula)
        proposals.append(
            Proposal(
                proposal_id=proposal_id(
                    operation="correct-formula",
                    object_type="metabolite",
                    object_id=metabolite_id,
                    before=before,
                    after=after,
                ),
                operation="correct-formula",
                object_type="metabolite",
                object_id=metabolite_id,
                before=before,
                after=after,
                evidence=(f"explicit-correction:{metabolite_id}",),
                confidence="configured",
                policy=strategy,
                stage="beta1-balance-proposals",
                reason="configured formula correction",
                metadata={
                    "imbalance_before": _affected_audits(model, metabolite_id),
                    "imbalance_after": _affected_audits(
                        _corrected_model(model, formula={metabolite_id: after}),
                        metabolite_id,
                    ),
                    "semantic_impact": "formula balance and mass totals may change",
                },
            )
        )
    for metabolite_id, charge in sorted((charge_corrections or {}).items()):
        metabolite = model.metabolites.get_by_id(metabolite_id)
        before, after = getattr(metabolite, "charge", None), int(charge)
        proposals.append(
            Proposal(
                proposal_id=proposal_id(
                    operation="correct-charge",
                    object_type="metabolite",
                    object_id=metabolite_id,
                    before=before,
                    after=after,
                ),
                operation="correct-charge",
                object_type="metabolite",
                object_id=metabolite_id,
                before=before,
                after=after,
                evidence=(f"explicit-correction:{metabolite_id}",),
                confidence="configured",
                policy=strategy,
                stage="beta1-balance-proposals",
                reason="configured charge correction",
                metadata={
                    "imbalance_before": _affected_audits(model, metabolite_id),
                    "imbalance_after": _affected_audits(
                        _corrected_model(model, charge={metabolite_id: after}),
                        metabolite_id,
                    ),
                    "semantic_impact": "charge balance and solver behavior may change",
                },
            )
        )
    return tuple(proposals)


def _proton_water_correction(
    model: Any,
    reaction: Any,
    *,
    species_by_compartment: Mapping[str, tuple[Any | None, Any | None]] | None = None,
) -> (
    tuple[
        dict[str, float],
        dict[str, float],
        Any,
        list[str],
        BalanceAudit,
        BalanceAudit,
    ]
    | None
):
    """Return a conservative H/H2O repair when the residual is solvable.

    This strategy is deliberately narrower than a general-purpose balancer:
    it only acts on evaluable internal reactions whose residual elements are H
    and O and for which local proton and water species are present.  A repair
    is proposed only when both elemental and charge residuals are removed.
    """
    audit = audit_reaction(reaction)
    if audit.mass_status != "unbalanced" or audit.charge_status != "unbalanced":
        return None
    if set(audit.mass_residual) - {"H", "O"}:
        return None
    compartments = {
        str(getattr(metabolite, "compartment", ""))
        for metabolite in reaction.metabolites
    }
    if len(compartments) != 1:
        return None
    compartment = next(iter(compartments))
    if species_by_compartment is not None:
        water, proton = species_by_compartment.get(compartment, (None, None))
    else:
        local = [
            metabolite
            for metabolite in model.metabolites
            if str(getattr(metabolite, "compartment", "")) == compartment
        ]
        water = next(
            (
                metabolite
                for metabolite in sorted(local, key=lambda item: str(item.id))
                if formula_atoms(str(getattr(metabolite, "formula", "") or ""))
                == {"H": 2, "O": 1}
                and getattr(metabolite, "charge", None) == 0
            ),
            None,
        )
        proton = next(
            (
                metabolite
                for metabolite in sorted(local, key=lambda item: str(item.id))
                if formula_atoms(str(getattr(metabolite, "formula", "") or ""))
                == {"H": 1}
                and getattr(metabolite, "charge", None) in {-1, 1}
            ),
            None,
        )
    if water is None or proton is None:
        return None
    water_coefficient = -float(audit.mass_residual.get("O", 0.0))
    proton_coefficient = -float(audit.charge_residual or 0.0) / float(proton.charge)
    expected_proton = -float(audit.mass_residual.get("H", 0.0)) - 2.0 * (
        water_coefficient
    )
    if abs(proton_coefficient - expected_proton) > 1e-9:
        return None
    if abs(water_coefficient) <= 1e-12 and abs(proton_coefficient) <= 1e-12:
        return None
    before = normalized_stoichiometry(reaction)
    after = dict(before)
    for metabolite, coefficient in (
        (water, water_coefficient),
        (proton, proton_coefficient),
    ):
        after[str(metabolite.id)] = after.get(str(metabolite.id), 0.0) + coefficient
        if abs(after[str(metabolite.id)]) <= 1e-12:
            del after[str(metabolite.id)]
    trial_reaction = _reaction_audit_view(reaction, after, model)
    corrected = audit_reaction(trial_reaction)
    if corrected.mass_status != "balanced" or corrected.charge_status != "balanced":
        return None
    return (
        before,
        after,
        trial_reaction,
        sorted({str(water.id), str(proton.id)}),
        audit,
        corrected,
    )


def apply_model_proposals(
    model: Any,
    proposals: Iterable[Proposal],
    *,
    mode: str = "apply-all",
    decisions: Iterable[Decision] = (),
) -> tuple[Any, tuple[dict[str, object], ...]]:
    """Apply a previously persisted proposal set to a copied model."""
    copied = model.copy()
    _, ledger = apply_proposals(
        proposals,
        mode=mode,
        decisions=decisions,
        apply=lambda item, value: _apply_model_proposal(copied, item, value),
    )
    return copied, ledger


def _apply_model_proposal(model: Any, proposal: Proposal, replacement: object) -> None:
    if proposal.object_type == "metabolite":
        metabolite = model.metabolites.get_by_id(proposal.object_id)
        if proposal.operation == "correct-formula":
            metabolite.formula = str(replacement)
        elif proposal.operation == "correct-charge":
            metabolite.charge = int(replacement)
        elif proposal.operation == "annotate-identity":
            metabolite.annotation = dict(replacement)  # type: ignore[arg-type]
        else:
            raise ValueError(f"unsupported metabolite operation: {proposal.operation}")
        return
    if proposal.object_type != "reaction":
        raise ValueError(f"unsupported proposal operation: {proposal.operation}")
    reaction = model.reactions.get_by_id(proposal.object_id)
    if proposal.operation == "rewrite-gpr":
        reaction.gene_reaction_rule = str(replacement)
        return
    if proposal.operation in {
        "flag-reaction-identity",
        "flag-reaction-directionality",
        "annotate-s-gpr",
    }:
        # Annotation proposals are independently auditable.  Merge their
        # namespaces at application time so two valid evidence records for the
        # same reaction cannot erase one another on sequential application.
        incoming = dict(replacement)  # type: ignore[arg-type]
        current = dict(getattr(reaction, "annotation", {}) or {})
        current.update(incoming)
        reaction.annotation = current
        return
    if proposal.operation != "adjust-stoichiometry":
        raise ValueError(f"unsupported reaction operation: {proposal.operation}")
    desired = {str(key): float(value) for key, value in dict(replacement).items()}
    current = {str(m.id): float(c) for m, c in reaction.metabolites.items()}
    delta = defaultdict(float, desired)
    for key, coefficient in current.items():
        delta[key] -= coefficient
    reaction.add_metabolites(
        {
            model.metabolites.get_by_id(key): value
            for key, value in delta.items()
            if abs(value) > 1e-12
        }
    )


def consolidate_model(
    model: Any,
    *,
    remove_isolated: bool = False,
    gene_mapping: Mapping[str, str] | None = None,
) -> tuple[Any, dict[str, object]]:
    """Return a deterministic copy with exact duplicate chemistry consolidated."""
    copied = model.copy()
    metabolite_groups: dict[tuple[object, ...], list[Any]] = defaultdict(list)
    for metabolite in copied.metabolites:
        identity_by_namespace: dict[str, tuple[str, ...]] = defaultdict(tuple)
        for namespace, value in _annotation_values(metabolite):
            if namespace.lower() in {
                "chebi",
                "kegg",
                "pubchem",
                "inchi",
                "inchikey",
                "smiles",
            }:
                identity_by_namespace[namespace.lower()] = tuple(
                    sorted(
                        set(identity_by_namespace.get(namespace.lower(), ()))
                        | {str(value)}
                    )
                )
        identity_values = ()
        for namespace in ("inchi", "inchikey", "smiles", "chebi", "kegg", "pubchem"):
            if namespace in identity_by_namespace:
                identity_values = ((namespace, identity_by_namespace[namespace]),)
                break
        # Formula/charge/compartment agreement alone does not establish
        # chemical identity.  Generic or unannotated records remain separate
        # until an explicit identity mapping is supplied.
        if not identity_values:
            continue
        key = (
            str(getattr(metabolite, "compartment", "")),
            getattr(metabolite, "formula", None),
            getattr(metabolite, "charge", None),
            identity_values,
        )
        metabolite_groups[key].append(metabolite)
    retained: dict[str, str] = {}
    removed_metabolites: list[str] = []
    for group in metabolite_groups.values():
        group.sort(key=lambda item: str(item.id))
        keep = group[0]
        for duplicate in group[1:]:
            retained[str(duplicate.id)] = str(keep.id)
            removed_metabolites.append(str(duplicate.id))
            # Merge annotations and retain the lexically stable non-empty name
            # so consolidation does not discard provenance from either record.
            keep.annotation = _merge_annotations(
                getattr(keep, "annotation", {}),
                getattr(duplicate, "annotation", {}),
            )
            names = sorted(
                name
                for name in (
                    str(getattr(keep, "name", "") or ""),
                    str(getattr(duplicate, "name", "") or ""),
                )
                if name
            )
            if names:
                keep.name = names[0]
    # Remap group membership before removing duplicate metabolites.  COBRA
    # groups hold object references, so removing the metabolite alone leaves a
    # dangling member that is invisible to reaction-reference checks.
    for group_object in getattr(copied, "groups", ()):
        for member in tuple(getattr(group_object, "members", ())):
            replacement_id = retained.get(str(getattr(member, "id", "")))
            if replacement_id is None:
                continue
            replacement = copied.metabolites.get_by_id(replacement_id)
            try:
                group_object.remove_members([member])
                if replacement not in group_object.members:
                    group_object.add_members([replacement])
            except AttributeError:
                continue
    for reaction in copied.reactions:
        changes = defaultdict(float)
        for metabolite, coefficient in reaction.metabolites.items():
            target = copied.metabolites.get_by_id(
                retained.get(str(metabolite.id), str(metabolite.id))
            )
            changes[target] += float(coefficient)
        reaction.add_metabolites(
            {
                metabolite: -float(coefficient)
                for metabolite, coefficient in reaction.metabolites.items()
            }
        )
        reaction.add_metabolites(
            {
                metabolite: coefficient
                for metabolite, coefficient in changes.items()
                if abs(coefficient) > 1e-12
            }
        )
    for identifier in sorted(removed_metabolites):
        copied.metabolites.remove(copied.metabolites.get_by_id(identifier))
    removed_genes: list[str] = []
    normalized_gene_mapping = normalize_gene_mapping(gene_mapping or {})
    if normalized_gene_mapping:
        for reaction in copied.reactions:
            if reaction.gene_reaction_rule:
                reaction.gene_reaction_rule = rewrite_gpr(
                    reaction.gene_reaction_rule, normalized_gene_mapping
                )
        for alias, target in sorted(normalized_gene_mapping.items()):
            if alias == target:
                continue
            try:
                copied.genes.get_by_id(alias)
            except KeyError:
                continue
            removed_genes.append(alias)
            copied.genes.remove(copied.genes.get_by_id(alias))
    reaction_groups: dict[tuple[object, ...], list[Any]] = defaultdict(list)
    for reaction in copied.reactions:
        reaction_groups[
            (
                reaction_identity_key(reaction),
                float(reaction.lower_bound),
                float(reaction.upper_bound),
                json.dumps(
                    canonicalize_gpr(str(reaction.gene_reaction_rule)).to_dict(),
                    sort_keys=True,
                )
                if reaction.gene_reaction_rule
                else None,
            )
        ].append(reaction)
    removed_reactions: list[str] = []
    retained_reactions: dict[str, str] = {}
    for group in reaction_groups.values():
        group.sort(key=lambda item: str(item.id))
        keep = group[0]
        for duplicate in group[1:]:
            retained_reactions[str(duplicate.id)] = str(keep.id)
            keep.annotation = _merge_annotations(
                getattr(keep, "annotation", {}),
                getattr(duplicate, "annotation", {}),
            )
            names = sorted(
                name
                for name in (
                    str(getattr(keep, "name", "") or ""),
                    str(getattr(duplicate, "name", "") or ""),
                )
                if name
            )
            if names:
                keep.name = names[0]
            # Preserve objective semantics when duplicate reactions carry
            # separate non-zero objective coefficients.
            try:
                coefficients = copied.objective.get_linear_coefficients(
                    [
                        keep.forward_variable,
                        keep.reverse_variable,
                        duplicate.forward_variable,
                        duplicate.reverse_variable,
                    ]
                )
                keep_coefficient = float(
                    coefficients.get(keep.forward_variable, 0.0)
                ) - float(coefficients.get(keep.reverse_variable, 0.0))
                duplicate_coefficient = float(
                    coefficients.get(duplicate.forward_variable, 0.0)
                ) - float(coefficients.get(duplicate.reverse_variable, 0.0))
                if keep_coefficient or duplicate_coefficient:
                    copied.objective.set_linear_coefficients(
                        {
                            keep.forward_variable: keep_coefficient
                            + duplicate_coefficient,
                            keep.reverse_variable: 0.0,
                            duplicate.forward_variable: 0.0,
                            duplicate.reverse_variable: 0.0,
                        }
                    )
            except (AttributeError, TypeError):
                pass
            for group_object in getattr(copied, "groups", ()):
                members = getattr(group_object, "members", ())
                if duplicate in members:
                    try:
                        group_object.remove_members([duplicate])
                        group_object.add_members([keep])
                    except AttributeError:
                        pass
            removed_reactions.append(str(duplicate.id))
            copied.reactions.remove(duplicate)
    removed_orphans: list[str] = []
    if remove_isolated:
        for metabolite in list(copied.metabolites):
            if not metabolite.reactions:
                for group_object in getattr(copied, "groups", ()):
                    try:
                        if metabolite in group_object.members:
                            group_object.remove_members([metabolite])
                    except AttributeError:
                        continue
                removed_orphans.append(str(metabolite.id))
                copied.metabolites.remove(metabolite)
    return copied, {
        "retained_metabolites": retained,
        "removed_metabolites": sorted(removed_metabolites),
        "retained_reactions": retained_reactions,
        "removed_reactions": sorted(removed_reactions),
        "gene_mapping": normalized_gene_mapping,
        "removed_genes": sorted(removed_genes),
        "removed_isolated_metabolites": sorted(removed_orphans),
    }


def _empty_cleanup_report() -> dict[str, object]:
    return {
        "retained_metabolites": {},
        "removed_metabolites": [],
        "retained_reactions": {},
        "removed_reactions": [],
        "gene_mapping": {},
        "removed_genes": [],
        "removed_isolated_metabolites": [],
    }


def generate_cleanup_proposals(
    model: Any,
    *,
    remove_isolated: bool = False,
    gene_mapping: Mapping[str, str] | None = None,
) -> tuple[tuple[Proposal, ...], dict[str, object]]:
    """Propose deterministic cleanup without mutating the supplied model."""
    candidate, report = consolidate_model(
        model,
        remove_isolated=remove_isolated,
        gene_mapping=gene_mapping,
    )
    before = model_signature(model)
    after = model_signature(candidate)
    if before == after:
        return (), report
    proposal = Proposal(
        proposal_id=proposal_id(
            operation="consolidate-model",
            object_type="model",
            object_id=str(model.id),
            before=before,
            after=after,
        ),
        operation="consolidate-model",
        object_type="model",
        object_id=str(model.id),
        before=before,
        after=after,
        evidence=(f"model-signature:{model.id}",),
        confidence="deterministic-policy",
        policy="deterministic-cleanup",
        stage="beta1-deduplicate-and-clean",
        reason="consolidate exact duplicate chemistry and configured isolated objects",
        metadata={
            "remove_isolated": bool(remove_isolated),
            "gene_mapping": dict(gene_mapping or {}),
            "cleanup_report": _json(report),
        },
    )
    return (proposal,), report


def apply_cleanup_proposals(
    model: Any,
    proposals: Iterable[Proposal],
    *,
    mode: str = "apply-all",
    decisions: Iterable[Decision] = (),
) -> tuple[Any, tuple[dict[str, object], ...], dict[str, object]]:
    """Apply persisted cleanup proposals to a copied model under policy."""
    state = [model.copy()]
    report: dict[str, object] = _empty_cleanup_report()

    def apply(item: Proposal, replacement: object) -> None:
        del replacement
        metadata = item.metadata
        cleaned, cleanup_report = consolidate_model(
            state[0],
            remove_isolated=bool(metadata.get("remove_isolated", False)),
            gene_mapping=(
                metadata.get("gene_mapping", {})
                if isinstance(metadata.get("gene_mapping", {}), Mapping)
                else {}
            ),
        )
        state[0] = cleaned
        report.update(cleanup_report)

    _, ledger = apply_proposals(
        proposals,
        mode=mode,
        decisions=decisions,
        apply=apply,
    )
    return state[0], ledger, report


def _load_model(path: Path) -> Any:
    from cobra.io import load_json_model, read_sbml_model

    return (
        load_json_model(str(path))
        if path.suffix.lower() == ".json"
        else read_sbml_model(str(path))
    )


def _semantic_ledger_entries(
    before: Any,
    after: Any,
    existing: Iterable[Mapping[str, object]],
) -> tuple[dict[str, object], ...]:
    """Record cleanup changes that are not represented by proposals."""
    from thg_protocol.analysis.model_signature import diff_model_signatures

    diff = diff_model_signatures(model_signature(before), model_signature(after))
    known = {str(item.get("object_id")) for item in existing}
    entries: list[dict[str, object]] = []
    for collection in ("metabolites", "reactions", "genes", "groups", "objective"):
        identifiers = list(diff["added"].get(collection, []))
        identifiers.extend(diff["removed"].get(collection, []))
        identifiers.extend(item["id"] for item in diff["changed"].get(collection, []))
        for identifier in sorted({str(item) for item in identifiers} - known):
            entries.append(
                {
                    "operation": "semantic-diff",
                    "object_type": collection,
                    "object_id": identifier,
                    "status": "applied",
                    "reason": "derived object change from deterministic cleanup",
                }
            )
    return tuple(entries)


def run_beta1(
    input_model: str | Path,
    output_dir: str | Path,
    *,
    mode: str = "apply-all",
    balance_strategy: str = DEFAULT_BALANCE_STRATEGY,
    corrections: Mapping[str, Mapping[str, float]] | None = None,
    formula_corrections: Mapping[str, str] | None = None,
    charge_corrections: Mapping[str, int] | None = None,
    decisions: Iterable[Decision] = (),
    remove_isolated: bool = False,
    sanctioned_model: bool = False,
    metabolite_identities: Mapping[str, Mapping[str, object]] = {},
    gene_mapping: Mapping[str, str] = {},
    reaction_identities: Mapping[str, Mapping[str, object]] = {},
    formula_policy: Mapping[str, str] | None = None,
    subunit_stoichiometry: Mapping[str, Mapping[str, float]] = {},
    run_solver_checks: bool = False,
    run_flux_consistency: bool = False,
) -> dict[str, object]:
    """Run the complete offline β1 curation core and write its artifact bundle."""
    source = Path(input_model).resolve()
    destination = Path(output_dir).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    decision_items = tuple(decisions)
    model = _load_model(source).copy()
    inventory = inventory_model(model, input_path=source)
    proposals = list(
        generate_curation_proposals(
            model,
            metabolite_identities=metabolite_identities,
            gene_mapping=gene_mapping,
            reaction_identities=reaction_identities,
            subunit_stoichiometry=subunit_stoichiometry,
        )
    )
    proposals.extend(
        generate_balance_proposals(
            model,
            corrections=corrections,
            formula_corrections=formula_corrections,
            charge_corrections=charge_corrections,
            strategy=balance_strategy,
        )
    )
    proposals = tuple(proposals)
    base_proposals = proposals
    prospective, _ = apply_model_proposals(
        model,
        proposals,
        mode=mode,
        decisions=decision_items,
    )
    cleanup_proposals, _ = generate_cleanup_proposals(
        prospective,
        remove_isolated=remove_isolated,
        gene_mapping=gene_mapping,
    )
    proposals = proposals + cleanup_proposals
    proposal_path = destination / "beta1-proposals.jsonl"
    write_proposals(proposal_path, proposals)
    applied_model, ledger = apply_model_proposals(
        model,
        base_proposals,
        mode=mode,
        decisions=decision_items,
    )
    cleanup_items = tuple(
        item for item in proposals if item.operation == "consolidate-model"
    )
    curated, cleanup_ledger, cleanup = apply_cleanup_proposals(
        applied_model,
        cleanup_items,
        mode=mode,
        decisions=decision_items,
    )
    ledger = tuple(ledger) + tuple(cleanup_ledger)
    ledger = tuple(ledger) + _semantic_ledger_entries(model, curated, ledger)
    ledger_path = destination / "beta1-change-ledger.jsonl"
    ledger_path.write_text(
        "\n".join(json.dumps(item, sort_keys=True) for item in ledger)
        + ("\n" if ledger else ""),
        encoding="utf-8",
    )
    decisions_path = destination / "beta1-decisions.jsonl"
    decisions_path.write_text(
        "\n".join(json.dumps(item.to_dict(), sort_keys=True) for item in decision_items)
        + ("\n" if decision_items else ""),
        encoding="utf-8",
    )
    audits = audit_model(curated, formula_policy=formula_policy)
    valid_gprs: list[str] = []
    invalid_gprs: list[dict[str, str]] = []
    for reaction in curated.reactions:
        if not reaction.gene_reaction_rule:
            continue
        try:
            parse_gpr(reaction.gene_reaction_rule)
        except ValueError as error:
            invalid_gprs.append({"reaction_id": str(reaction.id), "error": str(error)})
        else:
            valid_gprs.append(str(reaction.id))
    validation = {
        "schema_version": 1,
        "model_id": str(curated.id),
        "all_ids_unique": len({m.id for m in curated.metabolites})
        == len(curated.metabolites)
        and len({r.id for r in curated.reactions}) == len(curated.reactions),
        "valid_references": all(
            metabolite in curated.metabolites
            for reaction in curated.reactions
            for metabolite in reaction.metabolites
        ),
        "valid_gene_references": all(
            gene in curated.genes
            for reaction in curated.reactions
            for gene in reaction.genes
        ),
        "valid_gprs": valid_gprs,
        "invalid_gprs": invalid_gprs,
        "audits": [item.to_dict() for item in audits],
        "unresolved": [
            item.to_dict() for item in audits if is_unresolved_balance(item)
        ],
        "ledger_entries": len(ledger),
        "proposal_count": len(proposals),
    }
    from thg_protocol.analysis.model_signature import diff_model_signatures

    semantic_diff = diff_model_signatures(
        model_signature(model), model_signature(curated)
    )
    ledger_ids = {str(item.get("object_id")) for item in ledger}
    semantic_ids: set[str] = set()
    for collection in ("metabolites", "reactions", "genes", "groups", "objective"):
        semantic_ids.update(
            str(item) for item in semantic_diff["added"].get(collection, [])
        )
        semantic_ids.update(
            str(item) for item in semantic_diff["removed"].get(collection, [])
        )
        semantic_ids.update(
            str(item["id"]) for item in semantic_diff["changed"].get(collection, [])
        )
    validation.update(
        {
            "unique_ids": all(
                len(values) == len(set(values))
                for values in (
                    [str(item.id) for item in curated.metabolites],
                    [str(item.id) for item in curated.reactions],
                    [str(item.id) for item in curated.genes],
                    [str(item.id) for item in getattr(curated, "groups", ())],
                )
            ),
            "valid_groups": all(
                all(
                    member in curated.metabolites
                    or member in curated.reactions
                    or member in curated.genes
                    for member in group.members
                )
                for group in getattr(curated, "groups", ())
            ),
            "objective_valid": all(
                str(item["reaction"]) in {str(r.id) for r in curated.reactions}
                for item in model_signature(curated).get("objective", [])
            ),
            "compartment_count": len(getattr(curated, "compartments", {})),
            "no_systematic_compartment_expansion": set(
                getattr(curated, "compartments", {})
            )
            <= set(getattr(model, "compartments", {})),
            "ledger_agrees_with_semantic_diff": semantic_ids <= ledger_ids,
            "semantic_diff": semantic_diff,
            "unresolved_identity_conflicts": [
                {"object_id": object_id, **dict(result)}
                for object_id, result in metabolite_identities.items()
                if result.get("status") != "matched"
            ]
            + [
                {"object_id": object_id, **dict(result)}
                for object_id, result in reaction_identities.items()
                if result.get("status") not in {"exact", "equivalent-reversed"}
            ],
        }
    )
    if run_solver_checks:
        try:
            solution = curated.optimize()
            validation["solver"] = {
                "status": str(solution.status),
                "objective_value": float(solution.objective_value)
                if solution.objective_value is not None
                else None,
            }
        except Exception as error:  # pragma: no cover - solver-specific
            validation["solver"] = {
                "status": "error",
                "error": f"{type(error).__name__}: {error}",
            }
    if run_flux_consistency:
        try:
            from cobra.flux_analysis import find_blocked_reactions

            blocked = sorted(find_blocked_reactions(curated))
            validation["flux_consistency"] = {
                "method": "cobra.flux_analysis.find_blocked_reactions",
                "blocked_reactions": blocked,
                "consistent": not blocked,
            }
        except Exception as error:  # pragma: no cover - solver-specific
            validation["flux_consistency"] = {
                "status": "error",
                "error": f"{type(error).__name__}: {error}",
            }
    validation_path = destination / "beta1-validation.json"
    validation_path.write_text(
        json.dumps(validation, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    evidence_dir = destination / "evidence"
    mappings_dir = destination / "mappings"
    evidence_dir.mkdir(exist_ok=True)
    mappings_dir.mkdir(exist_ok=True)
    (evidence_dir / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "mode": "offline-normalized",
                "input_sha256": sha256_file(source),
                "records": [],
                "errors": [],
                "warnings": [],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    (mappings_dir / "identity-mappings.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "metabolites": {
                    object_id: resolution.get("selected")
                    for object_id, resolution in metabolite_identities.items()
                    if resolution.get("status") == "matched"
                },
                "reactions": {
                    object_id: dict(resolution)
                    for object_id, resolution in reaction_identities.items()
                    if resolution.get("status") in {"exact", "equivalent-reversed"}
                },
                "genes": dict(
                    sorted(
                        (str(key), str(value)) for key, value in gene_mapping.items()
                    )
                ),
                "unresolved": [
                    {
                        "object_id": object_id,
                        "status": resolution.get("status"),
                    }
                    for object_id, resolution in metabolite_identities.items()
                    if resolution.get("status") != "matched"
                ]
                + [
                    {"object_id": object_id, "status": resolution.get("status")}
                    for object_id, resolution in reaction_identities.items()
                    if resolution.get("status") not in {"exact", "equivalent-reversed"}
                ],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    json_path = destination / "thg-beta1-candidate.json"
    from cobra.io import save_json_model, write_sbml_model

    save_json_model(curated, str(json_path))
    sbml_path = destination / "thg-beta1-candidate.xml"
    write_sbml_model(curated, str(sbml_path))
    # Export/reload is part of the β1 validation boundary, not just an output
    # convenience: serialization failures must stop the run before release.
    _load_model(json_path)
    _load_model(sbml_path)
    signature = model_signature(curated)
    signature_path = destination / "beta1-signature.json"
    signature_path.write_text(
        json.dumps(signature, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    unresolved_path = destination / "beta1-unresolved.tsv"
    unresolved_path.write_text(
        "reaction_id\tmass_status\tcharge_status\n"
        + "\n".join(
            f"{item.reaction_id}\t{item.mass_status}\t{item.charge_status}"
            for item in audits
            if item.mass_status == "unbalanced"
        )
        + "\n",
        encoding="utf-8",
    )
    inventory_path = destination / "beta1-inventory.json"
    inventory_path.write_text(
        json.dumps(inventory.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    summary_path = destination / "beta1-summary.md"
    summary = (
        "# β1 curation summary\n\n"
        f"- Input SHA-256: `{sha256_file(source)}`\n"
        f"- Metabolites: {len(curated.metabolites)}\n"
        f"- Reactions: {len(curated.reactions)}\n"
        f"- Genes: {len(curated.genes)}\n"
        f"- Proposals: {len(proposals)}\n"
        f"- Unresolved mass-balance reactions: {len(validation['unresolved'])}\n"
    )
    summary_path.write_text(
        summary,
        encoding="utf-8",
    )
    provenance_path = destination / "beta1-provenance.json"
    output_paths = {
        "json": json_path,
        "sbml": sbml_path,
        "signature": signature_path,
        "proposals": proposal_path,
        "ledger": ledger_path,
        "decisions": decisions_path,
        "validation": validation_path,
        "unresolved": unresolved_path,
        "inventory": inventory_path,
        "summary": summary_path,
        "evidence": evidence_dir / "manifest.json",
        "mappings": mappings_dir / "identity-mappings.json",
    }
    effective_formula_policy = (
        DEFAULT_FORMULA_POLICY if formula_policy is None else formula_policy
    )
    provenance_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "input": {"path": str(source), "sha256": sha256_file(source)},
                "sanctioned_model": sanctioned_model,
                "configuration": {
                    "mode": mode,
                    "balance_strategy": balance_strategy,
                    "formula_policy": dict(effective_formula_policy),
                    "subunit_stoichiometry": dict(subunit_stoichiometry),
                    "remove_isolated": remove_isolated,
                    "sanctioned_model": sanctioned_model,
                },
                "software": _software_versions(),
                "outputs": {
                    name: {"path": str(path), "sha256": sha256_file(path)}
                    for name, path in output_paths.items()
                },
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    output_paths["provenance"] = provenance_path
    return {
        "model": curated,
        "inventory": inventory.to_dict(),
        "cleanup": cleanup,
        "validation": validation,
        "outputs": {name: str(path) for name, path in output_paths.items()},
    }


def _software_versions() -> dict[str, str]:
    versions: dict[str, str] = {"python": __import__("platform").python_version()}
    for package in ("cobra", "libsbml"):
        try:
            module = __import__(package)
            versions[package] = str(getattr(module, "__version__", "unknown"))
        except ImportError:
            versions[package] = "unavailable"
    return versions


def beta1_release_gate(
    bundle_dir: str | Path, *, sanctioned_model: bool | None = None
) -> dict[str, object]:
    """Report whether a candidate bundle is eligible for the THGβ1 label."""
    root = Path(bundle_dir)
    required = (
        "thg-beta1-candidate.json",
        "thg-beta1-candidate.xml",
        "beta1-signature.json",
        "beta1-proposals.jsonl",
        "beta1-change-ledger.jsonl",
        "beta1-validation.json",
        "beta1-unresolved.tsv",
        "beta1-summary.md",
        "beta1-inventory.json",
        "beta1-provenance.json",
        "beta1-decisions.jsonl",
    )
    missing = [name for name in required if not (root / name).is_file()]
    validation: dict[str, object] = {}
    validation_path = root / "beta1-validation.json"
    if validation_path.is_file():
        validation = json.loads(validation_path.read_text(encoding="utf-8"))
    reasons: list[str] = []
    if missing:
        reasons.append("missing required artifacts: " + ", ".join(missing))
    if not bool(validation.get("all_ids_unique", validation.get("unique_ids", False))):
        reasons.append("unique-ID validation did not pass")
    if validation.get("unresolved"):
        reasons.append("unresolved validation exceptions are not approved")
    if validation.get("unresolved_identity_conflicts"):
        reasons.append("unresolved identity conflicts are not approved")
    for field_name in (
        "valid_references",
        "valid_gene_references",
        "valid_groups",
        "objective_valid",
        "no_systematic_compartment_expansion",
        "ledger_agrees_with_semantic_diff",
    ):
        if field_name not in validation or not validation[field_name]:
            reasons.append(f"validation field failed: {field_name}")
    if validation.get("invalid_gprs"):
        reasons.append("invalid GPRs are present")
    solver = validation.get("solver")
    if isinstance(solver, Mapping) and solver.get("status") not in {
        "optimal",
        "feasible",
    }:
        reasons.append("solver validation did not report a feasible solution")
    flux_consistency = validation.get("flux_consistency")
    if isinstance(flux_consistency, Mapping) and (
        flux_consistency.get("status") == "error"
        or flux_consistency.get("consistent") is False
    ):
        reasons.append("flux-consistency validation did not pass")
    provenance_path = root / "beta1-provenance.json"
    provenance = (
        json.loads(provenance_path.read_text(encoding="utf-8"))
        if provenance_path.is_file()
        else {}
    )
    provenance_input = provenance.get("input", {})
    if isinstance(provenance_input, Mapping):
        input_path = provenance_input.get("path")
        input_sha256 = provenance_input.get("sha256")
        if isinstance(input_path, str) and isinstance(input_sha256, str):
            if (
                not Path(input_path).is_file()
                or sha256_file(input_path) != input_sha256
            ):
                reasons.append("input checksum does not match provenance")
    output_names = {
        "json": "thg-beta1-candidate.json",
        "sbml": "thg-beta1-candidate.xml",
        "signature": "beta1-signature.json",
        "proposals": "beta1-proposals.jsonl",
        "ledger": "beta1-change-ledger.jsonl",
        "decisions": "beta1-decisions.jsonl",
        "validation": "beta1-validation.json",
        "unresolved": "beta1-unresolved.tsv",
        "inventory": "beta1-inventory.json",
        "summary": "beta1-summary.md",
    }
    recorded_outputs = provenance.get("outputs", {})
    if isinstance(recorded_outputs, Mapping):
        for name, record in recorded_outputs.items():
            if name not in output_names:
                continue
            if isinstance(record, Mapping):
                expected_path = record.get("path")
                expected_sha256 = record.get("sha256")
                output_path = (
                    Path(expected_path)
                    if isinstance(expected_path, str)
                    else root / output_names[name]
                )
            else:
                expected_sha256 = record
                output_path = root / output_names[name]
            if not isinstance(expected_sha256, str) or not output_path.is_file():
                reasons.append(f"provenance output is missing: {name}")
            elif sha256_file(output_path) != expected_sha256:
                reasons.append(f"provenance checksum does not match: {name}")
    if sanctioned_model is None:
        sanctioned_model = bool(provenance.get("sanctioned_model", False))
    if not sanctioned_model:
        reasons.append("sanctioned human-model run is not recorded")
    elif isinstance(provenance_input, Mapping):
        sanctioned_sha256 = provenance_input.get("sha256")
        if sanctioned_sha256 != SANCTIONED_BETA1_INPUT_SHA256:
            reasons.append("input checksum is not the maintained sanctioned β1 fixture")
    for directory, required in (
        (root / "evidence", "evidence"),
        (root / "mappings", "mappings"),
    ):
        if not directory.is_dir() or not any(directory.iterdir()):
            reasons.append(f"{required} artifact directory is incomplete")
    return {
        "schema_version": 1,
        "ready": not reasons,
        "label": "THGβ1" if not reasons else "thg-beta1-candidate",
        "reasons": reasons,
    }


def release_beta1(
    bundle_dir: str | Path,
    output_dir: str | Path | None = None,
) -> dict[str, object]:
    """Promote a gate-passing candidate bundle to the public β1 filenames."""
    root = Path(bundle_dir).resolve()
    gate = beta1_release_gate(root)
    if not gate["ready"]:
        raise ValueError("β1 release gate failed: " + "; ".join(gate["reasons"]))
    destination = Path(output_dir).resolve() if output_dir is not None else root
    destination.mkdir(parents=True, exist_ok=True)
    json_path = destination / "thg-beta1.json"
    sbml_path = destination / "thg-beta1.xml"
    import shutil

    shutil.copy2(root / "thg-beta1-candidate.json", json_path)
    shutil.copy2(root / "thg-beta1-candidate.xml", sbml_path)
    manifest = destination / "beta1-release.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "label": "THGβ1",
                "source_bundle": str(root),
                "outputs": {
                    "json": {"path": str(json_path), "sha256": sha256_file(json_path)},
                    "sbml": {"path": str(sbml_path), "sha256": sha256_file(sbml_path)},
                },
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return {
        "label": "THGβ1",
        "json": str(json_path),
        "sbml": str(sbml_path),
        "manifest": str(manifest),
    }


__all__ = [
    "BalanceAudit",
    "GPRExpression",
    "InventoryReport",
    "MetaboliteCandidate",
    "ReactionIdentity",
    "audit_model",
    "beta1_release_gate",
    "audit_reaction",
    "apply_model_proposals",
    "canonicalize_gpr",
    "classify_reaction",
    "compare_reaction_identity",
    "consolidate_model",
    "duplicate_reaction_groups",
    "generate_balance_proposals",
    "inventory_model",
    "normalize_namespace",
    "normalized_stoichiometry",
    "parse_gpr",
    "protonation_relation",
    "resolve_metabolite_identity",
    "rewrite_gpr",
    "reaction_identity_key",
    "run_beta1",
    "score_metabolite_candidate",
    "formula_class",
    "serialize_s_gpr",
    "with_subunit_stoichiometry",
    "release_beta1",
    "serialize_gpr",
    "generate_cleanup_proposals",
    "apply_cleanup_proposals",
    "SANCTIONED_BETA1_INPUT_SHA256",
]
