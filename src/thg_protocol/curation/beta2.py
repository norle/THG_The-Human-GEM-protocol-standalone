"""Proposal-driven compartment expansion for a validated β1 model.

The core in this module is deliberately offline: callers provide normalized
gene-location evidence.  Network clients belong at the evidence-collection
boundary, never in the model mutation code.
"""

from __future__ import annotations

import ast
import json
import shutil
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from pathlib import Path

from cobra import Metabolite, Reaction

from thg_protocol.curation.beta1 import classify_reaction
from thg_protocol.workflow.ids import DeterministicIdRegistry
from thg_protocol.workflow.hashing import sha256_file
from thg_protocol.workflow.proposals import proposal_id

LOCATION_ALIASES = {
    "cytoplasm": "Cytosol", "cytosol": "Cytosol", "cytosolic": "Cytosol",
    "mitochondrion": "Mitochondria", "mitochondria": "Mitochondria",
    "nucleus": "Nucleus", "nuclear": "Nucleus",
    "er": "Endoplasmic reticulum", "endoplasmic reticulum": "Endoplasmic reticulum",
    "golgi": "Golgi apparatus", "golgi apparatus": "Golgi apparatus",
    "peroxisome": "Peroxisome", "plasma membrane": "Plasma membrane",
}

@dataclass(frozen=True)
class LocationResolution:
    rules: Mapping[str, str]
    evidence: tuple[Mapping[str, object], ...]
    unresolved: tuple[str, ...] = ()

def normalize_location(value: str) -> str:
    key = " ".join(str(value).strip().lower().split())
    return LOCATION_ALIASES.get(key, str(value).strip())

def normalize_compartment_registry(value: Mapping[str, str] | None = None) -> dict[str, str]:
    """Return a deterministic display-name -> model-compartment registry."""
    source = value or {"c": "Cytosol", "m": "Mitochondria", "n": "Nucleus", "p": "Peroxisome", "r": "Endoplasmic reticulum", "g": "Golgi apparatus"}
    return {str(key): normalize_location(str(name)) for key, name in sorted(source.items())}

def _parse(rule: str) -> ast.AST:
    return ast.parse(rule, mode="eval").body

def _locations(node: ast.AST, genes: Mapping[str, set[str]]) -> set[str]:
    if isinstance(node, ast.Name):
        return set(genes.get(node.id, set()))
    if isinstance(node, ast.BoolOp):
        values = [_locations(item, genes) for item in node.values]
        if isinstance(node.op, ast.And):
            return set.intersection(*values) if values else set()
        return set.union(*values) if values else set()
    raise ValueError("GPR contains an unsupported expression")

def _possible_locations(node: ast.AST, genes: Mapping[str, set[str]]) -> set[str]:
    """Return locations mentioned by any branch for rejection evidence."""
    if isinstance(node, ast.Name):
        return set(genes.get(node.id, set()))
    if isinstance(node, ast.BoolOp):
        return set().union(*(_possible_locations(item, genes) for item in node.values))
    return set()

def _render(node: ast.AST, location: str, genes: Mapping[str, set[str]]) -> str | None:
    if isinstance(node, ast.Name):
        return node.id if location in genes.get(node.id, set()) else None
    if not isinstance(node, ast.BoolOp):
        return None
    children = [_render(item, location, genes) for item in node.values]
    children = [item for item in children if item]
    if isinstance(node.op, ast.And):
        # A required subunit missing from this location invalidates the branch.
        if len(children) != len(node.values):
            return None
        return "(" + " and ".join(children) + ")"
    if not children:
        return None
    if len(children) == 1:
        return children[0]
    return "(" + " or ".join(sorted(set(children))) + ")"

