"""Detailed, offline-capable scientific stages for the β1 workflow."""

from __future__ import annotations

import json
import platform
import shutil
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from thg_protocol.io.models import load_model as _load_cobra_model
from thg_protocol.runtime.concurrency import parallel_map
from thg_protocol.runtime.hashing import sha256_file, sha256_json
from thg_protocol.runtime.stage import (
    StageContext,
    StageResult,
)
from thg_protocol.runtime.stage import (
    dependency_path as _dependency_path,
)
from thg_protocol.runtime.stage import (
    dump_json as _dump,
)

from ..proposals import (
    decisions_fingerprint,
    read_decisions,
    read_proposals,
    write_proposals,
)

DETAILED_BETA1_STAGE_IDS = (
    "beta1-input",
    "beta1-inventory",
    "collect-metabolite-evidence",
    "resolve-metabolite-identities",
    "collect-reaction-evidence",
    "resolve-reaction-identities",
    "normalize-genes",
    "curate-gprs",
    "generate-curation-proposals",
    "apply-curation",
    "balance-audit",
    "generate-balance-proposals",
    "apply-balance-proposals",
    "deduplicate-and-clean",
    "validate-beta1",
    "export-beta1",
)


def _evidence_record(
    *, object_type: str, object_id: str, value: Mapping[str, object]
) -> dict[str, object]:
    """Add the shared evidence envelope without changing the payload shape."""
    source = str(value.get("source", "model-annotation"))
    normalized_result = value.get(
        "normalized_result",
        value.get("candidates", value.get("annotations", {})),
    )
    query = value.get("query", {"object_type": object_type, "object_id": object_id})
    result = dict(value)
    result.update(
        {
            "schema_version": 1,
            "evidence_id": str(
                value.get(
                    "evidence_id",
                    "ev-"
                    + sha256_json(
                        {
                            "source": source,
                            "query": query,
                            "normalized_result": normalized_result,
                        }
                    ),
                )
            ),
            "source": source,
            "source_version": str(value.get("source_version", "model-input")),
            "query": query,
            "normalized_result": normalized_result,
            "raw_response_path": value.get("raw_response_path"),
            "raw_response_sha256": value.get("raw_response_sha256"),
            "parser_version": str(value.get("parser_version", "beta1-1")),
            "normalization_version": str(value.get("normalization_version", "beta1-1")),
            "confidence": str(value.get("confidence", "recorded")),
            "affected_objects": list(
                value.get("affected_objects", [f"{object_type}:{object_id}"])
            ),
            "errors": list(value.get("errors", [])),
            "warnings": list(value.get("warnings", [])),
            "retry_history": list(value.get("retry_history", [])),
            "license": value.get("license"),
            "normalized_result_sha256": sha256_json(normalized_result),
        }
    )
    return result


