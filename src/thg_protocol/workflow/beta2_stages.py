"""Detailed, offline-capable β2 expansion stages."""
from __future__ import annotations

import json
import ast
import platform
import shutil
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .artifacts import resolve_artifact
from .hashing import sha256_file, sha256_json
from .stages import StageContext, StageResult, _dependency_path, _load_cobra_model

DETAILED_BETA2_STAGE_IDS = (
    "load-beta1", "collect-catalysis-evidence", "resolve-gprs",
    "collect-location-evidence", "normalize-compartments",
    "infer-complex-and-isoenzyme-locations", "generate-expansion-plan",
    "apply-expansion-decisions", "apply-expansion", "consolidate-expanded-model",
    "validate-beta2", "export-beta2",
)

def _dump(path: Path, value: object) -> Path:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path

def _section(context: StageContext) -> Mapping[str, object]:
    value = context.config.sections.get("beta2", {})
    return value if isinstance(value, Mapping) else {}

def _model(context: StageContext, stage: str, role: str = "model") -> Any:
    return _load_cobra_model(_dependency_path(context, stage, role))

class DetailedBeta2Stage:
    implementation_version = 1
    kind = "scientific"
    def __init__(self, stage_id: str, dependencies: tuple[str, ...] = ()):
        self.id, self.dependencies = stage_id, dependencies
    def enabled(self, config: Any) -> bool:
        del config
        return True
    def fingerprint_data(self, context: StageContext) -> Mapping[str, object]:
        section = dict(_section(context))
        source = section.get("input_model")
        return {"stage": self.id, "implementation_version": self.implementation_version, "configuration": section, "input_sha256": sha256_file(source) if isinstance(source, str) and Path(source).is_file() else None, "dependencies": {item: [str(output.get("sha256")) for output in context.manifest.get("steps", {}).get(item, {}).get("outputs", []) if isinstance(output, Mapping)] for item in self.dependencies}}
    def run(self, context: StageContext, work_dir: Path) -> StageResult:
        from thg_protocol.curation.beta2 import (apply_expansion_plan, generate_expansion_plan, normalize_compartment_registry, normalize_location, resolve_gpr_locations, validate_beta2)
        section = _section(context)
        if self.id == "load-beta1":
            source: Path
            external = bool(section.get("external_beta1_equivalent", False))
            if isinstance(section.get("input_model"), str):
                if not external:
                    raise ValueError("beta2.input_model requires explicit external_beta1_equivalent=true")
                source = Path(str(section["input_model"]))
            elif isinstance(section.get("upstream"), Mapping):
                reference = resolve_artifact(section["upstream"], base_dir=context.config.source_path.parent if context.config.source_path else None)
                if reference.reference.stage_id != "export-beta1" or reference.reference.role != "model":
                    raise ValueError("beta2 upstream must reference the beta1 export model artifact")
                source = reference.path
            else:
                raise ValueError("beta2 requires input_model or upstream artifact reference")
            if not external and isinstance(section.get("upstream"), Mapping):
                upstream = section["upstream"]
                manifest = json.loads((reference.reference.run_dir / "manifest.json").read_text(encoding="utf-8"))
                if str(manifest.get("workflow")) != "beta1":
                    raise ValueError("β2 upstream must be a completed beta1 artifact")
            model = _load_cobra_model(source)
            invalid_gprs = []
            for reaction in model.reactions:
                rule = str(reaction.gene_reaction_rule or "").strip()
                if rule:
                    try:
                        ast.parse(rule, mode="eval")
                    except SyntaxError:
                        invalid_gprs.append(str(reaction.id))
            if invalid_gprs:
                raise ValueError("β1 input contains invalid GPRs: " + ", ".join(sorted(invalid_gprs)))
            missing_compartments = sorted({str(getattr(item, "compartment", "")) for item in model.metabolites if not str(getattr(item, "compartment", ""))})
            if missing_compartments:
                raise ValueError("β1 input contains metabolites without compartments")
            copied = work_dir / f"beta1-input{source.suffix.lower()}"
            shutil.copy2(source, copied)
            return StageResult((("model", copied), ("input-gate", _dump(work_dir / "beta1-input-gate.json", {"passed": True, "external_beta1_equivalent": external, "exception": "external-beta1-equivalent" if external else None, "input_sha256": sha256_file(source), "gpr_validation": "passed", "compartment_mapping": "present"}))), {"external": external, "model_id": str(model.id)})
        if self.id == "collect-catalysis-evidence":
            model = _model(context, "load-beta1")
            configured = section.get("catalysis_evidence", {})
            records = dict(configured) if isinstance(configured, Mapping) else {}
            for reaction in model.reactions:
                records.setdefault(str(reaction.id), {"ec": reaction.annotation.get("ec-code", reaction.annotation.get("ec", [])) if isinstance(reaction.annotation, Mapping) else [], "gpr": str(reaction.gene_reaction_rule or ""), "source": "model-annotation"})
            return StageResult((("evidence", _dump(work_dir / "beta2-catalysis-evidence.json", {"schema_version": 1, "records": {key: records[key] for key in sorted(records)}})),), {"records": len(records)})
        if self.id == "resolve-gprs":
            model = _model(context, "load-beta1")
            from thg_protocol.curation.beta1 import canonicalize_gpr, serialize_gpr
            stoich = section.get("subunit_stoichiometry", {})
            records = {}
            for r in sorted(model.reactions, key=lambda item: str(item.id)):
                raw = str(r.gene_reaction_rule or "")
                try:
                    canonical = serialize_gpr(canonicalize_gpr(raw)) if raw else ""
                    valid = True
                except (SyntaxError, ValueError):
                    canonical, valid = raw, False
                records[str(r.id)] = {"gpr": canonical, "original_gpr": raw, "genes": sorted(str(g.id) for g in r.genes), "subunit_stoichiometry": dict(stoich.get(str(r.id), {})) if isinstance(stoich, Mapping) and isinstance(stoich.get(str(r.id), {}), Mapping) else {}, "valid": valid}
            return StageResult((("gprs", _dump(work_dir / "beta2-gprs.json", {"schema_version": 1, "records": records})),), {"records": len(records)})
        if self.id == "collect-location-evidence":
            configured = section.get("gene_locations", {})
            records = {}
            if isinstance(configured, Mapping):
                for key, value in sorted(configured.items(), key=lambda item: str(item[0])):
                    if isinstance(value, Mapping):
                        raw_locations = value.get("locations", ())
                        status = str(value.get("status", "direct"))
                        source = str(value.get("source", "configuration"))
                    else:
                        raw_locations, status, source = value, "direct", "configuration"
                    if isinstance(raw_locations, str):
                        raw_locations = [raw_locations]
                    locations = sorted({normalize_location(str(item)) for item in raw_locations}) if isinstance(raw_locations, (list, tuple, set, frozenset)) else []
                    records[str(key)] = {"locations": locations, "status": status, "source": source, "evidence_id": f"gene-location:{key}"}
            return StageResult((("evidence", _dump(work_dir / "beta2-location-evidence.json", {"schema_version": 1, "ontology_version": str(section.get("compartment_ontology_version", "beta2-compartments-1")), "gene_locations": records, "source": "configuration"})),), {"genes": len(records)})
        if self.id == "normalize-compartments":
            registry = normalize_compartment_registry(section.get("compartments") if isinstance(section.get("compartments"), Mapping) else None)
            payload = {"schema_version": 1, "ontology_version": str(section.get("compartment_ontology_version", "beta2-compartments-1")), "compartments": registry}
            return StageResult((("registry", _dump(work_dir / "compartment-registry.json", payload)),), {"compartments": len(registry), "ontology_version": payload["ontology_version"]})
        if self.id == "infer-complex-and-isoenzyme-locations":
            gprs = json.loads(_dependency_path(context, "resolve-gprs", "gprs").read_text(encoding="utf-8"))
            raw_locations = json.loads(_dependency_path(context, "collect-location-evidence", "evidence").read_text(encoding="utf-8"))["gene_locations"]
            allow_conflicts = str(section.get("uncertainty_policy", "reject-conflicts")) == "allow-conflicts"
            locations = {gene: (value.get("locations", []) if isinstance(value, Mapping) and (str(value.get("status", "direct")) != "conflicting" or allow_conflicts) else value if not isinstance(value, Mapping) else []) for gene, value in raw_locations.items()}
            resolved = {}; evidence = []; unresolved = []
            for reaction_id, record in gprs["records"].items():
                result = resolve_gpr_locations(str(record["gpr"]), locations, fallback_location=str(section["fallback_location"]) if isinstance(section.get("fallback_location"), str) else None)
                resolved[reaction_id] = {"rules": dict(result.rules), "subunit_stoichiometry": record.get("subunit_stoichiometry", {})}; evidence.extend({"reaction_id": reaction_id, **item} for item in result.evidence)
                evidence.extend({"reaction_id": reaction_id, "gene_id": gene, "status": value.get("status", "direct"), "locations": value.get("locations", []), "evidence_id": value.get("evidence_id")} for gene, value in raw_locations.items() if isinstance(value, Mapping) and gene in record.get("genes", []))
                unresolved.extend(f"{reaction_id}:{item}" for item in result.unresolved)
            output = {"schema_version": 1, "rules": resolved, "evidence": evidence, "unresolved": sorted(unresolved)}
            return StageResult((("locations", _dump(work_dir / "beta2-resolved-locations.json", output)),), {"reactions": len(resolved), "unresolved": len(unresolved)})
        if self.id == "generate-expansion-plan":
            from thg_protocol.workflow.ids import DeterministicIdRegistry
            registry_payload = json.loads(_dependency_path(context, "normalize-compartments", "registry").read_text(encoding="utf-8"))
            registry = registry_payload.get("compartments", registry_payload)
            raw_rules = json.loads(_dependency_path(context, "infer-complex-and-isoenzyme-locations", "locations").read_text(encoding="utf-8"))["rules"]
            rules = {reaction: (value.get("rules", {}) if isinstance(value, Mapping) else value) for reaction, value in raw_rules.items()}
            id_registry = DeterministicIdRegistry()
            plans = generate_expansion_plan(_model(context, "load-beta1"), rules, registry=id_registry, compartments=registry, subunit_stoichiometry=section.get("subunit_stoichiometry") if isinstance(section.get("subunit_stoichiometry"), Mapping) else None)
            output = work_dir / "beta2-expansion-plan.jsonl"; output.write_text("\n".join(json.dumps(item, sort_keys=True) for item in plans) + ("\n" if plans else ""), encoding="utf-8")
            proposals = work_dir / "beta2-proposals.jsonl"
            proposal_records = []
            for item in plans:
                proposal_records.append({"proposal_id": item["proposal_id"], "operation": "expand" if item.get("action") == "create" else "retain", "object_type": "reaction", "object_id": str(item["reaction_id"]), "before": {}, "after": dict(item), "evidence": [str(item.get("evidence_id", ""))] if item.get("evidence_id") else [], "confidence": "recorded", "policy": str(item.get("reason", "policy")), "stage": self.id, "status": "proposed", "reason": str(item.get("reason", "")), "metadata": {"reaction_class": item.get("reaction_class")}})
            proposals.write_text("\n".join(json.dumps(item, sort_keys=True) for item in proposal_records) + ("\n" if proposal_records else ""), encoding="utf-8")
            registry_path = _dump(work_dir / "beta2-id-registry.json", id_registry.to_dict())
            return StageResult((("plan", output), ("proposals", proposals), ("id-registry", registry_path)), {"plans": len(plans), "proposals": len(proposal_records), "ids": len(id_registry.mappings)})
        if self.id == "apply-expansion-decisions":
            plan = _dependency_path(context, "generate-expansion-plan", "plan")
            decisions = {"mode": str(section.get("mode", "apply-all")), "plan_sha256": sha256_file(plan), "approved": [], "decisions_file": section.get("decisions_file")}
            if isinstance(section.get("decisions_file"), str):
                from .proposals import read_decisions
                decisions["proposal_decisions"] = {item.proposal_id: {"action": item.action, "replacement": item.replacement} for item in read_decisions(str(section["decisions_file"]))}
            else:
                decisions["proposal_decisions"] = {}
            return StageResult((("decisions", _dump(work_dir / "beta2-decisions.json", decisions)),), decisions)
        if self.id == "apply-expansion":
            plans = [json.loads(line) for line in _dependency_path(context, "generate-expansion-plan", "plan").read_text(encoding="utf-8").splitlines() if line.strip()]
            decisions = json.loads(_dependency_path(context, "apply-expansion-decisions", "decisions").read_text(encoding="utf-8"))
            model, ledger = apply_expansion_plan(_model(context, "load-beta1"), plans, mode=str(decisions["mode"]), decisions=decisions.get("proposal_decisions", {}))
            from cobra.io import save_json_model
            output = work_dir / "expanded-model.json"; save_json_model(model, str(output))
            ledger_path = work_dir / "beta2-change-ledger.jsonl"; ledger_path.write_text("\n".join(json.dumps(item, sort_keys=True) for item in ledger) + ("\n" if ledger else ""), encoding="utf-8")
            return StageResult((("model", output), ("ledger", ledger_path)), {"applied": sum(item.get("status") == "applied" for item in ledger)})
        if self.id == "consolidate-expanded-model":
            source = _dependency_path(context, "apply-expansion", "model"); output = work_dir / "consolidated-model.json"; shutil.copy2(source, output)
            prior = _dependency_path(context, "apply-expansion", "ledger").read_text(encoding="utf-8")
            ledger = work_dir / "consolidated-change-ledger.jsonl"
            ledger.write_text(prior + json.dumps({"operation": "consolidate", "status": "applied", "deterministic": True, "removed_orphans": False}, sort_keys=True) + "\n", encoding="utf-8")
            return StageResult((("model", output), ("ledger", ledger)), {"consolidated": True, "removed_orphans": False})
        if self.id == "validate-beta2":
            plans = [json.loads(line) for line in _dependency_path(context, "generate-expansion-plan", "plan").read_text(encoding="utf-8").splitlines() if line.strip()]
            ledger = [json.loads(line) for line in _dependency_path(context, "consolidate-expanded-model", "ledger").read_text(encoding="utf-8").splitlines() if line.strip()]
            validation = validate_beta2(_model(context, "consolidate-expanded-model"), plans, ledger, baseline=_model(context, "load-beta1"), run_solver_checks=bool(section.get("run_solver_checks", False)))
            output = _dump(work_dir / "beta2-validation.json", validation)
            return StageResult((("validation", output),), validation)
        if self.id == "export-beta2":
            model_source = _dependency_path(context, "consolidate-expanded-model", "model")
            json_path = work_dir / "thg-beta2-candidate.json"; shutil.copy2(model_source, json_path)
            from cobra.io import read_sbml_model, write_sbml_model
            model = read_sbml_model(str(model_source)) if model_source.suffix == ".xml" else _load_cobra_model(model_source)
            xml_path = work_dir / "thg-beta2-candidate.xml"; write_sbml_model(model, str(xml_path))
            _load_cobra_model(json_path)
            read_sbml_model(str(xml_path))
            for role, stage, name in (("expansion-plan", "generate-expansion-plan", "beta2-expansion-plan.jsonl"), ("proposals", "generate-expansion-plan", "beta2-proposals.jsonl"), ("id-registry", "generate-expansion-plan", "beta2-id-registry.json"), ("ledger", "consolidate-expanded-model", "beta2-change-ledger.jsonl"), ("validation", "validate-beta2", "beta2-validation.json"), ("location-evidence", "infer-complex-and-isoenzyme-locations", "beta2-location-evidence.jsonl")):
                source = _dependency_path(context, stage, "plan" if role == "expansion-plan" else "proposals" if role == "proposals" else "id-registry" if role == "id-registry" else "ledger" if role == "ledger" else "validation" if role == "validation" else "locations")
                destination = work_dir / name
                if role == "location-evidence":
                    payload = json.loads(source.read_text(encoding="utf-8"))
                    destination.write_text("\n".join(json.dumps(item, sort_keys=True) for item in payload.get("evidence", [])) + ("\n" if payload.get("evidence") else ""), encoding="utf-8")
                else:
                    shutil.copy2(source, destination)
            from thg_protocol.analysis.model_signature import diff_model_signatures, model_signature
            before = model_signature(_model(context, "load-beta1"))
            diff_path = _dump(work_dir / "beta1-to-beta2-diff.json", diff_model_signatures(before, model_signature(model)))
            unresolved = json.loads(_dependency_path(context, "infer-complex-and-isoenzyme-locations", "locations").read_text(encoding="utf-8")).get("unresolved", [])
            unresolved_path = work_dir / "beta2-unresolved.tsv"; unresolved_path.write_text("object\n" + "\n".join(str(item) for item in unresolved) + ("\n" if unresolved else ""), encoding="utf-8")
            validation_payload = json.loads((work_dir / "beta2-validation.json").read_text(encoding="utf-8"))
            summary = work_dir / "beta2-summary.md"; summary.write_text("# THGβ2 candidate\n\nThis is a release candidate artifact; the THGβ2 label remains gated.\n\n" + f"- Reactions: {len(model.reactions)}\n- Metabolites: {len(model.metabolites)}\n- Unresolved location references: {len(unresolved)}\n- Added reactions: {len(validation_payload.get('added_reactions', []))}\n- β1 feasibility: {validation_payload.get('feasibility', {}).get('beta1', {}).get('status', 'not-recorded')}\n- β2 feasibility: {validation_payload.get('feasibility', {}).get('beta2', {}).get('status', 'not-recorded')}\n- Blocked-reaction analysis: {validation_payload.get('blocked_reactions', {}).get('status', 'not-recorded')}\n- Cycle-risk analysis: {validation_payload.get('cycle_risk', {}).get('status', 'not-recorded')}\n", encoding="utf-8")
            decision_path = section.get("decisions_file")
            provenance = _dump(work_dir / "beta2-provenance.json", {"schema_version": 1, "workflow": "beta2", "input_sha256": sha256_file(_dependency_path(context, "load-beta1", "model")), "upstream": section.get("upstream"), "external_beta1_equivalent": bool(section.get("external_beta1_equivalent", False)), "configuration": dict(section), "decision_file_sha256": sha256_file(str(decision_path)) if isinstance(decision_path, str) and Path(str(decision_path)).is_file() else None, "ontology_version": json.loads(_dependency_path(context, "normalize-compartments", "registry").read_text(encoding="utf-8")).get("ontology_version"), "software": {"python": platform.python_version(), "cobra": __import__("cobra").__version__}, "stage_fingerprints": {str(key): value.get("fingerprint") for key, value in context.manifest.get("steps", {}).items() if isinstance(value, Mapping)}})
            return StageResult((("model", json_path), ("sbml", xml_path), ("validation", work_dir / "beta2-validation.json"), ("plan", work_dir / "beta2-expansion-plan.jsonl"), ("proposals", work_dir / "beta2-proposals.jsonl"), ("id-registry", work_dir / "beta2-id-registry.json"), ("ledger", work_dir / "beta2-change-ledger.jsonl"), ("location-evidence", work_dir / "beta2-location-evidence.jsonl"), ("diff", diff_path), ("unresolved", unresolved_path), ("summary", summary), ("provenance", provenance)), {"release_candidate": False})
        raise ValueError(f"unknown β2 stage: {self.id}")
    def validate(self, result: StageResult) -> None:
        if not result.outputs or any(not path.is_file() for _, path in result.outputs):
            raise ValueError(f"stage '{self.id}' did not produce complete artifacts")

def detailed_beta2_stages() -> tuple[DetailedBeta2Stage, ...]:
    dependencies = {"load-beta1": (), "collect-catalysis-evidence": ("load-beta1",), "resolve-gprs": ("collect-catalysis-evidence",), "collect-location-evidence": ("resolve-gprs",), "normalize-compartments": ("collect-location-evidence",), "infer-complex-and-isoenzyme-locations": ("normalize-compartments",), "generate-expansion-plan": ("infer-complex-and-isoenzyme-locations",), "apply-expansion-decisions": ("generate-expansion-plan",), "apply-expansion": ("apply-expansion-decisions",), "consolidate-expanded-model": ("apply-expansion",), "validate-beta2": ("consolidate-expanded-model",), "export-beta2": ("validate-beta2",)}
    return tuple(DetailedBeta2Stage(stage, dependencies[stage]) for stage in DETAILED_BETA2_STAGE_IDS)