def resolve_gpr_locations(gpr: str, gene_locations: Mapping[str, set[str] | list[str] | tuple[str, ...]], *, fallback_location: str | None = None) -> LocationResolution:
    """Apply union semantics to OR and intersection semantics to AND."""
    if not gpr.strip():
        return LocationResolution({}, (), ())
    genes = {str(gene): {normalize_location(str(item)) for item in locations} for gene, locations in gene_locations.items()}
    try:
        tree = _parse(gpr)
    except SyntaxError as error:
        return LocationResolution({}, (), (f"invalid-gpr:{error.msg}",))
    fallback = normalize_location(fallback_location) if fallback_location else None
    fallback_genes = set()
    if fallback:
        for gene in ast_names(tree):
            if not genes.get(gene):
                genes[gene] = {fallback}
                fallback_genes.add(gene)
    locations = sorted(_locations(tree, genes))
    possible_locations = sorted(_possible_locations(tree, genes))
    rules: dict[str, str] = {}
    evidence: list[Mapping[str, object]] = []
    for location in possible_locations:
        rule = _render(tree, location, genes)
        if rule:
            rules[location] = rule
            evidence.append({"location": location, "status": "supported", "evidence_type": "fallback" if fallback_genes & ast_names(tree) else "direct-or-inferred", "gpr": rule})
        else:
            evidence.append({"location": location, "status": "rejected", "reason": "required-subunit-location-intersection-is-empty"})
    unresolved = tuple(sorted(name for name in ast_names(tree) if not genes.get(name)))
    return LocationResolution(rules, tuple(evidence), unresolved)

def ast_names(node: ast.AST) -> set[str]:
    return {item.id for item in ast.walk(node) if isinstance(item, ast.Name)}

def reaction_policy(reaction: Any) -> dict[str, object]:
    """Classify every reaction and return the β2 generic-expansion policy."""
    kind = classify_reaction(reaction)
    rid = str(getattr(reaction, "id", "")).lower()
    name = str(getattr(reaction, "name", "") or "").lower()
    if "spontaneous" in rid or "spontaneous" in name:
        kind = "spontaneous"
    has_gpr = bool(str(getattr(reaction, "gene_reaction_rule", "") or "").strip())
    eligible = kind == "internal" and has_gpr
    reason = "eligible-internal-enzymatic" if eligible else (
        "no-gpr-or-ec-evidence" if kind == "internal" else f"excluded-{kind}"
    )
    return {"reaction_class": kind, "eligible": eligible, "reason": reason}

def generate_expansion_plan(model: Any, location_rules: Mapping[str, Mapping[str, str]], *, registry: DeterministicIdRegistry | None = None, compartments: Mapping[str, str] | None = None, subunit_stoichiometry: Mapping[str, object] | None = None) -> list[dict[str, object]]:
    """Generate stable proposals without modifying ``model``."""
    registry = registry or DeterministicIdRegistry()
    compartment_registry = normalize_compartment_registry(compartments)
    names = {name: key for key, name in compartment_registry.items()}
    plans: list[dict[str, object]] = []
    for reaction in sorted(model.reactions, key=lambda item: str(item.id)):
        policy = reaction_policy(reaction)
        eligible = bool(policy["eligible"])
        reaction_class = str(policy["reaction_class"])
        rules = location_rules.get(str(reaction.id), {})
        if not rules:
            plans.append({
                "proposal_id": proposal_id(operation="retain", object_type="reaction", object_id=str(reaction.id), before={}, after={"policy": policy}),
                "reaction_id": str(reaction.id), "action": "retain",
                "reaction_class": reaction_class, "policy": policy,
                "reason": policy["reason"],
            })
            continue
        for location, gpr in sorted(rules.items()):
            target = names.get(normalize_location(location))
            if target is None:
                plans.append({"proposal_id": proposal_id(operation="expand", object_type="reaction", object_id=str(reaction.id)+":"+location, before={}, after={"location": location}), "reaction_id": str(reaction.id), "action": "reject", "reason": "location-not-in-registry", "location": location})
                continue
            if not eligible or target in {str(getattr(item, "compartment", "")) for item in reaction.metabolites}:
                plans.append({"proposal_id": proposal_id(operation="expand", object_type="reaction", object_id=str(reaction.id)+":"+location, before={}, after={"location": location}), "reaction_id": str(reaction.id), "action": "retain", "reaction_class": reaction_class, "location": location, "reason": "excluded-by-reaction-policy"})
                continue
            new_id = registry.generate(object_type="reaction", source_id=str(reaction.id), compartment=target, prefix="THG")
            metabolite_ids = {str(metabolite.id): registry.generate(object_type="metabolite", source_id=str(metabolite.id), compartment=target, prefix="THG") for metabolite in reaction.metabolites}
            equivalent = []
            target_stoich = sorted((str(getattr(m, "formula", "") or ""), getattr(m, "charge", None), float(c)) for m, c in reaction.metabolites.items())
            for existing in model.reactions:
                if str(existing.id) == str(reaction.id):
                    continue
                if {str(m.compartment) for m in existing.metabolites} != {target}:
                    continue
                existing_stoich = sorted((str(getattr(m, "formula", "") or ""), getattr(m, "charge", None), float(c)) for m, c in existing.metabolites.items())
                if existing_stoich == target_stoich:
                    equivalent.append(str(existing.id))
            subunits = dict(subunit_stoichiometry.get(str(reaction.id), {})) if isinstance(subunit_stoichiometry, Mapping) and isinstance(subunit_stoichiometry.get(str(reaction.id), {}), Mapping) else {}
            plans.append({"proposal_id": proposal_id(operation="expand", object_type="reaction", object_id=str(reaction.id)+":"+location, before={}, after={"reaction_id": new_id, "gpr": gpr}), "action": "retain" if equivalent else "create", "reaction_id": str(reaction.id), "new_reaction_id": new_id, "location": location, "target_compartment": target, "gpr": gpr, "s_gpr": subunits, "metabolite_ids": metabolite_ids, "bounds": [float(reaction.lower_bound), float(reaction.upper_bound)], "reaction_class": reaction_class, "source_reaction": str(reaction.id), "evidence_id": f"loc:{reaction.id}:{location}", "equivalent_existing": sorted(equivalent), "reason": "equivalent-existing-reaction" if equivalent else "eligible-expansion"})
    return plans