def _status_counts(statuses: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    for status in statuses:
        key = str(status)
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def _section(context: StageContext) -> Mapping[str, object]:
    value = context.config.sections.get("beta1", {})
    return value if isinstance(value, Mapping) else {}


def _model(context: StageContext, stage_id: str, role: str = "model") -> Any:
    return _load_cobra_model(_dependency_path(context, stage_id, role))


def _save(model: Any, path: Path) -> None:
    from thg_protocol.io.models import save_model

    save_model(model, path)


def _mapping(value: object) -> Mapping[str, Mapping[str, float]] | None:
    if not isinstance(value, Mapping):
        return None
    return {
        str(key): {str(name): float(number) for name, number in item.items()}
        for key, item in value.items()
        if isinstance(item, Mapping)
    }


def _string_mapping(value: object) -> dict[str, str]:
    return (
        {str(key): str(item) for key, item in value.items()}
        if isinstance(value, Mapping)
        else {}
    )


def _int_mapping(value: object) -> Mapping[str, int] | None:
    if not isinstance(value, Mapping):
        return None
    return {str(key): int(item) for key, item in value.items()}


def _resolution_mapping(value: object) -> dict[str, Mapping[str, object]]:
    if not isinstance(value, Mapping):
        return {}
    return {
        str(key): dict(item) for key, item in value.items() if isinstance(item, Mapping)
    }


def _decision_items(section: Mapping[str, object]) -> tuple[Any, ...]:
    path = section.get("decisions_file")
    return read_decisions(path) if isinstance(path, str) else ()


def _resolve_metabolite_payload(
    payload: tuple[str, Mapping[str, object], str | None, str | None, int | None]
) -> tuple[str, dict[str, object]]:
    from thg_protocol.curation.beta1 import resolve_metabolite_identity

    object_id, record, reference_name, reference_formula, reference_charge = payload
    return object_id, resolve_metabolite_identity(
        record.get("candidates", []),
        errors=record.get("errors", [])
        if isinstance(record.get("errors", []), (list, tuple))
        else (),
        reference_name=reference_name,
        reference_formula=reference_formula,
        reference_charge=reference_charge,
    )


def _curate_gpr_payload(
    payload: tuple[
        str,
        str,
        Mapping[str, str],
        tuple[str, ...],
        Mapping[str, object],
        bool,
    ]
) -> tuple[dict[str, object], list[dict[str, str]]] | None:
    from thg_protocol.curation.beta1 import (
        canonicalize_gpr,
        rewrite_gpr,
        serialize_gpr,
        serialize_s_gpr,
    )

    reaction_id, before, mapping, known_genes, subunits, has_subunits = payload
    if not before:
        return None
    after = serialize_gpr(canonicalize_gpr(before))
    if mapping:
        after = rewrite_gpr(after, mapping)
    ast = canonicalize_gpr(after)
    dangling = [
        {"reaction_id": reaction_id, "gene_id": gene_id}
        for gene_id in sorted(_gpr_gene_ids(ast) - set(known_genes))
    ]
    return (
        {
            "reaction_id": reaction_id,
            "before": before,
            "after": after,
            "valid": not dangling,
            "s_gpr": serialize_s_gpr(after, subunits) if has_subunits else None,
        },
        dangling,
    )


def _software_versions() -> dict[str, str]:
    versions = {"python": platform.python_version()}
    for package in ("cobra", "libsbml"):
        try:
            module = __import__(package)
        except ImportError:
            versions[package] = "unavailable"
        else:
            versions[package] = str(getattr(module, "__version__", "unknown"))
    return versions


def _run_provenance(
    context: StageContext, section: Mapping[str, object]
) -> dict[str, object]:
    steps = context.manifest.get("steps")
    fingerprints: dict[str, object] = {}
    upstream: dict[str, object] = {}
    if isinstance(steps, Mapping):
        for stage_id, entry in sorted(steps.items(), key=lambda item: str(item[0])):
            if not isinstance(entry, Mapping):
                continue
            fingerprints[str(stage_id)] = entry.get("fingerprint")
            upstream[str(stage_id)] = [
                {
                    "role": item.get("role"),
                    "path": item.get("path"),
                    "sha256": item.get("sha256"),
                }
                for item in entry.get("outputs", [])
                if isinstance(item, Mapping)
            ]
    snapshot = context.run_dir / "config.snapshot.json"
    decisions = section.get("decisions_file")
    return {
        "configuration_sha256": sha256_json(dict(section)),
        "config_snapshot_sha256": sha256_file(snapshot) if snapshot.is_file() else None,
        "decision_file_sha256": (
            sha256_file(str(decisions))
            if isinstance(decisions, str) and Path(decisions).is_file()
            else None
        ),
        "source_releases": section.get("source_releases", {}),
        "software": _software_versions(),
        "solver": section.get("solver", {}),
        "stage_fingerprints": fingerprints,
        "upstream_artifacts": upstream,
    }


class DetailedBeta1Stage:
    """One stage in the explicit Phase 1 scientific DAG."""

    implementation_version = 3

    def __init__(self, stage_id: str, dependencies: tuple[str, ...] = ()) -> None:
        self.id = stage_id
        self.dependencies = dependencies
        self.kind = "scientific"

    def enabled(self, config: Any) -> bool:
        del config
        return True

    def fingerprint_data(self, context: StageContext) -> Mapping[str, object]:
        section = _section(context)
        dependency_hashes: dict[str, list[str]] = {}
        steps = context.manifest.get("steps")
        if isinstance(steps, Mapping):
            for dependency in self.dependencies:
                entry = steps.get(dependency)
                if isinstance(entry, Mapping):
                    dependency_hashes[dependency] = [
                        str(item.get("sha256"))
                        for item in entry.get("outputs", [])
                        if isinstance(item, Mapping)
                    ]
        source = section.get("input_model")
        result = {
            "stage": self.id,
            "implementation_version": self.implementation_version,
            "configuration": {
                key: value for key, value in section.items() if key != "n_jobs"
            },
            "input_sha256": sha256_file(source)
            if isinstance(source, str) and Path(source).is_file()
            else None,
            "dependencies": dependency_hashes,
        }
        if self.id in {
            "resolve-metabolite-identities",
            "generate-curation-proposals",
        }:
            result["identity_policy_version"] = 3
        decisions = section.get("decisions_file")
        if isinstance(decisions, str):
            result["decisions_sha256"] = decisions_fingerprint(decisions)
        return result

    def run(self, context: StageContext, work_dir: Path) -> StageResult:
        from thg_protocol.curation.beta1 import (
            BalanceAudit,
            apply_cleanup_proposals,
            apply_model_proposals,
            audit_model,
            generate_balance_proposals,
            generate_cleanup_proposals,
            generate_curation_proposals,
            inventory_model,
            normalize_gene_mapping,
        )

        section = _section(context)
        if self.id == "beta1-input":
            source = Path(str(section["input_model"]))
            model = _load_cobra_model(source)
            copied = work_dir / f"input-model{source.suffix.lower()}"
            shutil.copy2(source, copied)
            return StageResult(
                (("model", copied),),
                {"model_id": str(model.id), "input_sha256": sha256_file(source)},
            )

        if self.id == "beta1-inventory":
            model = _model(context, "beta1-input")
            report = inventory_model(
                model, input_path=_section(context).get("input_model")
            )
            output = _dump(work_dir / "beta1-inventory.json", report.to_dict())
            return StageResult((("inventory", output),), report.to_dict()["counts"])

        if self.id == "collect-metabolite-evidence":
            model = _model(context, "beta1-input")
            configured = section.get("metabolite_evidence")
            if not isinstance(configured, Mapping):
                configured = section.get("metabolite_identities")
            records: dict[str, object] = {}
            if isinstance(configured, Mapping):
                records = {
                    str(key): _evidence_record(
                        object_type="metabolite",
                        object_id=str(key),
                        value=item if isinstance(item, Mapping) else {},
                    )
                    for key, item in configured.items()
                }
            else:
                for metabolite in sorted(
                    model.metabolites, key=lambda item: str(item.id)
                ):
                    records[str(metabolite.id)] = _evidence_record(
                        object_type="metabolite",
                        object_id=str(metabolite.id),
                        value={
                            "source": "model-annotation",
                            "candidates": [
                                {
                                    "namespace": namespace,
                                    "identity": identity,
                                    "score": 0.0,
                                    "evidence": ("existing-identifier",),
                                }
                                for namespace, identity in _annotation_pairs(metabolite)
                            ],
                            "retry_history": [],
                        },
                    )
            output = _dump(
                work_dir / "metabolite-evidence.json",
                {"schema_version": 1, "records": records, "errors": [], "warnings": []},
            )
            return StageResult((("evidence", output),), {"records": len(records)})

        if self.id == "resolve-metabolite-identities":
            evidence = json.loads(
                _dependency_path(
                    context, "collect-metabolite-evidence", "evidence"
                ).read_text(encoding="utf-8")
            )
            model = _model(context, "beta1-input")
            resolutions: dict[str, object] = {}
            tasks = []
            for object_id, record in sorted(evidence.get("records", {}).items()):
                if isinstance(record, Mapping) and "status" in record:
                    resolutions[object_id] = dict(record)
                elif isinstance(record, Mapping):
                    try:
                        metabolite = model.metabolites.get_by_id(object_id)
                    except KeyError:
                        resolutions[object_id] = {
                            "status": "no-match",
                            "selected": None,
                            "candidates": [],
                            "errors": ["evidence references an unknown metabolite"],
                            "reason": (
                                "evidence object is not present in the input model"
                            ),
                        }
                    else:
                        tasks.append(
                            (
                                object_id,
                                dict(record),
                                str(getattr(metabolite, "name", "") or "") or None,
                                str(getattr(metabolite, "formula", "") or "")
                                or None,
                                getattr(metabolite, "charge", None),
                            )
                        )
                else:
                    resolutions[object_id] = {
                        "status": "no-match",
                        "selected": None,
                        "candidates": [],
                    }
            del model
            for object_id, result in parallel_map(
                _resolve_metabolite_payload,
                tasks,
                n_jobs=int(section.get("n_jobs", 1)),
            ):
                resolutions[object_id] = result
            output = _dump(
                work_dir / "metabolite-identities.json",
                {"schema_version": 1, "resolutions": resolutions},
            )
            return StageResult(
                (("identities", output),),
                {
                    "resolved": sum(
                        item.get("status") == "matched"
                        for item in resolutions.values()
                        if isinstance(item, Mapping)
                    )
                },
            )

        if self.id == "collect-reaction-evidence":
            configured = section.get("reaction_evidence")
            records = (
                {
                    str(key): _evidence_record(
                        object_type="reaction",
                        object_id=str(key),
                        value=item if isinstance(item, Mapping) else {},
                    )
                    for key, item in configured.items()
                }
                if isinstance(configured, Mapping)
                else {}
            )
            if not records:
                model = _model(context, "beta1-input")
                records = {
                    str(reaction.id): _evidence_record(
                        object_type="reaction",
                        object_id=str(reaction.id),
                        value={
                            "source": "model-annotation",
                            "annotations": dict(
                                getattr(reaction, "annotation", {}) or {}
                            ),
                            "retry_history": [],
                        },
                    )
                    for reaction in sorted(
                        model.reactions, key=lambda item: str(item.id)
                    )
                }
            output = _dump(
                work_dir / "reaction-evidence.json",
                {"schema_version": 1, "records": records, "errors": [], "warnings": []},
            )
            return StageResult((("evidence", output),), {"records": len(records)})

        if self.id == "resolve-reaction-identities":
            from thg_protocol.curation.beta1 import (
                _compare_reaction_identity_payload,
                _reaction_payload,
                duplicate_reaction_groups,
            )

            model = _model(context, "beta1-input")
            configured = section.get("reaction_targets", {})
            evidence_payload = json.loads(
                _dependency_path(
                    context, "collect-reaction-evidence", "evidence"
                ).read_text(encoding="utf-8")
            )
            evidence_records = evidence_payload.get("records", {})
            metabolite_identity_payload = json.loads(
                _dependency_path(
                    context, "resolve-metabolite-identities", "identities"
                ).read_text(encoding="utf-8")
            )
            metabolite_mapping = {
                str(object_id): str(result["selected"].get("identity"))
                for object_id, result in metabolite_identity_payload.get(
                    "resolutions", {}
                ).items()
                if isinstance(result, Mapping)
                and result.get("status") == "matched"
                and isinstance(result.get("selected"), Mapping)
                and result["selected"].get("identity")
            }
            resolutions: dict[str, object] = {}
            tasks = []
            task_ids = []
            duplicate_groups = duplicate_reaction_groups(
                model, metabolite_mapping=metabolite_mapping
            )
            targets = configured if isinstance(configured, Mapping) else {}
            for reaction in sorted(model.reactions, key=lambda item: str(item.id)):
                target = targets.get(reaction.id)
                evidence_record = (
                    evidence_records.get(reaction.id, {})
                    if isinstance(evidence_records, Mapping)
                    else {}
                )
                if target is None and isinstance(evidence_record, Mapping):
                    target = evidence_record.get("stoichiometry")
                if target is None:
                    configured_identity = section.get("reaction_identities", {})
                    if isinstance(configured_identity, Mapping):
                        identity_record = configured_identity.get(str(reaction.id))
                        if isinstance(identity_record, Mapping):
                            target = identity_record.get("stoichiometry")
                            if target is None:
                                target = identity_record.get("normalized")
                            if target is None and all(
                                isinstance(value, (int, float))
                                for value in identity_record.values()
                            ):
                                target = identity_record
                if target is None:
                    resolutions[str(reaction.id)] = {
                        "status": "not-evaluated",
                        "normalized": {},
                        "reversed": False,
                        "reason": "no reference stoichiometry was supplied",
                        "normalization_policy": str(
                            section.get("proton_water_policy", "strict")
                        ),
                        "evidence": list(
                            evidence_record.get("evidence", [])
                            if isinstance(evidence_record, Mapping)
                            else []
                        ),
                    }
                    continue
                if isinstance(target, Mapping):
                    task_ids.append(str(reaction.id))
                    tasks.append(
                        (
                            _reaction_payload(reaction),
                            dict(target),
                            metabolite_mapping,
                            str(section.get("proton_water_policy", "strict")),
                            tuple(
                                str(item)
                                for item in section.get("normalization_species", ())
                            )
                            if isinstance(
                                section.get("normalization_species", ()), (list, tuple)
                            )
                            else (),
                        )
                    )
            del model
            for reaction_id, result in zip(
                task_ids,
                parallel_map(
                    _compare_reaction_identity_payload,
                    tasks,
                    n_jobs=int(section.get("n_jobs", 1)),
                ),
                strict=True,
            ):
                evidence_record = (
                    evidence_records.get(reaction_id, {})
                    if isinstance(evidence_records, Mapping)
                    else {}
                )
                resolutions[reaction_id] = {
                    "status": result.status,
                    "normalized": dict(result.normalized),
                    "reversed": result.reversed,
                    "reason": result.reason,
                    "normalization_policy": result.normalization_policy,
                    "evidence": list(
                        evidence_record.get("evidence", [])
                        if isinstance(evidence_record, Mapping)
                        else []
                    ),
                }
            output = _dump(
                work_dir / "reaction-identities.json",
                {
                    "schema_version": 1,
                    "resolutions": resolutions,
                    "duplicate_chemistry": [
                        list(group) for group in duplicate_groups
                    ],
                },
            )
            return StageResult((("identities", output),), {"records": len(resolutions)})

        if self.id == "normalize-genes":
            model = _model(context, "beta1-input")
            mapping = normalize_gene_mapping(
                _string_mapping(section.get("gene_mapping"))
            )
            used = sorted(
                {
                    str(gene.id)
                    for reaction in model.reactions
                    for gene in reaction.genes
                }
            )
            output = _dump(
                work_dir / "gene-mapping.json",
                {
                    "schema_version": 1,
                    "mapping": mapping,
                    "used_genes": used,
                    "unused_mapping_keys": sorted(set(mapping) - set(used)),
                    "conflicts": [],
                },
            )
            return StageResult(
                (("mapping", output),),
                {"mapped": len(mapping), "used_genes": len(used)},
            )

        if self.id == "curate-gprs":
            model = _model(context, "beta1-input")
            mapping_payload = json.loads(
                _dependency_path(context, "normalize-genes", "mapping").read_text(
                    encoding="utf-8"
                )
            )
            mapping = mapping_payload.get("mapping", {})
            subunit_mapping = section.get("subunit_stoichiometry", {})
            if not isinstance(subunit_mapping, Mapping):
                subunit_mapping = {}
            records = []
            known_genes = {str(gene.id) for gene in model.genes} | {
                str(value) for value in mapping.values()
            }
            dangling_references: list[dict[str, object]] = []
            tasks = tuple(
                (
                    str(reaction.id),
                    str(reaction.gene_reaction_rule or ""),
                    dict(mapping),
                    tuple(sorted(known_genes)),
                    dict(subunit_mapping.get(str(reaction.id), {}))
                    if isinstance(subunit_mapping.get(str(reaction.id), {}), Mapping)
                    else {},
                    str(reaction.id) in subunit_mapping,
                )
                for reaction in sorted(model.reactions, key=lambda item: str(item.id))
            )
            del model
            for result in parallel_map(
                _curate_gpr_payload,
                tasks,
                n_jobs=int(section.get("n_jobs", 1)),
            ):
                if result is None:
                    continue
                record, dangling = result
                records.append(record)
                dangling_references.extend(dangling)
            output = _dump(
                work_dir / "gpr-curation.json",
                {
                    "schema_version": 1,
                    "records": records,
                    "dangling_references": dangling_references,
                },
            )
            return StageResult((("gprs", output),), {"records": len(records)})

        if self.id == "generate-curation-proposals":
            model = _model(context, "beta1-input")
            identities = json.loads(
                _dependency_path(
                    context, "resolve-metabolite-identities", "identities"
                ).read_text(encoding="utf-8")
            )
            mapping = json.loads(
                _dependency_path(context, "normalize-genes", "mapping").read_text(
                    encoding="utf-8"
                )
            )
            gpr_payload = json.loads(
                _dependency_path(context, "curate-gprs", "gprs").read_text(
                    encoding="utf-8"
                )
            )
            proposals = generate_curation_proposals(
                model,
                metabolite_identities=_resolution_mapping(
                    identities.get("resolutions", {})
                ),
                gene_mapping=_string_mapping(mapping.get("mapping", {})),
                reaction_identities=_resolution_mapping(
                    json.loads(
                        _dependency_path(
                            context, "resolve-reaction-identities", "identities"
                        ).read_text(encoding="utf-8")
                    ).get("resolutions", {})
                ),
                subunit_stoichiometry=(
                    section.get("subunit_stoichiometry", {})
                    if isinstance(section.get("subunit_stoichiometry", {}), Mapping)
                    else {}
                ),
                canonical_gprs=(
                    gpr_payload.get("records", {})
                    if isinstance(gpr_payload.get("records", {}), Mapping)
                    else {}
                ),
            )
            output = work_dir / "curation-proposals.jsonl"
            write_proposals(output, proposals)
            return StageResult((("proposals", output),), {"proposals": len(proposals)})

        if self.id == "apply-curation":
            model = _model(context, "beta1-input")
            proposals = read_proposals(
                _dependency_path(context, "generate-curation-proposals", "proposals")
            )
            curated, ledger = apply_model_proposals(
                model,
                proposals,
                mode=str(section.get("mode", "apply-all")),
                decisions=_decision_items(section),
            )
            ledger = tuple(ledger) + _semantic_ledger_entries(model, curated, ledger)
            output = work_dir / "curated-model.json"
            _save(curated, output)
            ledger_path = work_dir / "curation-change-ledger.jsonl"
            ledger_path.write_text(
                "\n".join(json.dumps(item, sort_keys=True) for item in ledger)
                + ("\n" if ledger else ""),
                encoding="utf-8",
            )
            return StageResult(
                (("model", output), ("ledger", ledger_path)),
                {"applied": sum(item.get("status") == "applied" for item in ledger)},
            )

        if self.id == "balance-audit":
            audits = audit_model(
                _model(context, "apply-curation"),
                formula_policy=(
                    section.get("formula_policy")
                    if isinstance(section.get("formula_policy"), Mapping)
                    else None
                ),
                n_jobs=int(section.get("n_jobs", 1)),
            )
            output = _dump(
                work_dir / "balance-audit.json",
                {"schema_version": 1, "audits": [item.to_dict() for item in audits]},
            )
            return StageResult(
                (("audit", output),),
                {
                    "unbalanced": sum(
                        item.mass_status == "unbalanced" for item in audits
                    )
                },
            )

        if self.id == "generate-balance-proposals":
            model = _model(context, "apply-curation")
            audit_payload = json.loads(
                _dependency_path(context, "balance-audit", "audit").read_text(
                    encoding="utf-8"
                )
            )
            audits = {
                audit.reaction_id: audit
                for item in audit_payload.get("audits", ())
                if isinstance(item, Mapping)
                for audit in (BalanceAudit.from_dict(item),)
            }
            proposals = generate_balance_proposals(
                model,
                corrections=_mapping(section.get("corrections")),
                formula_corrections=_string_mapping(section.get("formula_corrections")),
                charge_corrections=_int_mapping(section.get("charge_corrections")),
                strategy=str(section.get("balance_strategy", "proton-water")),
                audits=audits,
            )
            output = work_dir / "balance-proposals.jsonl"
            write_proposals(output, proposals)
            return StageResult((("proposals", output),), {"proposals": len(proposals)})

        if self.id == "apply-balance-proposals":
            model = _model(context, "apply-curation")
            proposals = read_proposals(
                _dependency_path(context, "generate-balance-proposals", "proposals")
            )
            curated, balance_ledger = apply_model_proposals(
                model,
                proposals,
                mode=str(section.get("mode", "apply-all")),
                decisions=_decision_items(section),
            )
            previous = _dependency_path(context, "apply-curation", "ledger").read_text(
                encoding="utf-8"
            )
            prior_entries = tuple(
                json.loads(line) for line in previous.splitlines() if line.strip()
            )
            balance_ledger = tuple(balance_ledger) + _semantic_ledger_entries(
                model, curated, prior_entries + tuple(balance_ledger)
            )
            output = work_dir / "balanced-model.json"
            _save(curated, output)
            ledger_path = work_dir / "beta1-change-ledger.jsonl"
            current = "\n".join(
                json.dumps(item, sort_keys=True) for item in balance_ledger
            )
            ledger_path.write_text(
                previous
                + ("\n" if previous and current else "")
                + (current + "\n" if current else ""),
                encoding="utf-8",
            )
            return StageResult(
                (("model", output), ("ledger", ledger_path)),
                {"balance_proposals": len(proposals)},
            )

        if self.id == "deduplicate-and-clean":
            model = _model(context, "apply-balance-proposals")
            cleanup_proposals, _ = generate_cleanup_proposals(
                model,
                remove_isolated=bool(section.get("remove_isolated", False)),
                gene_mapping=_string_mapping(section.get("gene_mapping")),
            )
            cleanup_proposal_path = work_dir / "cleanup-proposals.jsonl"
            write_proposals(cleanup_proposal_path, cleanup_proposals)
            cleaned, cleanup_ledger, report = apply_cleanup_proposals(
                model,
                cleanup_proposals,
                mode=str(section.get("mode", "apply-all")),
                decisions=_decision_items(section),
            )
            output = work_dir / "clean-model.json"
            _save(cleaned, output)
            cleanup = _dump(work_dir / "cleanup.json", report)
            ledger = work_dir / "beta1-change-ledger.jsonl"
            previous_ledger = _dependency_path(
                context, "apply-balance-proposals", "ledger"
            ).read_text(encoding="utf-8")
            from thg_protocol.analysis.model_signature import (
                diff_model_signatures,
                model_signature,
            )

            cleanup_diff = diff_model_signatures(
                model_signature(model), model_signature(cleaned)
            )
            cleanup_entries: list[dict[str, object]] = list(cleanup_ledger)
            for collection in (
                "metabolites",
                "reactions",
                "genes",
                "groups",
                "objective",
            ):
                for identifier in cleanup_diff["added"].get(collection, []):
                    cleanup_entries.append(
                        {
                            "operation": "consolidate-add",
                            "object_type": collection,
                            "object_id": identifier,
                            "status": "applied",
                            "reason": "deterministic cleanup",
                        }
                    )
                for identifier in cleanup_diff["removed"].get(collection, []):
                    cleanup_entries.append(
                        {
                            "operation": "consolidate-remove",
                            "object_type": collection,
                            "object_id": identifier,
                            "status": "applied",
                            "reason": "deterministic cleanup",
                        }
                    )
                for item in cleanup_diff["changed"].get(collection, []):
                    cleanup_entries.append(
                        {
                            "operation": "consolidate-update",
                            "object_type": collection,
                            "object_id": item["id"],
                            "status": "applied",
                            "reason": "deterministic cleanup",
                        }
                    )
            cleanup_text = "\n".join(
                json.dumps(item, sort_keys=True) for item in cleanup_entries
            )
            ledger.write_text(
                previous_ledger
                + ("\n" if previous_ledger and cleanup_text else "")
                + (cleanup_text + "\n" if cleanup_text else ""),
                encoding="utf-8",
            )
            return StageResult(
                (
                    ("model", output),
                    ("cleanup", cleanup),
                    ("cleanup-proposals", cleanup_proposal_path),
                    ("ledger", ledger),
                ),
                report,
            )

        if self.id == "validate-beta1":
            model = _model(context, "deduplicate-and-clean")
            audits = audit_model(
                model,
                formula_policy=(
                    section.get("formula_policy")
                    if isinstance(section.get("formula_policy"), Mapping)
                    else None
                ),
                n_jobs=int(section.get("n_jobs", 1)),
            )
            from thg_protocol.curation.beta1 import is_unresolved_balance

            valid_gprs = []
            invalid_gprs = []
            from thg_protocol.curation.beta1 import parse_gpr

            for reaction in model.reactions:
                if reaction.gene_reaction_rule:
                    try:
                        parse_gpr(reaction.gene_reaction_rule)
                    except ValueError as error:
                        invalid_gprs.append(
                            {"reaction_id": str(reaction.id), "error": str(error)}
                        )
                    else:
                        valid_gprs.append(str(reaction.id))
            ids_by_collection = {
                "metabolites": [str(item.id) for item in model.metabolites],
                "reactions": [str(item.id) for item in model.reactions],
                "genes": [str(item.id) for item in model.genes],
                "groups": [str(item.id) for item in getattr(model, "groups", ())],
            }
            validation = {
                "schema_version": 1,
                "model_id": str(model.id),
                "unique_ids": all(
                    len(values) == len(set(values))
                    for values in ids_by_collection.values()
                ),
                "all_ids_unique": all(
                    len(values) == len(set(values))
                    for values in ids_by_collection.values()
                ),
                "valid_gprs": valid_gprs,
                "invalid_gprs": invalid_gprs,
                "audits": [item.to_dict() for item in audits],
                "unresolved": [
                    item.to_dict() for item in audits if is_unresolved_balance(item)
                ],
                "balance_status_counts": {
                    "mass": _status_counts(item.mass_status for item in audits),
                    "charge": _status_counts(item.charge_status for item in audits),
                },
                "objective": str(
                    getattr(getattr(model, "objective", None), "direction", "unknown")
                ),
                "compartment_count": len(getattr(model, "compartments", {})),
            }
            original = _model(context, "beta1-input")
            from thg_protocol.analysis.model_signature import (
                diff_model_signatures,
                model_signature,
            )

            semantic_diff = diff_model_signatures(
                model_signature(original), model_signature(model)
            )
            model_metabolite_ids = {str(item.id) for item in model.metabolites}
            validation["valid_references"] = all(
                str(metabolite.id) in model_metabolite_ids
                for reaction in model.reactions
                for metabolite in reaction.metabolites
            )
            model_gene_ids = {str(item.id) for item in model.genes}
            validation["valid_gene_references"] = all(
                str(gene.id) in model_gene_ids
                for reaction in model.reactions
                for gene in reaction.genes
            )
            validation["valid_groups"] = all(
                all(
                    member in model.metabolites
                    or member in model.reactions
                    or member in model.genes
                    for member in group.members
                )
                for group in getattr(model, "groups", ())
            )
            validation["objective_valid"] = getattr(
                model, "objective", None
            ) is not None and all(
                str(item["reaction"]) in {str(r.id) for r in model.reactions}
                for item in model_signature(model).get("objective", [])
            )
            validation["no_systematic_compartment_expansion"] = set(
                getattr(model, "compartments", {})
            ) <= set(getattr(original, "compartments", {}))
            identity_payload = json.loads(
                _dependency_path(
                    context, "resolve-metabolite-identities", "identities"
                ).read_text(encoding="utf-8")
            )
            reaction_identity_payload = json.loads(
                _dependency_path(
                    context, "resolve-reaction-identities", "identities"
                ).read_text(encoding="utf-8")
            )
            validation["unresolved_identity_conflicts"] = [
                {"object_id": object_id, **dict(result)}
                for object_id, result in identity_payload.get("resolutions", {}).items()
                if isinstance(result, Mapping) and result.get("status") != "matched"
            ] + [
                {"object_id": object_id, **dict(result)}
                for object_id, result in reaction_identity_payload.get(
                    "resolutions", {}
                ).items()
                if isinstance(result, Mapping)
                and result.get("status")
                not in {"exact", "equivalent-reversed", "not-evaluated"}
            ]
            validation["duplicate_chemistry"] = reaction_identity_payload.get(
                "duplicate_chemistry", []
            )
            ledger_lines = (
                _dependency_path(context, "deduplicate-and-clean", "ledger")
                .read_text(encoding="utf-8")
                .splitlines()
            )
            ledger_ids = {
                str(json.loads(line).get("object_id"))
                for line in ledger_lines
                if line.strip()
            }
            semantic_ids: set[str] = set()
            for collection in (
                "metabolites",
                "reactions",
                "genes",
                "groups",
                "objective",
            ):
                semantic_ids.update(
                    str(item) for item in semantic_diff["added"].get(collection, [])
                )
                semantic_ids.update(
                    str(item) for item in semantic_diff["removed"].get(collection, [])
                )
                semantic_ids.update(
                    str(item["id"])
                    for item in semantic_diff["changed"].get(collection, [])
                )
            validation["ledger_agrees_with_semantic_diff"] = semantic_ids <= ledger_ids
            validation["semantic_diff"] = semantic_diff
            if bool(section.get("run_solver_checks", False)):
                try:
                    solution = model.optimize()
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
            if bool(section.get("run_blocked_reactions", False)):
                try:
                    from cobra.flux_analysis import find_blocked_reactions

                    validation["blocked_reactions"] = sorted(
                        find_blocked_reactions(model)
                    )
                except Exception as error:  # pragma: no cover - solver-specific
                    validation["blocked_reactions"] = {
                        "error": f"{type(error).__name__}: {error}"
                    }
            if bool(section.get("run_flux_consistency", False)):
                try:
                    from cobra.flux_analysis import find_blocked_reactions

                    blocked = sorted(find_blocked_reactions(model))
                    validation["flux_consistency"] = {
                        "method": "cobra.flux_analysis.find_blocked_reactions",
                        "blocked_reactions": blocked,
                        "consistent": not blocked,
                    }
                except Exception as error:  # pragma: no cover - solver-specific
                    validation["flux_consistency"] = {
                        "method": "cobra.flux_analysis.find_blocked_reactions",
                        "status": "error",
                        "error": f"{type(error).__name__}: {error}",
                    }
            output = _dump(work_dir / "beta1-validation.json", validation)
            ledger = work_dir / "beta1-change-ledger.jsonl"
            shutil.copy2(
                _dependency_path(context, "deduplicate-and-clean", "ledger"), ledger
            )
            return StageResult(
                (("validation", output), ("ledger", ledger)),
                {"unresolved": len(validation["unresolved"])},
            )

        if self.id == "export-beta1":
            model = _model(context, "deduplicate-and-clean")
            json_path = work_dir / "thg-beta1-candidate.json"
            xml_path = work_dir / "thg-beta1-candidate.xml"
            _save(model, json_path)
            _save(model, xml_path)
            # Export/reload is part of the validation boundary.  Do not let a
            # serialization failure produce a completed candidate stage.
            _load_cobra_model(json_path)
            _load_cobra_model(xml_path)
            from thg_protocol.analysis.model_signature import model_signature

            signature = _dump(work_dir / "beta1-signature.json", model_signature(model))
            validation = work_dir / "beta1-validation.json"
            shutil.copy2(
                _dependency_path(context, "validate-beta1", "validation"), validation
            )
            validation_payload = json.loads(validation.read_text(encoding="utf-8"))
            unresolved = work_dir / "beta1-unresolved.tsv"
            unresolved.write_text(
                "reaction_id\tmass_status\tcharge_status\n"
                + "\n".join(
                    f"{item['reaction_id']}\t{item['mass_status']}\t{item['charge_status']}"
                    for item in validation_payload.get("unresolved", [])
                )
                + "\n"
                + "\n".join(
                    f"{item['object_id']}\tidentity\t{item.get('status', 'unresolved')}"
                    for item in validation_payload.get(
                        "unresolved_identity_conflicts", []
                    )
                )
                + "\n",
                encoding="utf-8",
            )
            summary = work_dir / "beta1-summary.md"
            summary.write_text(
                "# β1 candidate summary\n\n"
                f"- Model: `{model.id}`\n"
                f"- Metabolites: {len(model.metabolites)}\n"
                f"- Reactions: {len(model.reactions)}\n"
                "- Unresolved mass-balance reactions: "
                f"{len(validation_payload.get('unresolved', []))}\n",
                encoding="utf-8",
            )
            ledger = work_dir / "beta1-change-ledger.jsonl"
            shutil.copy2(_dependency_path(context, "validate-beta1", "ledger"), ledger)
            proposals = work_dir / "beta1-proposals.jsonl"
            curation_proposals = _dependency_path(
                context, "generate-curation-proposals", "proposals"
            ).read_text(encoding="utf-8")
            balance_proposals = _dependency_path(
                context, "generate-balance-proposals", "proposals"
            ).read_text(encoding="utf-8")
            cleanup_proposals = _dependency_path(
                context, "deduplicate-and-clean", "cleanup-proposals"
            ).read_text(encoding="utf-8")
            proposals.write_text(
                curation_proposals + balance_proposals + cleanup_proposals,
                encoding="utf-8",
            )
            decisions_path = work_dir / "beta1-decisions.jsonl"
            decisions_path.write_text(
                "\n".join(
                    json.dumps(item.to_dict(), sort_keys=True)
                    for item in _decision_items(section)
                )
                + ("\n" if _decision_items(section) else ""),
                encoding="utf-8",
            )
            inventory = work_dir / "beta1-inventory.json"
            shutil.copy2(
                _dependency_path(context, "beta1-inventory", "inventory"), inventory
            )
            provenance = _dump(
                work_dir / "beta1-provenance.json",
                {
                    "schema_version": 1,
                    "input": {
                        "path": str(section["input_model"]),
                        "sha256": sha256_file(str(section["input_model"])),
                    },
                    "input_sha256": sha256_file(str(section["input_model"])),
                    "configuration": dict(section),
                    **_run_provenance(context, section),
                    "candidate": True,
                    "sanctioned_model": bool(section.get("sanctioned_model", False)),
                    "source_stage": "deduplicate-and-clean",
                    "outputs": {
                        "json": sha256_file(json_path),
                        "sbml": sha256_file(xml_path),
                        "signature": sha256_file(signature),
                        "validation": sha256_file(validation),
                        "ledger": sha256_file(ledger),
                        "proposals": sha256_file(proposals),
                        "decisions": sha256_file(decisions_path),
                        "inventory": sha256_file(inventory),
                        "unresolved": sha256_file(unresolved),
                        "summary": sha256_file(summary),
                    },
                },
            )
            _load_cobra_model(json_path)
            _load_cobra_model(xml_path)
            evidence_dir = work_dir / "evidence"
            mappings_dir = work_dir / "mappings"
            evidence_dir.mkdir()
            mappings_dir.mkdir()
            for stage_id, role, name in (
                ("collect-metabolite-evidence", "evidence", "metabolite-evidence.json"),
                (
                    "resolve-metabolite-identities",
                    "identities",
                    "metabolite-identities.json",
                ),
                ("collect-reaction-evidence", "evidence", "reaction-evidence.json"),
                (
                    "resolve-reaction-identities",
                    "identities",
                    "reaction-identities.json",
                ),
            ):
                shutil.copy2(
                    _dependency_path(context, stage_id, role), evidence_dir / name
                )
            shutil.copy2(
                _dependency_path(context, "normalize-genes", "mapping"),
                mappings_dir / "gene-mapping.json",
            )
            return StageResult(
                (
                    ("model", json_path),
                    ("sbml", xml_path),
                    ("signature", signature),
                    ("validation", validation),
                    ("ledger", ledger),
                    ("proposals", proposals),
                    ("decisions", decisions_path),
                    ("inventory", inventory),
                    ("provenance", provenance),
                    ("unresolved", unresolved),
                    ("summary", summary),
                    ("evidence", evidence_dir / "metabolite-evidence.json"),
                    ("mapping", mappings_dir / "gene-mapping.json"),
                ),
                {"candidate": True, "model_id": str(model.id)},
            )

        raise ValueError(f"unknown detailed β1 stage: {self.id}")

    def validate(self, result: StageResult) -> None:
        if not result.outputs or any(not path.is_file() for _, path in result.outputs):
            raise ValueError(f"stage '{self.id}' produced an incomplete artifact set")


def _annotation_pairs(metabolite: Any) -> list[tuple[str, str]]:
    annotation = getattr(metabolite, "annotation", {}) or {}
    if not isinstance(annotation, Mapping):
        return []
    pairs: list[tuple[str, str]] = []
    for namespace, value in annotation.items():
        values = value if isinstance(value, (list, tuple, set, frozenset)) else (value,)
        pairs.extend((str(namespace), str(item)) for item in values)
    return pairs


def _gpr_gene_ids(node: Any) -> set[str]:
    if getattr(node, "kind", None) == "gene":
        return {str(getattr(node, "value", ""))}
    return {
        gene_id
        for child in getattr(node, "children", ())
        for gene_id in _gpr_gene_ids(child)
    }


def _semantic_ledger_entries(
    before: Any,
    after: Any,
    existing: tuple[Mapping[str, object], ...],
) -> tuple[dict[str, object], ...]:
    from thg_protocol.analysis.model_signature import (
        diff_model_signatures,
        model_signature,
    )

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
                    "reason": "derived object change from an applied proposal",
                }
            )
    return tuple(entries)