def apply_expansion_plan(model: Any, plans: list[Mapping[str, object]], *, mode: str = "apply-all", approved: set[str] | None = None, decisions: Mapping[str, str] | None = None) -> tuple[Any, list[dict[str, object]]]:
    """Apply valid create proposals to a copy and return a change ledger."""
    if mode not in {"apply-all", "report-only", "user-approved-only"}:
        raise ValueError("unsupported β2 application mode: " + mode)
    result = model.copy()
    approved = approved or set()
    decisions = decisions or {}
    ledger: list[dict[str, object]] = []
    for original_plan in plans:
        plan = dict(original_plan)
        action = str(plan.get("action"))
        pid = str(plan.get("proposal_id"))
        detail = decisions.get(pid, "")
        if isinstance(detail, Mapping):
            decision = str(detail.get("action", ""))
            replacement = detail.get("replacement")
            if decision == "replace" and isinstance(replacement, Mapping):
                plan.update(dict(replacement))
                action = str(plan.get("action", "create"))
        else:
            decision = str(detail)
        apply = action in {"create", "update"} and decision != "reject" and (mode == "apply-all" or pid in approved or decision == "approve")
        if not apply:
            ledger.append({"proposal_id": pid, "status": "rejected" if action == "reject" else "not-applied", "reason": plan.get("reason", "decision-policy")})
            continue
        if str(plan["new_reaction_id"]) in result.reactions:
            ledger.append({"proposal_id": pid, "status": "already-applied", "object_id": plan["new_reaction_id"]})
            continue
        metabolites: dict[Any, float] = {}
        for source, new_id in dict(plan["metabolite_ids"]).items():
            original = result.metabolites.get_by_id(source)
            if new_id in result.metabolites:
                target = result.metabolites.get_by_id(new_id)
            else:
                target = Metabolite(new_id, name=original.name, formula=original.formula, charge=original.charge, compartment=str(plan["target_compartment"]))
                target.annotation = dict(original.annotation or {})
                target.annotation["thg_source_metabolite"] = source
                result.add_metabolites([target])
            metabolites[target] = float(result.reactions.get_by_id(str(plan["reaction_id"])).metabolites[original])
        source_reaction = result.reactions.get_by_id(str(plan["reaction_id"]))
        reaction = Reaction(str(plan["new_reaction_id"]), name=str(source_reaction.name))
        reaction.add_metabolites(metabolites)
        reaction.lower_bound, reaction.upper_bound = plan["bounds"]
        reaction.gene_reaction_rule = str(plan["gpr"])
        reaction.annotation = dict(source_reaction.annotation or {})
        reaction.annotation.update({"thg_source_reaction": str(plan["reaction_id"]), "thg_location": str(plan["location"]), "thg_proposal_id": pid, "thg_evidence_id": str(plan.get("evidence_id", "")), "thg_s_gpr": dict(plan.get("s_gpr", {}))})
        result.add_reactions([reaction])
        for group in getattr(source_reaction, "groups", ()):
            group.add_members([reaction])
        ledger.append({"proposal_id": pid, "status": "applied", "object_id": reaction.id, "source_reaction": plan["reaction_id"]})
    return result, ledger

def _feasibility(model: Any, *, run_solver_checks: bool) -> dict[str, object]:
    if not run_solver_checks:
        return {"status": "not-requested"}
    try:
        solution = model.optimize()
    except Exception as error:  # solver is an optional environment dependency
        return {"status": "unavailable", "error": f"{type(error).__name__}: {error}"}
    return {"status": str(solution.status), "objective": float(solution.objective_value) if solution.objective_value is not None else None}

def validate_beta2(model: Any, plans: list[Mapping[str, object]], ledger: list[Mapping[str, object]], *, baseline: Any | None = None, run_solver_checks: bool = False) -> dict[str, object]:
    from thg_protocol.analysis.consistency import charge_balance, reaction_balance
    added = {str(item.get("object_id")) for item in ledger if item.get("status") == "applied" and item.get("object_id")}
    planned = {str(item.get("new_reaction_id")) for item in plans if item.get("action") in {"create", "update"}}
    missing = sorted(added - planned)
    invalid_gprs: list[str] = []
    missing_source: list[str] = []
    missing_evidence: list[str] = []
    missing_proposal: list[str] = []
    missing_metabolite_source: list[str] = []
    wrong_compartment: list[str] = []
    plan_by_new = {str(item.get("new_reaction_id")): item for item in plans}
    balance_status: dict[str, str] = {}
    charge_status: dict[str, str] = {}
    for reaction_id in sorted(added):
        reaction = model.reactions.get_by_id(reaction_id) if reaction_id in model.reactions else None
        if reaction is None or not str(getattr(reaction, "annotation", {}).get("thg_source_reaction", "")):
            missing_source.append(reaction_id)
            continue
        if not str(reaction.annotation.get("thg_evidence_id", "")):
            missing_evidence.append(reaction_id)
        if not str(reaction.annotation.get("thg_proposal_id", "")):
            missing_proposal.append(reaction_id)
        for metabolite in reaction.metabolites:
            if not str(getattr(metabolite, "annotation", {}).get("thg_source_metabolite", "")):
                missing_metabolite_source.append(str(metabolite.id))
            expected = str(plan_by_new.get(reaction_id, {}).get("target_compartment", ""))
            if expected and str(getattr(metabolite, "compartment", "")) != expected:
                wrong_compartment.append(reaction_id)
        try:
            ast.parse(str(reaction.gene_reaction_rule), mode="eval")
        except SyntaxError:
            invalid_gprs.append(reaction_id)
        balance_status[reaction_id] = "balanced" if not reaction_balance(reaction) else "unbalanced"
        charge = charge_balance(reaction)
        charge_status[reaction_id] = "missing-charge" if "missing" in charge else "balanced" if abs(float(charge["charge"])) < 1e-9 else "unbalanced"
    solver = {"beta1": _feasibility(baseline, run_solver_checks=run_solver_checks) if baseline is not None else {"status": "not-provided"}, "beta2": _feasibility(model, run_solver_checks=run_solver_checks)}
    objective = {"beta1": str(getattr(getattr(baseline, "objective", None), "expression", "")) if baseline is not None else None, "beta2": str(getattr(getattr(model, "objective", None), "expression", ""))}
    equivalent = {str(item.get("reaction_id")): list(item.get("equivalent_existing", [])) for item in plans if item.get("equivalent_existing")}
    return {"schema_version": 1, "valid": not (missing or missing_source or missing_evidence or missing_proposal or missing_metabolite_source or invalid_gprs or wrong_compartment), "added_reactions": sorted(added), "missing_provenance": sorted(set(missing + missing_source)), "missing_evidence": sorted(set(missing_evidence)), "missing_proposals": sorted(set(missing_proposal)), "missing_metabolite_provenance": sorted(set(missing_metabolite_source)), "wrong_compartment_reactions": sorted(set(wrong_compartment)), "invalid_gprs": invalid_gprs, "mass_balance": balance_status, "charge_status": charge_status, "equivalent_existing_chemistry": equivalent, "transport_policy": {str(item.get("reaction_id")): str(item.get("reason", "")) for item in plans if item.get("reaction_class") == "transport"}, "excluded_expansions": sum(item.get("action") not in {"create", "update"} for item in plans), "plan_count": len(plans), "feasibility": solver, "objective": objective, "blocked_reactions": {"status": "not-requested" if not run_solver_checks else "not-evaluated"}, "cycle_risk": {"status": "not-requested" if not run_solver_checks else "not-evaluated"}}