def detailed_beta1_stages() -> tuple[DetailedBeta1Stage, ...]:
    dependencies = {
        "beta1-input": (),
        "beta1-inventory": ("beta1-input",),
        "collect-metabolite-evidence": ("beta1-inventory",),
        "resolve-metabolite-identities": ("collect-metabolite-evidence",),
        "collect-reaction-evidence": ("resolve-metabolite-identities",),
        "resolve-reaction-identities": ("collect-reaction-evidence",),
        "normalize-genes": ("resolve-reaction-identities",),
        "curate-gprs": ("normalize-genes",),
        "generate-curation-proposals": ("curate-gprs",),
        "apply-curation": ("generate-curation-proposals",),
        "balance-audit": ("apply-curation",),
        "generate-balance-proposals": ("balance-audit",),
        "apply-balance-proposals": ("generate-balance-proposals",),
        "deduplicate-and-clean": ("apply-balance-proposals",),
        "validate-beta1": ("deduplicate-and-clean",),
        "export-beta1": ("validate-beta1",),
    }
    return tuple(
        DetailedBeta1Stage(stage_id, dependencies[stage_id])
        for stage_id in DETAILED_BETA1_STAGE_IDS
    )


__all__ = ["DETAILED_BETA1_STAGE_IDS", "DetailedBeta1Stage", "detailed_beta1_stages"]