RELEASE_CANDIDATE_FILES = (
    "thg-beta2-candidate.json", "thg-beta2-candidate.xml", "beta2-expansion-plan.jsonl",
    "beta2-proposals.jsonl", "beta2-id-registry.json", "beta2-change-ledger.jsonl", "beta2-location-evidence.jsonl",
    "beta2-unresolved.tsv", "beta2-validation.json", "beta1-to-beta2-diff.json", "beta2-summary.md",
    "beta2-provenance.json",
)

def beta2_release_gate(bundle_dir: str | Path) -> dict[str, object]:
    """Check the β2 artifact gate without assigning the public β2 label."""
    root = Path(bundle_dir)
    reasons: list[str] = []
    missing = [name for name in RELEASE_CANDIDATE_FILES if not (root / name).is_file()]
    if missing:
        reasons.append("missing artifacts: " + ", ".join(missing))
    validation: Mapping[str, object] = {}
    try:
        loaded = json.loads((root / "beta2-validation.json").read_text(encoding="utf-8"))
        if isinstance(loaded, Mapping):
            validation = loaded
    except (OSError, json.JSONDecodeError):
        reasons.append("beta2 validation is unreadable")
    if validation.get("valid") is not True:
        reasons.append("required β2 validation did not pass")
    if any(value != "balanced" for value in validation.get("mass_balance", {}).values()):
        reasons.append("added reactions include mass- or charge-unbalanced chemistry")
    if any(value != "balanced" for value in validation.get("charge_status", {}).values()):
        reasons.append("added reactions include charge-unbalanced chemistry")
    feasibility = validation.get("feasibility", {})
    if isinstance(feasibility, Mapping):
        for branch in ("beta1", "beta2"):
            status = feasibility.get(branch, {}).get("status") if isinstance(feasibility.get(branch), Mapping) else None
            if status not in {"optimal", "feasible", "not-requested"}:
                reasons.append(f"{branch} feasibility did not report a usable result")
    try:
        provenance = json.loads((root / "beta2-provenance.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        provenance = {}
        reasons.append("β2 provenance is unreadable")
    if provenance.get("external_beta1_equivalent"):
        reasons.append("external β1-equivalent input is not a sanctioned release input")
    upstream = provenance.get("upstream")
    if not isinstance(upstream, Mapping):
        reasons.append("verified β1 upstream reference is missing")
    else:
        try:
            from thg_protocol.workflow.artifacts import resolve_artifact
            from thg_protocol.curation.beta1 import beta1_release_gate
            resolved = resolve_artifact(upstream)
            if isinstance(provenance.get("input_sha256"), str) and sha256_file(resolved.path) != provenance.get("input_sha256"):
                reasons.append("β2 input checksum does not match verified β1 artifact")
            upstream_root = Path(str(upstream.get("run_dir")))
            manifest = json.loads((upstream_root / "manifest.json").read_text(encoding="utf-8"))
            record = next(item for item in manifest["steps"][str(upstream.get("stage_id"))]["outputs"] if item.get("role") == upstream.get("role"))
            upstream_bundle = upstream_root / str(record["path"])
            upstream_gate = beta1_release_gate(upstream_bundle.parent)
            if upstream_gate.get("ready") is not True:
                reasons.append("β1 upstream release gate did not pass")
        except Exception as error:
            reasons.append(f"β1 upstream gate unavailable: {type(error).__name__}")
    return {"passed": not reasons, "reasons": reasons, "missing": missing, "validation": dict(validation)}

def release_beta2(bundle_dir: str | Path) -> dict[str, object]:
    """Promote candidate filenames only after the β2 release gate passes."""
    root = Path(bundle_dir)
    gate = beta2_release_gate(root)
    if not gate["passed"]:
        raise ValueError("β2 release gate failed: " + "; ".join(gate["reasons"]))
    shutil.copy2(root / "thg-beta2-candidate.json", root / "thg-beta2.json")
    shutil.copy2(root / "thg-beta2-candidate.xml", root / "thg-beta2.xml")
    return {**gate, "json": str(root / "thg-beta2.json"), "sbml": str(root / "thg-beta2.xml"), "label": "THGβ2"}

__all__ = ["LocationResolution", "normalize_location", "normalize_compartment_registry", "resolve_gpr_locations", "reaction_policy", "generate_expansion_plan", "apply_expansion_plan", "validate_beta2", "beta2_release_gate", "release_beta2"]
