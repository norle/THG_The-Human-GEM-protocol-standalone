"""Detailed, offline-capable β2 expansion stages."""

from __future__ import annotations

import ast
import json
import logging
import platform
import shutil
from collections.abc import Mapping
from pathlib import Path
from typing import Any

try:
    from tqdm import tqdm
except ImportError:  # pragma: no cover - exercised by clean-wheel checks
    def tqdm(iterable: object, **_kwargs: object) -> object:
        return iterable

from thg_protocol.io.models import load_model as _load_cobra_model
from thg_protocol.runtime.artifacts import resolve_artifact, upstream_fingerprint
from thg_protocol.runtime.concurrency import parallel_map
from thg_protocol.runtime.hashing import sha256_file
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

LOGGER = logging.getLogger("thg_protocol.workflow")

DETAILED_BETA2_STAGE_IDS = (
    "load-beta1",
    "collect-catalysis-evidence",
    "collect-gpr-evidence",
    "resolve-gprs",
    "normalize-compartments",
    "collect-location-evidence",
    "collect-reaction-location-evidence",
    "resolve-compartment-evidence",
    "infer-complex-and-isoenzyme-locations",
    "generate-expansion-plan",
    "apply-expansion-decisions",
    "apply-expansion",
    "consolidate-expanded-model",
    "validate-beta2",
    "export-beta2",
)


def _gpr_checkpoint(
    work_dir: Path,
    phase: str,
    candidates: Mapping[str, object],
    source_metadata: Mapping[str, object],
) -> Path:
    return _dump(
        work_dir / f"beta2-gpr-{phase}-checkpoint.json",
        {
            "schema_version": 1,
            "phase": phase,
            "records": {
                key: candidates[key] for key in sorted(candidates)
            },
            "source_metadata": dict(source_metadata),
        },
    )


def _section(context: StageContext) -> Mapping[str, object]:
    value = context.config.sections.get("beta2", {})
    return value if isinstance(value, Mapping) else {}


def _jsonl(path: str | Path) -> list[dict[str, object]]:
    result = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            value = json.loads(line)
            if isinstance(value, dict):
                result.append(value)
    return result


def _snapshot_records(section: Mapping[str, object]) -> list[dict[str, object]]:
    path = section.get("evidence_file")
    if not isinstance(path, str) or not Path(path).is_file():
        return []
    return _jsonl(path)


def _record_kind(record: Mapping[str, object]) -> str:
    return str(
        record.get("record_type", record.get("kind", record.get("type", "")))
    ).lower()


def _source_release(section: Mapping[str, object], source: str) -> str:
    releases = section.get("source_releases", {})
    item = releases.get(source, {}) if isinstance(releases, Mapping) else {}
    return str(item.get("release", "")) if isinstance(item, Mapping) else str(item)


def _ec_numbers(value: object) -> list[str]:
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, (list, tuple, set, frozenset)):
        return []
    return sorted(
        {str(item).removeprefix("EC-").strip() for item in value if str(item).strip()}
    )


def _resolve_location_payload(
    payload: tuple[
        str,
        str,
        tuple[tuple[str, object], ...],
        tuple[tuple[str, object], ...],
        str | None,
        Mapping[str, object],
    ],
):
    from thg_protocol.curation.beta2 import resolve_gpr_locations

    reaction_id, gpr, location_items, raw_location_items, fallback, record = payload
    locations = dict(location_items)
    effective_gpr = str(record.get("candidate_sgpr") or gpr)
    result = resolve_gpr_locations(
        effective_gpr, locations, fallback_location=fallback
    )
    evidence = [{"reaction_id": reaction_id, **item} for item in result.evidence]
    genes = record.get("genes", [])
    for gene, value in raw_location_items:
        if isinstance(value, Mapping) and gene in genes:
            evidence.append(
                {
                    "reaction_id": reaction_id,
                    "gene_id": gene,
                    "status": value.get("status", "direct"),
                    "locations": value.get("locations", []),
                    "evidence_id": value.get("evidence_id"),
                }
            )
    return (
        reaction_id,
        {
            "rules": dict(result.rules),
            "subunit_stoichiometry": record.get("subunit_stoichiometry", {}),
        },
        evidence,
        [f"{reaction_id}:{item}" for item in result.unresolved],
    )


def _model(context: StageContext, stage: str, role: str = "model") -> Any:
    return _load_cobra_model(_dependency_path(context, stage, role))


def _reference_beta1_upstream(context: StageContext) -> dict[str, object] | None:
    if context.config.workflow != "reference":
        return None
    steps = context.manifest.get("steps")
    if not isinstance(steps, Mapping):
        return None
    outputs = steps.get("export-beta1", {}).get("outputs", [])
    models = [
        item
        for item in outputs
        if isinstance(item, Mapping) and item.get("role") == "model"
    ]
    if len(models) != 1:
        return None
    return {
        "run_dir": str(context.run_dir),
        "stage_id": "export-beta1",
        "role": "model",
        "sha256": models[0].get("sha256"),
    }


class DetailedBeta2Stage:
    implementation_version = 2
    kind = "scientific"

    def __init__(self, stage_id: str, dependencies: tuple[str, ...] = ()):
        self.id, self.dependencies = stage_id, dependencies

    def enabled(self, config: Any) -> bool:
        del config
        return True

    def fingerprint_data(self, context: StageContext) -> Mapping[str, object]:
        section = {
            key: value for key, value in _section(context).items() if key != "n_jobs"
        }
        source = section.get("input_model")
        result: dict[str, object] = {
            "stage": self.id,
            "implementation_version": self.implementation_version,
            "configuration": section,
            "input_sha256": sha256_file(source)
            if isinstance(source, str) and Path(source).is_file()
            else None,
            "evidence_sha256": sha256_file(section["evidence_file"])
            if isinstance(section.get("evidence_file"), str)
            and Path(section["evidence_file"]).is_file()
            else None,
            "dependencies": {
                item: [
                    str(output.get("sha256"))
                    for output in context.manifest.get("steps", {})
                    .get(item, {})
                    .get("outputs", [])
                    if isinstance(output, Mapping)
                ]
                for item in self.dependencies
            },
        }
        upstream = section.get("upstream")
        if upstream is None:
            upstream = _reference_beta1_upstream(context)
        if isinstance(upstream, Mapping):
            try:
                result["upstream"] = upstream_fingerprint(
                    [upstream],
                    base_dir=(
                        context.config.source_path.parent
                        if context.config.source_path is not None
                        else None
                    ),
                )
            except Exception as error:
                result["upstream_error"] = f"{type(error).__name__}: {error}"
        decisions = section.get("decisions_file")
        if isinstance(decisions, str):
            from .proposals import decisions_fingerprint

            result["decisions_sha256"] = decisions_fingerprint(decisions)
        return result

    def run(self, context: StageContext, work_dir: Path) -> StageResult:
        from thg_protocol.curation.beta2 import (
            apply_expansion_plan,
            generate_expansion_plan,
            normalize_compartment_registry,
            normalize_location,
            validate_beta2,
        )
        from thg_protocol.gpr.selection import select_reaction_gpr, usable_gpr

        section = _section(context)
        if self.id == "load-beta1":
            source: Path
            external = bool(section.get("external_beta1_equivalent", False))
            implicit_upstream = _reference_beta1_upstream(context)
            if implicit_upstream is not None:
                reference = resolve_artifact(implicit_upstream)
                source = reference.path
            elif isinstance(section.get("input_model"), str):
                if not external:
                    raise ValueError(
                        "beta2.input_model requires explicit "
                        "external_beta1_equivalent=true"
                    )
                source = Path(str(section["input_model"]))
            elif isinstance(section.get("upstream"), Mapping):
                reference = resolve_artifact(
                    section["upstream"],
                    base_dir=context.config.source_path.parent
                    if context.config.source_path
                    else None,
                )
                if (
                    reference.reference.stage_id != "export-beta1"
                    or reference.reference.role != "model"
                ):
                    raise ValueError(
                        "beta2 upstream must reference the beta1 export model artifact"
                    )
                source = reference.path
            else:
                raise ValueError(
                    "beta2 requires input_model or upstream artifact reference"
                )
            if not external and isinstance(section.get("upstream"), Mapping):
                manifest = json.loads(
                    (reference.reference.run_dir / "manifest.json").read_text(
                        encoding="utf-8"
                    )
                )
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
            missing_compartments = sorted(
                {
                    str(getattr(item, "compartment", ""))
                    for item in model.metabolites
                    if not str(getattr(item, "compartment", ""))
                }
            )
            if missing_compartments:
                raise ValueError("β1 input contains metabolites without compartments")
            copied = work_dir / f"beta1-input{source.suffix.lower()}"
            shutil.copy2(source, copied)
            return StageResult(
                (
                    ("model", copied),
                    (
                        "input-gate",
                        _dump(
                            work_dir / "beta1-input-gate.json",
                            {
                                "passed": True,
                                "external_beta1_equivalent": external,
                                "exception": "external-beta1-equivalent"
                                if external
                                else None,
                                "input_sha256": sha256_file(source),
                                "gpr_validation": "passed"
                                if not invalid_gprs
                                else "external-evidence-required",
                                "invalid_gprs": sorted(invalid_gprs),
                                "compartment_mapping": "present",
                            },
                        ),
                    ),
                ),
                {"external": external, "model_id": str(model.id)},
            )
        if self.id == "collect-catalysis-evidence":
            model = _model(context, "load-beta1")
            configured = section.get("catalysis_evidence", {})
            records = dict(configured) if isinstance(configured, Mapping) else {}
            for reaction in model.reactions:
                records.setdefault(
                    str(reaction.id),
                    {
                        "ec": reaction.annotation.get(
                            "ec-code", reaction.annotation.get("ec", [])
                        )
                        if isinstance(reaction.annotation, Mapping)
                        else [],
                        "gpr": str(reaction.gene_reaction_rule or ""),
                        "source": "model-annotation",
                        "rhea_id": (
                            reaction.annotation.get("rhea")
                            or reaction.annotation.get("rhea-id")
                            or reaction.annotation.get("rhea_id")
                        )
                        if isinstance(reaction.annotation, Mapping)
                        else None,
                    },
                )
            return StageResult(
                (
                    (
                        "evidence",
                        _dump(
                            work_dir / "beta2-catalysis-evidence.json",
                            {
                                "schema_version": 1,
                                "records": {
                                    key: records[key] for key in sorted(records)
                                },
                            },
                        ),
                    ),
                ),
                {"records": len(records)},
            )
        if self.id == "collect-gpr-evidence":
            model = _model(context, "load-beta1")
            catalysis = json.loads(
                _dependency_path(
                    context, "collect-catalysis-evidence", "evidence"
                ).read_text(encoding="utf-8")
            ).get("records", {})
            mode = str(section.get("evidence_mode", "provided"))
            snapshot = _snapshot_records(section) if mode == "snapshot" else []
            snapshot_by_reaction: dict[str, list[dict[str, object]]] = {}
            for item in snapshot:
                if (
                    _record_kind(item) in {"gpr", "gpr-evidence"}
                    and item.get("reaction_id")
                ):
                    snapshot_by_reaction.setdefault(
                        str(item["reaction_id"]), []
                    ).append(item)
            requests: dict[str, list[str]] = {}
            for reaction in model.reactions:
                valid, _ = usable_gpr(reaction.gene_reaction_rule)
                if valid and mode != "live":
                    continue
                record = catalysis.get(str(reaction.id), {})
                ecs = _ec_numbers(
                    record.get("ec", []) if isinstance(record, Mapping) else []
                )
                for ec in ecs:
                    requests.setdefault(ec, []).append(str(reaction.id))
            candidates: dict[str, dict[str, object]] = {}
            source_candidates: dict[str, list[dict[str, object]]] = {}
            source_metadata: dict[str, object] = {}
            LOGGER.debug(
                "collect-gpr-evidence: %d reactions, %d unique ECs, mode=%s",
                len(model.reactions),
                len(requests),
                mode,
            )
            if mode == "live":
                from thg_protocol.gpr.lookup import get_gpr_evidence
                from thg_protocol.services.biocyc import (
                    BioCycClient,
                    StaticBioCycClient,
                )
                from thg_protocol.services.kegg import KeggClient

                biocyc_enabled = not isinstance(
                    section.get("reaction_sources"), list
                ) or "biocyc" in {
                    str(item).lower() for item in section["reaction_sources"]
                }
                biocyc_client = (
                    BioCycClient(release=_source_release(section, "biocyc"))
                    if biocyc_enabled
                    else StaticBioCycClient()
                )
                kegg_client = KeggClient()
                kegg_genes_by_ec = (
                    kegg_client.link_ecs_to_genes(sorted(requests))
                    if not biocyc_enabled
                    else {}
                )
                if not biocyc_enabled:
                    found = sum(bool(genes) for genes in kegg_genes_by_ec.values())
                    LOGGER.info(
                        "collect-gpr-evidence: KEGG returned no genes for %d/%d ECs",
                        len(requests) - found,
                        len(requests),
                    )
                for ec in tqdm(
                    sorted(requests),
                    desc=(
                        "BioCyc / KEGG GPR lookup"
                        if biocyc_enabled
                        else "KEGG GPR lookup"
                    ),
                    unit="EC",
                    disable=not LOGGER.isEnabledFor(logging.DEBUG),
                ):
                    candidate = get_gpr_evidence(
                        ec,
                        biocyc_client=biocyc_client,
                        kegg_client=kegg_client,
                        kegg_genes=kegg_genes_by_ec.get(ec)
                        if not biocyc_enabled
                        else None,
                    )
                    candidates[ec] = candidate
                    source_candidates.setdefault(ec, []).append(candidate)
                    if getattr(biocyc_client, "metadata", None):
                        source_metadata["biocyc"] = dict(biocyc_client.metadata)
            elif mode == "snapshot":
                for item in snapshot:
                    if _record_kind(item) not in {"gpr", "gpr-evidence"}:
                        continue
                    ec = str(item.get("ec", "")).strip()
                    if ec:
                        candidate = dict(item)
                        candidates[ec] = candidate
                        source_candidates.setdefault(ec, []).append(candidate)
            fallback_checkpoint = _gpr_checkpoint(
                work_dir, "fallback", candidates, source_metadata
            )
            configured_reaction_sources = section.get("reaction_sources", [])
            reaction_sources = (
                {str(item).lower() for item in configured_reaction_sources}
                if isinstance(configured_reaction_sources, list)
                else set()
            )
            LOGGER.debug(
                "collect-gpr-evidence: reaction sources=%s",
                ", ".join(sorted(reaction_sources)) or "none",
            )
            rhea_candidates: dict[str, dict[str, object]] = {}
            if "rhea" in reaction_sources:
                from thg_protocol.services.rhea import RheaClient, StaticRheaClient

                rhea_file = section.get("rhea_snapshot")
                rhea_payload: Mapping[str, object] = {}
                if isinstance(rhea_file, str) and Path(rhea_file).is_file():
                    loaded = json.loads(Path(rhea_file).read_text(encoding="utf-8"))
                    rhea_payload = (
                        loaded if isinstance(loaded, Mapping) else {"records": loaded}
                    )
                client_type = (
                    RheaClient
                    if mode == "live" and not rhea_payload
                    else StaticRheaClient
                )
                rhea = client_type(
                    release=_source_release(section, "rhea"),
                    by_ec={
                        str(key): list(value)
                        for key, value in rhea_payload.get("by_ec", {}).items()
                        if isinstance(value, list)
                    },
                    reactions=dict(rhea_payload.get("reactions", {})),
                    proteins={
                        str(key): list(value)
                        for key, value in rhea_payload.get("proteins", {}).items()
                        if isinstance(value, list)
                    },
                )
                for ec in tqdm(
                    sorted(requests),
                    desc="Rhea",
                    unit="EC",
                    disable=not LOGGER.isEnabledFor(logging.DEBUG),
                ):
                    reaction_matches = rhea.reactions_for_ec(ec)
                    if len(reaction_matches) != 1:
                        candidate = {
                            "ec": ec,
                            "candidate_gpr": "",
                            "gene_symbols": [],
                            "gene_identifiers": [],
                            "source": "rhea",
                            "status": "unresolved",
                            "confidence": "candidate",
                            "warnings": ["ambiguous-rhea-reaction"]
                            if reaction_matches
                            else ["no-rhea-reaction"],
                            "candidate_sgpr": "",
                            "sgpr_structure": None,
                            "sgpr_status": "unresolved",
                            "sgpr_sources": ["rhea"],
                        }
                        rhea_candidates[ec] = candidate
                        source_candidates.setdefault(ec, []).append(candidate)
                        candidates.setdefault(ec, candidate)
                        continue
                    match = reaction_matches[0]
                    rhea_id = str(match.get("rhea_id", match.get("id", "")))
                    proteins = rhea.proteins_for_reaction(rhea_id)
                    if not proteins and isinstance(match.get("proteins"), list):
                        proteins = list(match["proteins"])
                    genes = []
                    for protein in proteins:
                        organism = str(
                            protein.get("organism", protein.get("taxon", ""))
                        ).lower()
                        if (
                            organism
                            and "human" not in organism
                            and "9606" not in organism
                            and "homo sapiens" not in organism
                        ):
                            continue
                        gene = str(
                            protein.get(
                                "gene",
                                protein.get("gene_symbol", protein.get("symbol", "")),
                            )
                        ).strip()
                        if gene:
                            genes.append(gene)
                    genes = sorted(set(genes))
                    from thg_protocol.gpr.stoichiometry import (
                        GeneNode,
                        OrNode,
                        sgpr_to_dict,
                        to_sgpr,
                    )

                    sgpr = OrNode(
                        tuple(
                            GeneNode(gene, None, "unknown", "rhea", (rhea_id,))
                            for gene in genes
                        )
                    ) if genes else None
                    candidate = {
                        "ec": ec,
                        "rhea_id": rhea_id,
                        "candidate_gpr": " or ".join(f"({gene})" for gene in genes),
                        "gene_symbols": genes,
                        "gene_identifiers": sorted(
                            {
                                str(
                                    protein.get(
                                        "uniprot", protein.get("protein_id", "")
                                    )
                                )
                                for protein in proteins
                                if protein.get("uniprot", protein.get("protein_id"))
                            }
                        ),
                        "source": "rhea",
                        "status": "candidate" if genes else "unresolved",
                        "confidence": "reaction-matched",
                        "warnings": [],
                        "candidate_sgpr": to_sgpr(sgpr) if sgpr else "",
                        "sgpr_structure": sgpr_to_dict(sgpr) if sgpr else None,
                        "sgpr_status": "candidate" if sgpr else "unresolved",
                        "sgpr_sources": ["rhea"],
                    }
                    rhea_candidates[ec] = candidate
                    source_candidates.setdefault(ec, []).append(candidate)
                    if candidates.get(ec, {}).get("source") in {"kegg", "none"}:
                        candidates[ec] = candidate
                    else:
                        candidates.setdefault(ec, candidate)
                    if "uniprot" in reaction_sources:
                        from thg_protocol.gpr.sources.uniprot import (
                            uniprot_sgpr_evidence,
                        )

                        source_candidates.setdefault(ec, []).append(
                            uniprot_sgpr_evidence(ec, proteins=proteins).to_dict()
                        )
                if getattr(rhea, "metadata", None):
                    source_metadata["rhea"] = dict(rhea.metadata)
                if getattr(rhea, "failed_requests", 0):
                    LOGGER.warning(
                        "collect-gpr-evidence: skipped %d unavailable Rhea requests",
                        rhea.failed_requests,
                    )
            if "rhea" in reaction_sources:
                from thg_protocol.gpr.stoichiometry import (
                    GeneNode,
                    OrNode,
                    sgpr_to_dict,
                    to_sgpr,
                )
                rhea_file = section.get("rhea_snapshot")
                rhea_payload = {}
                if isinstance(rhea_file, str) and Path(rhea_file).is_file():
                    loaded = json.loads(Path(rhea_file).read_text(encoding="utf-8"))
                    rhea_payload = loaded if isinstance(loaded, Mapping) else {}
                direct_by_ec = rhea_payload.get("reactions", {})
                for reaction_id, record in catalysis.items():
                    if not isinstance(record, Mapping) or not record.get("rhea_id"):
                        continue
                    rhea_id = str(record["rhea_id"])
                    reaction = (
                        direct_by_ec.get(rhea_id, {})
                        if isinstance(direct_by_ec, Mapping)
                        else {}
                    )
                    proteins = (
                        rhea_payload.get("proteins", {}).get(rhea_id, [])
                        if isinstance(rhea_payload.get("proteins"), Mapping)
                        else []
                    )
                    proteins = [
                        item
                        for item in proteins
                        if isinstance(item, Mapping)
                        and (
                            not str(item.get("organism", item.get("taxon", "")))
                            or any(
                                marker in str(
                                    item.get("organism", item.get("taxon", ""))
                                ).lower()
                                for marker in ("human", "9606", "homo sapiens")
                            )
                        )
                    ]
                    genes = sorted(
                        {
                            str(item.get("gene", item.get("gene_symbol", "")))
                            for item in proteins
                            if isinstance(item, Mapping)
                            and item.get("gene", item.get("gene_symbol"))
                        }
                    )
                    sgpr = OrNode(
                        tuple(
                            GeneNode(gene, None, "unknown", "rhea", (rhea_id,))
                            for gene in genes
                        )
                    ) if genes else None
                    candidates.setdefault(
                        f"direct:{reaction_id}",
                        {
                            "reaction_id": reaction_id,
                            "rhea_id": rhea_id,
                            "candidate_gpr": " or ".join(
                                f"({gene})" for gene in genes
                            ),
                            "gene_symbols": genes,
                            "source": "rhea",
                            "status": "candidate" if genes else "unresolved",
                            "confidence": "reaction-matched",
                            "identity": dict(reaction)
                            if isinstance(reaction, Mapping)
                            else {},
                            "candidate_sgpr": to_sgpr(sgpr) if sgpr else "",
                            "sgpr_structure": sgpr_to_dict(sgpr) if sgpr else None,
                            "sgpr_status": "candidate" if sgpr else "unresolved",
                            "sgpr_sources": ["rhea"],
                        },
                    )
            rhea_checkpoint = _gpr_checkpoint(
                work_dir, "rhea", candidates, source_metadata
            )
            if mode == "live" and "reactome" in reaction_sources:
                from thg_protocol.services.reactome import (
                    ReactomeClient,
                    catalyst_candidate_gpr,
                    catalyst_sgpr,
                )

                reactome = ReactomeClient(
                    release=_source_release(section, "reactome")
                )
                for _ec, candidate in tqdm(
                    rhea_candidates.items(),
                    desc="Reactome",
                    unit="candidate",
                    disable=not LOGGER.isEnabledFor(logging.DEBUG),
                ):
                    rhea_id = candidate.get("rhea_id")
                    if not rhea_id:
                        continue
                    matches = reactome.reactions_for_rhea(str(rhea_id))
                    if len(matches) != 1:
                        continue
                    candidate_gpr = catalyst_candidate_gpr(matches[0])
                    if candidate_gpr:
                        reactome_evidence = catalyst_sgpr(matches[0], ec=str(_ec))
                        reactome_candidate = {
                            **reactome_evidence.to_dict(),
                            "rhea_id": candidate.get("rhea_id", ""),
                            "source_metadata": dict(reactome.metadata),
                            "sgpr_status": reactome_evidence.status,
                            "sgpr_sources": ["reactome"],
                        }
                        source_candidates.setdefault(str(_ec), []).append(
                            reactome_candidate
                        )
                if reactome.metadata:
                    source_metadata["reactome"] = dict(reactome.metadata)
                if reactome.failed_requests:
                    LOGGER.warning(
                        "collect-gpr-evidence: skipped %d unavailable "
                        "Reactome requests",
                        reactome.failed_requests,
                    )
            if "reactome" in reaction_sources:
                reactome_file = section.get("reactome_snapshot")
                if isinstance(reactome_file, str) and Path(reactome_file).is_file():
                    loaded = json.loads(Path(reactome_file).read_text(encoding="utf-8"))
                    values = (
                        loaded
                        if isinstance(loaded, list)
                        else loaded.get("records", [])
                    )
                    for item in values:
                        if not isinstance(item, Mapping) or not item.get("ec"):
                            continue
                        ec = str(item["ec"])
                        from thg_protocol.services.reactome import (
                            catalyst_candidate_gpr,
                            catalyst_sgpr,
                        )

                        candidate_gpr = catalyst_candidate_gpr(item)
                        if candidate_gpr:
                            reactome_evidence = catalyst_sgpr(item, ec=ec)
                            reactome_dict = reactome_evidence.to_dict()
                            candidate = {
                                **dict(item),
                                "candidate_gpr": candidate_gpr,
                                "candidate_sgpr": reactome_dict["candidate_sgpr"],
                                "sgpr_structure": reactome_dict["sgpr_structure"],
                                "sgpr_status": reactome_evidence.status,
                                "sgpr_sources": ["reactome"],
                                "source": "reactome",
                                "status": "resolved",
                                "confidence": "strong",
                                "source_metadata": {
                                    "source": "Reactome",
                                    "release": _source_release(section, "reactome"),
                                },
                            }
                            source_candidates.setdefault(ec, []).append(candidate)
                            candidates.setdefault(ec, candidate)
            reactome_checkpoint = _gpr_checkpoint(
                work_dir, "reactome", candidates, source_metadata
            )
            records: list[dict[str, object]] = []
            for reaction_id in sorted(str(item.id) for item in model.reactions):
                if reaction_id in snapshot_by_reaction:
                    records.extend(
                        dict(item) for item in snapshot_by_reaction[reaction_id]
                    )
                    continue
                direct = candidates.get(f"direct:{reaction_id}")
                if direct is not None:
                    records.append({**direct, "reaction_id": reaction_id})
                    continue
                record = catalysis.get(reaction_id, {})
                for ec in _ec_numbers(
                    record.get("ec", []) if isinstance(record, Mapping) else []
                ):
                    for candidate in source_candidates.get(
                        ec,
                        [
                            candidates.get(
                                ec,
                                {
                                    "ec": ec,
                                    "candidate_gpr": "",
                                    "gene_symbols": [],
                                    "gene_identifiers": [],
                                    "source": "none",
                                    "status": "unresolved",
                                    "warnings": ["evidence-mode-provided"],
                                },
                            )
                        ],
                    ):
                        record = dict(candidate)
                        record["reaction_id"] = reaction_id
                        record.setdefault("ec", ec)
                        records.append(record)
            records.sort(
                key=lambda item: (
                    str(item.get("reaction_id", "")),
                    str(item.get("ec", "")),
                    str(item.get("source", "")),
                )
            )
            LOGGER.debug(
                "collect-gpr-evidence: completed %d records, %d candidates",
                len(records),
                len(candidates),
            )
            output = work_dir / "beta2-gpr-evidence.jsonl"
            output.write_text(
                "".join(json.dumps(item, sort_keys=True) + "\n" for item in records)
                + json.dumps(
                    {
                        "record_type": "source-metadata",
                        "source_metadata": source_metadata,
                    },
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
            return StageResult(
                (
                    ("evidence", output),
                    ("fallback-checkpoint", fallback_checkpoint),
                    ("rhea-checkpoint", rhea_checkpoint),
                    ("reactome-checkpoint", reactome_checkpoint),
                ),
                {"records": len(records), "unique_ec": len(requests)},
            )
        if self.id == "resolve-gprs":
            model = _model(context, "load-beta1")
            stoich = section.get("subunit_stoichiometry", {})
            tasks = tuple(
                (
                    str(reaction.id),
                    str(reaction.gene_reaction_rule or ""),
                    dict(stoich.get(str(reaction.id), {}))
                    if isinstance(stoich, Mapping)
                    and isinstance(stoich.get(str(reaction.id), {}), Mapping)
                    else {},
                    tuple(sorted(str(gene.id) for gene in reaction.genes)),
                )
                for reaction in sorted(model.reactions, key=lambda item: str(item.id))
            )
            external = {}
            evidence_path = _dependency_path(
                context, "collect-gpr-evidence", "evidence"
            )
            for item in _jsonl(evidence_path):
                external.setdefault(str(item.get("reaction_id")), []).append(item)
            records = {}
            for reaction_id, raw, reaction_stoich, genes in tasks:
                selection = select_reaction_gpr(
                    model_gpr=raw,
                    model_genes=genes,
                    evidence=external.get(reaction_id, []),
                    configured_stoichiometry=reaction_stoich,
                )
                records[reaction_id] = {
                    **selection.to_record(),
                    "original_gpr": raw,
                    "gene_identifiers": sorted(
                        {
                            str(gene)
                            for item in external.get(reaction_id, [])
                            for gene in item.get("gene_identifiers", [])
                        }
                    ),
                    "policy": str(section.get("gpr_policy", "model-then-ec")),
                    "evidence": external.get(reaction_id, []),
                }
                reaction = model.reactions.get_by_id(reaction_id)
                if selection.gpr and selection.gpr != str(raw).strip():
                    reaction.gene_reaction_rule = selection.gpr
            from thg_protocol.io.models import save_json

            model_path = work_dir / "beta2-resolved-gprs-model.json"
            save_json(model, model_path)
            return StageResult(
                (
                    ("model", model_path),
                    (
                        "gprs",
                        _dump(
                            work_dir / "beta2-gprs.json",
                            {"schema_version": 1, "records": records},
                        ),
                    ),
                ),
                {
                    "records": len(records),
                    "conflicts": sum(
                        bool(item["conflicts"]) for item in records.values()
                    ),
                },
            )
        if self.id == "collect-location-evidence":
            configured = section.get("gene_locations", {})
            records = {}
            if isinstance(configured, Mapping):
                for key, value in sorted(
                    configured.items(), key=lambda item: str(item[0])
                ):
                    if isinstance(value, Mapping):
                        raw_locations = value.get("locations", ())
                        status = str(value.get("status", "direct"))
                        source = str(value.get("source", "configuration"))
                    else:
                        raw_locations, status, source = value, "direct", "configuration"
                    if isinstance(raw_locations, str):
                        raw_locations = [raw_locations]
                    raw_items = (
                        list(raw_locations)
                        if isinstance(raw_locations, (list, tuple, set, frozenset))
                        else []
                    )
                    locations = sorted(
                        {
                            normalize_location(
                                str(item.get("raw_location", item.get("location", "")))
                            )
                            if isinstance(item, Mapping)
                            else normalize_location(str(item))
                            for item in raw_items
                        }
                        - {""}
                    )
                    records[str(key)] = {
                        "raw_locations": [
                            dict(item) if isinstance(item, Mapping) else str(item)
                            for item in raw_items
                        ],
                        "locations": locations,
                        "status": status,
                        "source": source,
                        "confidence": "authoritative",
                        "evidence_id": f"gene-location:{key}",
                    }
            mode = str(section.get("evidence_mode", "provided"))
            for item in _snapshot_records(section) if mode == "snapshot" else []:
                if _record_kind(item) not in {
                    "location",
                    "location-evidence",
                    "gene-location",
                }:
                    continue
                gene = str(item.get("gene_id", "")).strip()
                if not gene or gene in records:
                    continue
                raw = item.get("raw_locations", item.get("locations", []))
                if isinstance(raw, str):
                    raw = [raw]
                raw = (
                    [
                        dict(value) if isinstance(value, Mapping) else str(value)
                        for value in raw
                    ]
                    if isinstance(raw, (list, tuple, set))
                    else []
                )
                records[gene] = {
                    "raw_locations": raw,
                    "locations": sorted(
                        {
                            normalize_location(
                                str(
                                    value.get("raw_location", value.get("location", ""))
                                )
                            )
                            if isinstance(value, Mapping)
                            else normalize_location(value)
                            for value in raw
                        }
                    ),
                    "status": str(item.get("status", "recorded")),
                    "source": str(item.get("source", "snapshot")),
                    "confidence": str(item.get("confidence", "recorded")),
                    "identifiers": dict(item.get("identifiers", {}))
                    if isinstance(item.get("identifiers"), Mapping)
                    else {},
                    "evidence_id": str(
                        item.get("evidence_id", f"gene-location:{gene}")
                    ),
                }
            configured_sources = section.get("location_sources", [])
            sources = (
                {str(item).lower() for item in configured_sources}
                if isinstance(configured_sources, list)
                else set()
            )
            source_metadata: dict[str, object] = {}
            model = _model(context, "resolve-gprs")
            model_genes = sorted(
                str(gene.id) for reaction in model.reactions for gene in reaction.genes
            )

            def add_external(
                gene: str, location: Mapping[str, object], source: str
            ) -> None:
                if not gene:
                    return
                record = records.get(gene)
                if record is None:
                    record = {
                        "raw_locations": [],
                        "locations": [],
                        "status": "candidate",
                        "source": source,
                        "confidence": "strong"
                        if source == "goa-uniprot"
                        else "supporting",
                        "evidence_id": f"gene-location:{gene}",
                    }
                    records[gene] = record
                evidence = record.setdefault("supporting_evidence", [])
                if isinstance(evidence, list):
                    item = {"source": source, **dict(location)}
                    if item not in evidence:
                        evidence.append(item)
                if record.get("source") == "configuration":
                    return
                raw = dict(location)
                record.setdefault("raw_locations", []).append(raw)
                value = str(
                    raw.get("raw_location", raw.get("location", raw.get("go_id", "")))
                )
                normalized = normalize_location(value) if value else ""
                if normalized and normalized not in record.setdefault("locations", []):
                    record["locations"].append(normalized)

            if "goa" in sources:
                from thg_protocol.services.goa import (
                    GOAClient,
                    StaticGOAClient,
                    parse_gaf,
                )

                annotations = []
                annotation_file = section.get("go_annotation_file")
                if isinstance(annotation_file, str) and Path(annotation_file).is_file():
                    annotations = parse_gaf(
                        Path(annotation_file).read_text(encoding="utf-8"),
                        source_release=str(
                            section.get("source_releases", {}).get("goa", {}).get(
                                "release", ""
                            )
                            if isinstance(section.get("source_releases"), Mapping)
                            and isinstance(
                                section.get("source_releases", {}).get("goa"),
                                Mapping,
                            )
                            else section.get("compartment_ontology_version", "")
                        ),
                    )
                elif mode == "live":
                    goa_release = section.get("source_releases", {}).get("goa", {})
                    goa_release = (
                        goa_release.get("release", "")
                        if isinstance(goa_release, Mapping)
                        else ""
                    )
                    goa_client = GOAClient(
                        release=str(goa_release)
                    )
                    annotations = goa_client.annotations_for(model_genes)
                    if goa_client.metadata:
                        source_metadata["goa"] = dict(goa_client.metadata)
                for annotation in StaticGOAClient(annotations).annotations_for(
                    model_genes
                ):
                    gene = (
                        annotation.symbol
                        if annotation.symbol in model_genes
                        else annotation.object_id
                    )
                    add_external(
                        gene,
                        {
                            "go_id": annotation.go_id,
                            "raw_location": annotation.go_id,
                            "aspect": annotation.aspect,
                            "qualifier": annotation.qualifier,
                            "evidence_code": annotation.evidence_code,
                            "reference": annotation.reference,
                            "assigned_by": annotation.assigned_by,
                            "source_release": annotation.source_release,
                        },
                        "goa-uniprot",
                    )
            if "uniprot" in sources:
                from thg_protocol.services.uniprot import (
                    StaticUniProtClient,
                    UniProtClient,
                )

                annotations: list[object] = []
                snapshot_file = section.get("uniprot_snapshot")
                if isinstance(snapshot_file, str) and Path(snapshot_file).is_file():
                    value = json.loads(Path(snapshot_file).read_text(encoding="utf-8"))
                    annotations = (
                        value if isinstance(value, list) else value.get("records", [])
                    )
                elif mode == "live":
                    uniprot_client = UniProtClient(
                        release=_source_release(section, "uniprot")
                    )
                    annotations = uniprot_client.annotations_for(
                        model_genes, progress=LOGGER.isEnabledFor(logging.DEBUG)
                    )
                    if uniprot_client.metadata:
                        source_metadata["uniprot"] = dict(uniprot_client.metadata)
                for annotation in StaticUniProtClient(annotations).annotations_for(
                    model_genes
                ):
                    add_external(
                        annotation.gene_id,
                        {
                            "raw_location": annotation.raw_location,
                            "go_id": annotation.go_id,
                            "sl_id": annotation.sl_id,
                            "protein_id": annotation.protein_id,
                            "evidence_code": annotation.evidence_code,
                            "reference": annotation.reference,
                            "source_release": annotation.source_release,
                        },
                        "uniprot",
                    )
            if mode == "live":
                from thg_protocol.gpr.location import resolve_locations
                from thg_protocol.services.location import LocationClient

                registry = normalize_compartment_registry(
                    section.get("compartments")
                    if isinstance(section.get("compartments"), Mapping)
                    else None
                )
                allowed = set(registry.values())
                location_client = LocationClient()
                for gene in tqdm(
                    sorted(set(model_genes) - set(records)),
                    desc="UniProt legacy locations",
                    unit="gene",
                    disable=not LOGGER.isEnabledFor(logging.DEBUG),
                ):
                    if gene.startswith("ENS"):
                        plain = {}
                    else:
                        try:
                            plain = resolve_locations(
                                gene,
                                [gene],
                                [gene],
                                allowed_locations=allowed,
                                location_client=location_client,
                                fallback_location=section.get("fallback_location")
                                if isinstance(section.get("fallback_location"), str)
                                else None,
                            )[1]
                        except Exception as error:
                            plain = {}
                            records[gene] = {
                                "raw_locations": [],
                                "locations": [],
                                "status": "unresolved",
                                "source": "uniprot",
                                "confidence": "candidate",
                                "warnings": [str(error)],
                                "evidence_id": f"gene-location:{gene}",
                            }
                    if gene not in records:
                        locations = sorted(plain)
                        records[gene] = {
                            "raw_locations": locations,
                            "locations": locations,
                            "status": "resolved" if locations else "unresolved",
                            "source": "uniprot",
                            "confidence": "supporting",
                            "evidence_id": f"gene-location:{gene}",
                        }
            return StageResult(
                (
                    (
                        "evidence",
                        _dump(
                            work_dir / "beta2-location-evidence.json",
                            {
                                "schema_version": 1,
                                "ontology_version": str(
                                    section.get(
                                        "compartment_ontology_version",
                                        "beta2-compartments-1",
                                    )
                                ),
                                "gene_locations": records,
                                "source_metadata": source_metadata,
                                "source": "configuration"
                                if mode == "provided"
                                else mode,
                            },
                        ),
                    ),
                ),
                {"genes": len(records)},
            )
        if self.id == "normalize-compartments":
            from thg_protocol.curation.go import load_obo

            registry = normalize_compartment_registry(
                section.get("compartments")
                if isinstance(section.get("compartments"), Mapping)
                else None
            )
            go_terms = {
                str(key): str(value)
                for key, value in (
                    section.get("compartment_go_terms", {}).items()
                    if isinstance(section.get("compartment_go_terms"), Mapping)
                    else ()
                )
            }
            go_graph = (
                dict(section.get("go_graph", {}))
                if isinstance(section.get("go_graph"), Mapping)
                else {}
            )
            source_releases = (
                dict(section.get("source_releases", {}))
                if isinstance(section.get("source_releases"), Mapping)
                else {}
            )
            ontology_file = section.get("go_ontology_file")
            if isinstance(ontology_file, str) and Path(ontology_file).is_file():
                go_graph = load_obo(ontology_file)
            elif go_terms and str(section.get("evidence_mode", "provided")) == "live":
                from thg_protocol.services.go import GOALoader

                release_info = section.get("source_releases", {})
                release_info = (
                    release_info.get("go", release_info.get("go_ontology", {}))
                    if isinstance(release_info, Mapping)
                    else {}
                )
                release_info = release_info if isinstance(release_info, Mapping) else {}
                loader = GOALoader(
                    url=str(
                        section.get("go_ontology_url", release_info.get("url", ""))
                    )
                    or None,
                    release=str(
                        section.get(
                            "go_ontology_release", release_info.get("release", "")
                        )
                    )
                    or None,
                )
                go_graph = dict(loader.load())
                if loader.metadata:
                    source_releases["go"] = loader.metadata
            if str(section.get("evidence_mode", "provided")) == "snapshot":
                metadata = next(
                    (
                        item
                        for item in _snapshot_records(section)
                        if _record_kind(item) == "metadata"
                    ),
                    {},
                )
                if not go_graph and isinstance(metadata.get("go_graph"), Mapping):
                    go_graph = dict(metadata["go_graph"])
                if not go_terms and isinstance(
                    metadata.get("compartment_go_terms"), Mapping
                ):
                    go_terms = dict(metadata["compartment_go_terms"])
            for source_key in (
                "go_ontology_file",
                "go_annotation_file",
                "uniprot_snapshot",
                "rhea_snapshot",
                "reactome_snapshot",
            ):
                source_file = section.get(source_key)
                if not isinstance(source_file, str) or not Path(source_file).is_file():
                    continue
                source_name = {
                    "go_ontology_file": "go",
                    "go_annotation_file": "goa",
                    "uniprot_snapshot": "uniprot",
                    "rhea_snapshot": "rhea",
                    "reactome_snapshot": "reactome",
                }[source_key]
                current = source_releases.get(source_name, {})
                current = (
                    dict(current)
                    if isinstance(current, Mapping)
                    else {"release": current}
                )
                current.update(
                    {"file": source_file, "sha256": sha256_file(source_file)}
                )
                source_releases[source_name] = current
            payload = {
                "schema_version": 1,
                "ontology_version": str(
                    section.get("compartment_ontology_version", "beta2-compartments-1")
                ),
                "compartments": registry,
                "compartment_go_terms": go_terms,
                "go_graph": go_graph,
                "source_releases": source_releases,
            }
            return StageResult(
                (("registry", _dump(work_dir / "compartment-registry.json", payload)),),
                {
                    "compartments": len(registry),
                    "ontology_version": payload["ontology_version"],
                },
            )
        if self.id == "collect-reaction-location-evidence":
            configured = section.get("reaction_location_evidence", {})
            records: dict[str, dict[str, object]] = {}
            if isinstance(configured, Mapping):
                for reaction_id, value in configured.items():
                    values = value if isinstance(value, list) else [value]
                    records[str(reaction_id)] = {
                        "reaction_id": str(reaction_id),
                        "source": "configuration",
                        "locations": [
                            dict(item)
                            if isinstance(item, Mapping)
                            else {"raw_location": str(item)}
                            for item in values
                        ],
                        "status": "candidate",
                        "confidence": "authoritative",
                    }
            if str(section.get("evidence_mode", "provided")) == "snapshot":
                for item in _snapshot_records(section):
                    if _record_kind(item) not in {
                        "reaction-location",
                        "reaction-location-evidence",
                    }:
                        continue
                    reaction_id = str(item.get("reaction_id", ""))
                    if reaction_id and reaction_id not in records:
                        records[reaction_id] = dict(item)
            configured_sources = section.get("reaction_sources", [])
            sources = (
                {str(item).lower() for item in configured_sources}
                if isinstance(configured_sources, list)
                else set()
            )
            source_metadata: dict[str, object] = {}
            if "reactome" in sources:
                snapshot_file = section.get("reactome_snapshot")
                if isinstance(snapshot_file, str) and Path(snapshot_file).is_file():
                    payload = json.loads(
                        Path(snapshot_file).read_text(encoding="utf-8")
                    )
                    values = (
                        payload
                        if isinstance(payload, list)
                        else payload.get("records", [])
                    )
                    for item in values:
                        if not isinstance(item, Mapping):
                            continue
                        reaction_id = str(item.get("reaction_id", ""))
                        if not reaction_id:
                            continue
                        if reaction_id not in records:
                            records[reaction_id] = {
                                "reaction_id": reaction_id,
                                "source": "reactome",
                                "locations": [dict(item)],
                                "status": "candidate",
                                "confidence": "strong",
                            }
                        else:
                            records[reaction_id].setdefault(
                                "supporting_evidence", []
                            ).append({"source": "reactome", **dict(item)})
            if str(section.get("evidence_mode", "provided")) == "live":
                from thg_protocol.services.biocyc import (
                    BioCycClient,
                    StaticBioCycClient,
                )

                biocyc_enabled = (
                    not isinstance(section.get("reaction_sources"), list)
                    or "biocyc" in sources
                )
                client = (
                    BioCycClient(release=_source_release(section, "biocyc"))
                    if biocyc_enabled
                    else StaticBioCycClient()
                )
                if "reactome" in sources:
                    from thg_protocol.services.reactome import ReactomeClient

                    reactome = ReactomeClient(
                        release=_source_release(section, "reactome")
                    )
                    for record in records.values():
                        reactome_id = record.get("reactome_id")
                        if not reactome_id:
                            continue
                        payload = reactome.reaction(str(reactome_id)) or {}
                        location = payload.get(
                            "location", payload.get("compartment", {})
                        )
                        if isinstance(location, Mapping):
                            location = dict(location)
                        elif location:
                            location = {"raw_location": str(location)}
                        if isinstance(location, Mapping):
                            record.setdefault("locations", []).append(location)
                    if reactome.metadata:
                        source_metadata["reactome"] = dict(reactome.metadata)
                for record in records.values():
                    graph = (
                        dict(section.get("cco_graph", {}))
                        if isinstance(section.get("cco_graph"), Mapping)
                        else {}
                    )
                    for location in record.get("locations", []):
                        if not isinstance(location, Mapping) or not location.get(
                            "cco_id"
                        ):
                            continue
                        pending = [str(location["cco_id"])]
                        seen: set[str] = set()
                        while pending:
                            identifier = pending.pop(0)
                            if identifier in seen or identifier in graph:
                                continue
                            seen.add(identifier)
                            term = client.get_cco(identifier)
                            if term is None:
                                continue
                            graph[identifier] = dict(term)
                            for edge in (
                                "component_of",
                                "superclasses",
                            ):
                                pending.extend(
                                    str(item) for item in term.get(edge, []) or []
                                )
                    if graph:
                        record["cco_graph"] = graph
                if getattr(client, "metadata", None):
                    source_metadata["biocyc"] = dict(client.metadata)
            output = work_dir / "beta2-reaction-location-evidence.jsonl"
            output.write_text(
                "".join(
                    json.dumps(item, sort_keys=True) + "\n"
                    for _, item in sorted(records.items())
                ),
                encoding="utf-8",
            )
            with output.open("a", encoding="utf-8") as handle:
                handle.write(
                    json.dumps(
                        {
                            "record_type": "source-metadata",
                            "source_metadata": source_metadata,
                        },
                        sort_keys=True,
                    )
                    + "\n"
                )
            return StageResult((("evidence", output),), {"reactions": len(records)})
        if self.id == "resolve-compartment-evidence":
            from thg_protocol.curation.beta2 import resolve_compartment
            from thg_protocol.curation.go import resolve_go_compartment

            registry_payload = json.loads(
                _dependency_path(
                    context, "normalize-compartments", "registry"
                ).read_text(encoding="utf-8")
            )
            registry = registry_payload["compartments"]
            go_graph = registry_payload.get("go_graph", {})
            go_terms = registry_payload.get("compartment_go_terms", {})
            graph = section.get("cco_graph", {})
            if str(section.get("evidence_mode", "provided")) == "snapshot":
                for item in _snapshot_records(section):
                    if _record_kind(item) == "metadata" and isinstance(
                        item.get("cco_graph"), Mapping
                    ):
                        graph = item["cco_graph"]
                        break
            if (
                not isinstance(graph, Mapping)
                and str(section.get("evidence_mode", "provided")) == "snapshot"
            ):
                graph = {}
            location_payload = json.loads(
                _dependency_path(
                    context, "collect-location-evidence", "evidence"
                ).read_text(encoding="utf-8")
            )
            reaction_records = _jsonl(
                _dependency_path(
                    context, "collect-reaction-location-evidence", "evidence"
                )
            )
            if not isinstance(graph, Mapping):
                graph = {}
            if not graph:
                for item in reaction_records:
                    if isinstance(item.get("cco_graph"), Mapping):
                        graph = item["cco_graph"]
                        break

            def resolve_location(item: Mapping[str, object]) -> dict[str, object]:
                raw_location = str(item.get("raw_location", item.get("location", "")))
                go_id = str(item.get("go_id", "")) or None
                if (
                    isinstance(go_terms, Mapping)
                    and (go_terms or go_id)
                    and isinstance(go_graph, Mapping)
                ):
                    return resolve_go_compartment(
                        raw_location,
                        go_id,
                        go_graph,
                        go_terms,
                        registry,
                    )
                return resolve_compartment(
                    raw_location,
                    str(item["cco_id"]) if item.get("cco_id") else None,
                    graph,
                    registry,
                )

            snapshot_resolution: dict[str, list[dict[str, object]]] = {}
            for item in _snapshot_records(section):
                gene = str(item.get("gene_id", ""))
                if (
                    str(section.get("evidence_mode", "provided")) == "snapshot"
                    and _record_kind(item) == "compartment-resolution"
                    and gene
                ):
                    snapshot_resolution.setdefault(gene, []).append(item)
            gene_locations: dict[str, dict[str, object]] = {}
            resolution_records: list[dict[str, object]] = []
            unresolved: list[str] = []
            for gene, record in sorted(
                location_payload.get("gene_locations", {}).items()
            ):
                targets = []
                recorded = snapshot_resolution.get(str(gene), [])
                if recorded:
                    targets = sorted(
                        {
                            str(item.get("target_compartment_name"))
                            for item in recorded
                            if item.get("status") == "resolved"
                            and item.get("target_compartment_name")
                        }
                    )
                    gene_locations[gene] = dict(record)
                    gene_locations[gene]["locations"] = targets
                    resolution_records.extend(dict(item) for item in recorded)
                    unresolved.extend(
                        f"{gene}:{item.get('reason', 'unresolved-location')}"
                        for item in recorded
                        if item.get("status") != "resolved"
                    )
                    continue
                raw = (
                    record.get("raw_locations", record.get("locations", []))
                    if isinstance(record, Mapping)
                    else []
                )
                if isinstance(raw, str):
                    raw = [raw]
                for value in raw if isinstance(raw, (list, tuple, set)) else []:
                    item = (
                        value if isinstance(value, Mapping) else {"raw_location": value}
                    )
                    resolved = resolve_location(item)
                    resolved.update(
                        {
                            "gene_id": gene,
                            "source": record.get("source", "configuration")
                            if isinstance(record, Mapping)
                            else "configuration",
                        }
                    )
                    resolution_records.append(resolved)
                    if resolved.get("status") == "resolved":
                        targets.append(str(resolved["target_compartment_name"]))
                    else:
                        unresolved.append(
                            f"{gene}:{resolved.get('reason', 'unresolved-location')}"
                        )
                gene_locations[gene] = (
                    dict(record) if isinstance(record, Mapping) else {}
                )
                gene_locations[gene]["locations"] = sorted(set(targets))
                if len(set(targets)) > 1:
                    gene_locations[gene]["status"] = "conflicting"
                    resolution_records.append(
                        {
                            "gene_id": gene,
                            "status": "location-conflict",
                            "reason": "same-precedence-evidence-disagree",
                            "candidate_targets": sorted(set(targets)),
                        }
                    )
                    unresolved.append(f"{gene}:same-precedence-evidence-disagree")
            reaction_resolutions = []
            recorded_reactions: dict[str, list[dict[str, object]]] = {}
            for item in _snapshot_records(section):
                reaction_id = str(item.get("reaction_id", ""))
                if (
                    str(section.get("evidence_mode", "provided")) == "snapshot"
                    and _record_kind(item) == "compartment-resolution"
                    and reaction_id
                ):
                    recorded_reactions.setdefault(reaction_id, []).append(item)
            for record in reaction_records:
                if str(record.get("reaction_id")) in recorded_reactions:
                    reaction_resolutions.extend(
                        dict(item)
                        for item in recorded_reactions[str(record.get("reaction_id"))]
                    )
                    continue
                for item in (
                    record.get("locations", [])
                    if isinstance(record.get("locations", []), list)
                    else []
                ):
                    item = item if isinstance(item, Mapping) else {"raw_location": item}
                    resolved = resolve_location(item)
                    resolved.update(
                        {
                            "reaction_id": record.get("reaction_id"),
                            "source": record.get("source", "biocyc"),
                        }
                    )
                    reaction_resolutions.append(resolved)
            gpr_payload = json.loads(
                _dependency_path(context, "resolve-gprs", "gprs").read_text(
                    encoding="utf-8"
                )
            )
            reaction_targets: dict[str, set[str]] = {}
            for item in reaction_resolutions:
                if item.get("status") == "resolved":
                    reaction_targets.setdefault(
                        str(item.get("reaction_id")), set()
                    ).add(str(item.get("target_compartment_name")))
            gene_targets = {
                gene: set(record.get("locations", []))
                for gene, record in gene_locations.items()
                if isinstance(record, Mapping)
            }
            for reaction_id, record in gpr_payload.get("records", {}).items():
                genes = (
                    set(record.get("genes", []))
                    if isinstance(record, Mapping)
                    else set()
                )
                from_genes = set().union(
                    *(gene_targets.get(gene, set()) for gene in genes)
                )
                from_reaction = reaction_targets.get(str(reaction_id), set())
                if (
                    from_genes
                    and from_reaction
                    and from_genes.isdisjoint(from_reaction)
                ):
                    resolution_records.append(
                        {
                            "reaction_id": reaction_id,
                            "status": "location-conflict",
                            "reason": "gene-and-reaction-evidence-disagree",
                            "gene_targets": sorted(from_genes),
                            "reaction_targets": sorted(from_reaction),
                        }
                    )
            output = {
                "schema_version": 1,
                "ontology_version": str(
                    section.get("compartment_ontology_version", "beta2-compartments-1")
                ),
                "gene_locations": gene_locations,
                "reaction_locations": reaction_resolutions,
                "evidence": resolution_records + reaction_resolutions,
                "unresolved": sorted(
                    unresolved
                    + [
                        f"{item.get('reaction_id')}:{item.get('reason')}"
                        for item in reaction_resolutions
                        if item.get("status") != "resolved"
                    ]
                ),
            }
            return StageResult(
                (
                    (
                        "evidence",
                        _dump(
                            work_dir / "beta2-compartment-resolution-evidence.json",
                            output,
                        ),
                    ),
                ),
                {
                    "records": len(output["evidence"]),
                    "unresolved": len(output["unresolved"]),
                },
            )
        if self.id == "infer-complex-and-isoenzyme-locations":
            gprs = json.loads(
                _dependency_path(context, "resolve-gprs", "gprs").read_text(
                    encoding="utf-8"
                )
            )
            raw_locations = json.loads(
                _dependency_path(
                    context, "resolve-compartment-evidence", "evidence"
                ).read_text(encoding="utf-8")
            )["gene_locations"]
            allow_conflicts = (
                str(section.get("uncertainty_policy", "reject-conflicts"))
                == "allow-conflicts"
            )
            locations = {
                gene: (
                    value.get("locations", [])
                    if isinstance(value, Mapping)
                    and (
                        str(value.get("status", "direct")) != "conflicting"
                        or allow_conflicts
                    )
                    else value
                    if not isinstance(value, Mapping)
                    else []
                )
                for gene, value in raw_locations.items()
            }
            resolved = {}
            evidence = []
            unresolved = []
            tasks = tuple(
                (
                    str(reaction_id),
                    str(record["gpr"]),
                    tuple(
                        (gene, locations[gene])
                        for gene in (str(item) for item in record.get("genes", ()))
                        if gene in locations
                    ),
                    tuple(
                        (gene, raw_locations[gene])
                        for gene in (str(item) for item in record.get("genes", ()))
                        if gene in raw_locations
                    ),
                    str(section["fallback_location"])
                    if isinstance(section.get("fallback_location"), str)
                    else None,
                    dict(record),
                )
                for reaction_id, record in sorted(gprs["records"].items())
            )
            for (
                reaction_id,
                reaction_result,
                reaction_evidence,
                reaction_unresolved,
            ) in parallel_map(
                _resolve_location_payload,
                tasks,
                n_jobs=int(section.get("n_jobs", 1)),
            ):
                resolved[reaction_id] = reaction_result
                evidence.extend(reaction_evidence)
                unresolved.extend(reaction_unresolved)
            compartment_payload = json.loads(
                _dependency_path(
                    context, "resolve-compartment-evidence", "evidence"
                ).read_text(encoding="utf-8")
            )
            for item in compartment_payload.get("reaction_locations", []):
                reaction_id = str(item.get("reaction_id", ""))
                target = str(item.get("target_compartment_name", ""))
                if (
                    item.get("status") == "resolved"
                    and reaction_id in resolved
                    and target
                    and not resolved[reaction_id]["rules"]
                ):
                    gpr = str(gprs["records"].get(reaction_id, {}).get("gpr", ""))
                    if gpr:
                        resolved[reaction_id]["rules"] = {target: gpr}
                        evidence.append(
                            {
                                "reaction_id": reaction_id,
                                **item,
                                "status": "reaction-evidence-candidate",
                            }
                        )
            output = {
                "schema_version": 1,
                "rules": resolved,
                "evidence": evidence,
                "unresolved": sorted(unresolved),
            }
            return StageResult(
                (
                    (
                        "locations",
                        _dump(work_dir / "beta2-resolved-locations.json", output),
                    ),
                ),
                {"reactions": len(resolved), "unresolved": len(unresolved)},
            )
        if self.id == "generate-expansion-plan":
            from thg_protocol.workflow.ids import DeterministicIdRegistry

            registry_payload = json.loads(
                _dependency_path(
                    context, "normalize-compartments", "registry"
                ).read_text(encoding="utf-8")
            )
            registry = registry_payload.get("compartments", registry_payload)
            raw_rules = json.loads(
                _dependency_path(
                    context, "infer-complex-and-isoenzyme-locations", "locations"
                ).read_text(encoding="utf-8")
            )["rules"]
            rules = {
                reaction: (
                    value.get("rules", {}) if isinstance(value, Mapping) else value
                )
                for reaction, value in raw_rules.items()
            }
            id_registry = DeterministicIdRegistry()
            plans = generate_expansion_plan(
                _model(context, "resolve-gprs"),
                rules,
                registry=id_registry,
                compartments=registry,
                subunit_stoichiometry=section.get("subunit_stoichiometry")
                if isinstance(section.get("subunit_stoichiometry"), Mapping)
                else None,
            )
            output = work_dir / "beta2-expansion-plan.jsonl"
            output.write_text(
                "\n".join(json.dumps(item, sort_keys=True) for item in plans)
                + ("\n" if plans else ""),
                encoding="utf-8",
            )
            proposals = work_dir / "beta2-proposals.jsonl"
            proposal_records = []
            for item in plans:
                proposal_records.append(
                    {
                        "proposal_id": item["proposal_id"],
                        "operation": "expand"
                        if item.get("action") == "create"
                        else "retain",
                        "object_type": "reaction",
                        "object_id": str(item["reaction_id"]),
                        "before": {},
                        "after": dict(item),
                        "evidence": [str(item.get("evidence_id", ""))]
                        if item.get("evidence_id")
                        else [],
                        "confidence": "recorded",
                        "policy": str(item.get("reason", "policy")),
                        "stage": self.id,
                        "status": "proposed",
                        "reason": str(item.get("reason", "")),
                        "metadata": {"reaction_class": item.get("reaction_class")},
                    }
                )
            proposals.write_text(
                "\n".join(json.dumps(item, sort_keys=True) for item in proposal_records)
                + ("\n" if proposal_records else ""),
                encoding="utf-8",
            )
            registry_path = _dump(
                work_dir / "beta2-id-registry.json", id_registry.to_dict()
            )
            return StageResult(
                (
                    ("plan", output),
                    ("proposals", proposals),
                    ("id-registry", registry_path),
                ),
                {
                    "plans": len(plans),
                    "proposals": len(proposal_records),
                    "ids": len(id_registry.mappings),
                },
            )
        if self.id == "apply-expansion-decisions":
            plan = _dependency_path(context, "generate-expansion-plan", "plan")
            decisions = {
                "mode": str(section.get("mode", "apply-all")),
                "plan_sha256": sha256_file(plan),
                "approved": [],
                "decisions_file": section.get("decisions_file"),
            }
            if isinstance(section.get("decisions_file"), str):
                from .proposals import read_decisions

                proposal_decisions = {
                    item.proposal_id: {
                        "action": item.action,
                        "replacement": item.replacement,
                    }
                    for item in read_decisions(str(section["decisions_file"]))
                }
                plan_ids = {
                    json.loads(line).get("proposal_id")
                    for line in plan.read_text(encoding="utf-8").splitlines()
                    if line.strip()
                }
                unknown = sorted(set(proposal_decisions) - plan_ids)
                if unknown:
                    raise ValueError(
                        "β2 decisions reference unknown proposals: "
                        + ", ".join(unknown)
                    )
                decisions["proposal_decisions"] = proposal_decisions
            else:
                decisions["proposal_decisions"] = {}
            return StageResult(
                (("decisions", _dump(work_dir / "beta2-decisions.json", decisions)),),
                decisions,
            )
        if self.id == "apply-expansion":
            plans = [
                json.loads(line)
                for line in _dependency_path(context, "generate-expansion-plan", "plan")
                .read_text(encoding="utf-8")
                .splitlines()
                if line.strip()
            ]
            decisions = json.loads(
                _dependency_path(
                    context, "apply-expansion-decisions", "decisions"
                ).read_text(encoding="utf-8")
            )
            model, ledger = apply_expansion_plan(
                _model(context, "resolve-gprs"),
                plans,
                mode=str(decisions["mode"]),
                decisions=decisions.get("proposal_decisions", {}),
            )
            from thg_protocol.io.models import save_json

            output = work_dir / "expanded-model.json"
            save_json(model, output)
            ledger_path = work_dir / "beta2-change-ledger.jsonl"
            ledger_path.write_text(
                "\n".join(json.dumps(item, sort_keys=True) for item in ledger)
                + ("\n" if ledger else ""),
                encoding="utf-8",
            )
            return StageResult(
                (("model", output), ("ledger", ledger_path)),
                {"applied": sum(item.get("status") == "applied" for item in ledger)},
            )
        if self.id == "consolidate-expanded-model":
            source = _dependency_path(context, "apply-expansion", "model")
            output = work_dir / "consolidated-model.json"
            shutil.copy2(source, output)
            prior = _dependency_path(context, "apply-expansion", "ledger").read_text(
                encoding="utf-8"
            )
            ledger = work_dir / "consolidated-change-ledger.jsonl"
            ledger.write_text(
                prior
                + json.dumps(
                    {
                        "operation": "consolidate",
                        "status": "applied",
                        "deterministic": True,
                        "removed_orphans": False,
                    },
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
            return StageResult(
                (("model", output), ("ledger", ledger)),
                {"consolidated": True, "removed_orphans": False},
            )
        if self.id == "validate-beta2":
            plans = [
                json.loads(line)
                for line in _dependency_path(context, "generate-expansion-plan", "plan")
                .read_text(encoding="utf-8")
                .splitlines()
                if line.strip()
            ]
            ledger = [
                json.loads(line)
                for line in _dependency_path(
                    context, "consolidate-expanded-model", "ledger"
                )
                .read_text(encoding="utf-8")
                .splitlines()
                if line.strip()
            ]
            validation = validate_beta2(
                _model(context, "consolidate-expanded-model"),
                plans,
                ledger,
                baseline=_model(context, "load-beta1"),
                run_solver_checks=bool(section.get("run_solver_checks", False)),
            )
            output = _dump(work_dir / "beta2-validation.json", validation)
            return StageResult((("validation", output),), validation)
        if self.id == "export-beta2":
            model_source = _dependency_path(
                context, "consolidate-expanded-model", "model"
            )
            json_path = work_dir / "thg-beta2-candidate.json"
            shutil.copy2(model_source, json_path)
            from thg_protocol.io.models import load_model, save_sbml

            model = load_model(model_source)
            xml_path = work_dir / "thg-beta2-candidate.xml"
            save_sbml(model, xml_path)
            _load_cobra_model(json_path)
            load_model(xml_path)
            for role, stage, name in (
                (
                    "gpr-evidence",
                    "collect-gpr-evidence",
                    "gpr-evidence.jsonl",
                ),
                (
                    "reaction-location-evidence",
                    "collect-reaction-location-evidence",
                    "reaction-location-evidence.jsonl",
                ),
                (
                    "compartment-resolution-evidence",
                    "resolve-compartment-evidence",
                    "compartment-resolution-evidence.json",
                ),
                (
                    "expansion-plan",
                    "generate-expansion-plan",
                    "beta2-expansion-plan.jsonl",
                ),
                ("proposals", "generate-expansion-plan", "beta2-proposals.jsonl"),
                ("id-registry", "generate-expansion-plan", "beta2-id-registry.json"),
                ("ledger", "consolidate-expanded-model", "beta2-change-ledger.jsonl"),
                ("validation", "validate-beta2", "beta2-validation.json"),
                (
                    "location-evidence",
                    "infer-complex-and-isoenzyme-locations",
                    "beta2-location-evidence.jsonl",
                ),
            ):
                source = _dependency_path(
                    context,
                    stage,
                    "plan"
                    if role == "expansion-plan"
                    else "proposals"
                    if role == "proposals"
                    else "id-registry"
                    if role == "id-registry"
                    else "ledger"
                    if role == "ledger"
                    else "validation"
                    if role == "validation"
                    else "evidence"
                    if role in {"gpr-evidence", "reaction-location-evidence"}
                    else "evidence"
                    if role == "compartment-resolution-evidence"
                    else "locations",
                )
                destination = work_dir / name
                if role == "location-evidence":
                    payload = json.loads(source.read_text(encoding="utf-8"))
                    destination.write_text(
                        "\n".join(
                            json.dumps(item, sort_keys=True)
                            for item in payload.get("evidence", [])
                        )
                        + ("\n" if payload.get("evidence") else ""),
                        encoding="utf-8",
                    )
                else:
                    shutil.copy2(source, destination)
            snapshot_path = work_dir / "beta2-evidence-snapshot.jsonl"
            snapshot_records: list[dict[str, object]] = []
            for record in _jsonl(work_dir / "gpr-evidence.jsonl"):
                snapshot_records.append({"record_type": "gpr", **record})
            catalysis_payload = json.loads(
                _dependency_path(
                    context, "collect-catalysis-evidence", "evidence"
                ).read_text(encoding="utf-8")
            )
            for reaction_id, record in sorted(
                catalysis_payload.get("records", {}).items()
            ):
                snapshot_records.append(
                    {"record_type": "catalysis", "reaction_id": reaction_id, **record}
                )
            gpr_payload = json.loads(
                _dependency_path(context, "resolve-gprs", "gprs").read_text(
                    encoding="utf-8"
                )
            )
            for reaction_id, record in sorted(gpr_payload.get("records", {}).items()):
                snapshot_records.append(
                    {
                        "record_type": "selected-gpr",
                        "reaction_id": reaction_id,
                        **record,
                    }
                )
            for record in _jsonl(work_dir / "reaction-location-evidence.jsonl"):
                snapshot_records.append({"record_type": "reaction-location", **record})
            location_payload = json.loads(
                _dependency_path(
                    context, "collect-location-evidence", "evidence"
                ).read_text(encoding="utf-8")
            )
            for gene, record in sorted(
                location_payload.get("gene_locations", {}).items()
            ):
                snapshot_records.append(
                    {"record_type": "location", "gene_id": gene, **record}
                )
            resolution_payload = json.loads(
                (work_dir / "compartment-resolution-evidence.json").read_text(
                    encoding="utf-8"
                )
            )
            registry_payload = json.loads(
                _dependency_path(
                    context, "normalize-compartments", "registry"
                ).read_text(encoding="utf-8")
            )
            source_releases = dict(registry_payload.get("source_releases", {}))

            def merge_source_metadata(value: object) -> None:
                if not isinstance(value, Mapping):
                    return
                if "source" in value:
                    source = str(value.get("source", "")).lower()
                    if source:
                        current = source_releases.get(source, {})
                        current = dict(current) if isinstance(current, Mapping) else {}
                        current.update(dict(value))
                        source_releases[source] = current
                    return
                for source, metadata in value.items():
                    if not isinstance(metadata, Mapping):
                        continue
                    current = source_releases.get(str(source), {})
                    current = dict(current) if isinstance(current, Mapping) else {}
                    current.update(dict(metadata))
                    source_releases[str(source)] = current

            for record in _jsonl(work_dir / "gpr-evidence.jsonl"):
                merge_source_metadata(record.get("source_metadata"))
            for record in _jsonl(work_dir / "reaction-location-evidence.jsonl"):
                merge_source_metadata(record.get("source_metadata"))
            merge_source_metadata(location_payload.get("source_metadata"))
            go_release_path = _dump(
                work_dir / "go-release.json",
                {
                    "ontology_version": registry_payload.get("ontology_version"),
                    "source_releases": source_releases,
                    "go_ontology_file": section.get("go_ontology_file"),
                    "go_ontology_sha256": sha256_file(section["go_ontology_file"])
                    if isinstance(section.get("go_ontology_file"), str)
                    and Path(section["go_ontology_file"]).is_file()
                    else None,
                },
            )
            go_subgraph_path = _dump(
                work_dir / "go-compartment-subgraph.json",
                {
                    "compartment_go_terms": registry_payload.get(
                        "compartment_go_terms", {}
                    ),
                    "graph": registry_payload.get("go_graph", {}),
                },
            )
            gene_location_path = work_dir / "gene-location-evidence.jsonl"
            gene_location_path.write_text(
                "".join(
                    json.dumps(
                        {"record_type": "location", "gene_id": gene, **record},
                        sort_keys=True,
                    )
                    + "\n"
                    for gene, record in sorted(
                        location_payload.get("gene_locations", {}).items()
                    )
                ),
                encoding="utf-8",
            )
            reaction_identity_path = work_dir / "reaction-identity-evidence.jsonl"
            reaction_identity_path.write_text(
                "".join(
                    json.dumps(
                        {"record_type": "reaction-identity", **record}, sort_keys=True
                    )
                    + "\n"
                    for record in _jsonl(work_dir / "gpr-evidence.jsonl")
                    if record.get("rhea_id") or record.get("reactome_id")
                ),
                encoding="utf-8",
            )
            reconciliation_path = work_dir / "location-reconciliation.jsonl"
            reconciliation_path.write_text(
                "".join(
                    json.dumps(
                        {"record_type": "location-reconciliation", **record},
                        sort_keys=True,
                    )
                    + "\n"
                    for record in resolution_payload.get("evidence", [])
                ),
                encoding="utf-8",
            )
            for record in resolution_payload.get("evidence", []):
                snapshot_records.append(
                    {"record_type": "compartment-resolution", **record}
                )
            snapshot_records.append(
                {
                    "record_type": "metadata",
                    "schema_version": 1,
                    "ontology_version": resolution_payload.get(
                        "ontology_version",
                        section.get(
                            "compartment_ontology_version", "beta2-compartments-1"
                        ),
                    ),
                    "cco_graph": section.get("cco_graph", {}),
                    "go_graph": registry_payload.get("go_graph", {}),
                    "compartment_go_terms": registry_payload.get(
                        "compartment_go_terms", {}
                    ),
                    "source_releases": source_releases,
                }
            )
            snapshot_path.write_text(
                "".join(
                    json.dumps(item, sort_keys=True) + "\n" for item in snapshot_records
                ),
                encoding="utf-8",
            )
            from thg_protocol.analysis.model_signature import (
                diff_model_signatures,
                model_signature,
            )

            before = model_signature(_model(context, "load-beta1"))
            diff_path = _dump(
                work_dir / "beta1-to-beta2-diff.json",
                diff_model_signatures(before, model_signature(model)),
            )
            unresolved = json.loads(
                _dependency_path(
                    context, "infer-complex-and-isoenzyme-locations", "locations"
                ).read_text(encoding="utf-8")
            ).get("unresolved", [])
            unresolved.extend(resolution_payload.get("unresolved", []))
            unresolved_path = work_dir / "beta2-unresolved.tsv"
            unresolved_path.write_text(
                "object\n"
                + "\n".join(str(item) for item in unresolved)
                + ("\n" if unresolved else ""),
                encoding="utf-8",
            )
            validation_payload = json.loads(
                (work_dir / "beta2-validation.json").read_text(encoding="utf-8")
            )
            feasibility = validation_payload.get("feasibility", {})
            blocked = validation_payload.get("blocked_reactions", {})
            cycle_risk = validation_payload.get("cycle_risk", {})
            added_reactions = len(validation_payload.get("added_reactions", []))
            beta1_status = feasibility.get("beta1", {}).get("status", "not-recorded")
            beta2_status = feasibility.get("beta2", {}).get("status", "not-recorded")
            blocked_status = blocked.get("status", "not-recorded")
            cycle_status = cycle_risk.get("status", "not-recorded")
            summary = work_dir / "beta2-summary.md"
            summary.write_text(
                "# THGβ2 candidate\n\n"
                "This is a release candidate artifact; the THGβ2 label "
                "remains gated.\n\n" + f"- Reactions: {len(model.reactions)}\n"
                f"- Metabolites: {len(model.metabolites)}\n"
                f"- Unresolved location references: {len(unresolved)}\n"
                f"- Added reactions: {added_reactions}\n"
                f"- β1 feasibility: {beta1_status}\n"
                f"- β2 feasibility: {beta2_status}\n"
                f"- Blocked-reaction analysis: {blocked_status}\n"
                f"- Cycle-risk analysis: {cycle_status}\n",
                encoding="utf-8",
            )
            decision_path = section.get("decisions_file")
            provenance = _dump(
                work_dir / "beta2-provenance.json",
                {
                    "schema_version": 1,
                    "workflow": "beta2",
                    "input_sha256": sha256_file(
                        _dependency_path(context, "load-beta1", "model")
                    ),
                    "upstream": section.get("upstream")
                    or _reference_beta1_upstream(context),
                    "external_beta1_equivalent": bool(
                        section.get("external_beta1_equivalent", False)
                    ),
                    "configuration": dict(section),
                    "decision_file_sha256": sha256_file(str(decision_path))
                    if isinstance(decision_path, str)
                    and Path(str(decision_path)).is_file()
                    else None,
                    "ontology_version": json.loads(
                        _dependency_path(
                            context, "normalize-compartments", "registry"
                        ).read_text(encoding="utf-8")
                    ).get("ontology_version"),
                    "source_releases": source_releases,
                    "software": {
                        "python": platform.python_version(),
                        "cobra": __import__("cobra").__version__,
                    },
                    "stage_fingerprints": {
                        str(key): value.get("fingerprint")
                        for key, value in context.manifest.get("steps", {}).items()
                        if isinstance(value, Mapping)
                    },
                },
            )
            return StageResult(
                (
                    ("model", json_path),
                    ("sbml", xml_path),
                    ("validation", work_dir / "beta2-validation.json"),
                    ("plan", work_dir / "beta2-expansion-plan.jsonl"),
                    ("proposals", work_dir / "beta2-proposals.jsonl"),
                    ("id-registry", work_dir / "beta2-id-registry.json"),
                    ("ledger", work_dir / "beta2-change-ledger.jsonl"),
                    ("location-evidence", work_dir / "beta2-location-evidence.jsonl"),
                    ("gene-location-evidence", gene_location_path),
                    ("gpr-evidence", work_dir / "gpr-evidence.jsonl"),
                    ("reaction-identity-evidence", reaction_identity_path),
                    (
                        "reaction-location-evidence",
                        work_dir / "reaction-location-evidence.jsonl",
                    ),
                    (
                        "compartment-resolution-evidence",
                        work_dir / "compartment-resolution-evidence.json",
                    ),
                    ("location-reconciliation", reconciliation_path),
                    ("go-release", go_release_path),
                    ("go-compartment-subgraph", go_subgraph_path),
                    ("evidence-snapshot", snapshot_path),
                    ("diff", diff_path),
                    ("unresolved", unresolved_path),
                    ("summary", summary),
                    ("provenance", provenance),
                ),
                {"release_candidate": False},
            )
        raise ValueError(f"unknown β2 stage: {self.id}")

    def validate(self, result: StageResult) -> None:
        if not result.outputs or any(not path.is_file() for _, path in result.outputs):
            raise ValueError(f"stage '{self.id}' did not produce complete artifacts")


def detailed_beta2_stages() -> tuple[DetailedBeta2Stage, ...]:
    dependencies = {
        "load-beta1": (),
        "collect-catalysis-evidence": ("load-beta1",),
        "collect-gpr-evidence": ("collect-catalysis-evidence",),
        "resolve-gprs": ("collect-catalysis-evidence", "collect-gpr-evidence"),
        "normalize-compartments": ("resolve-gprs",),
        "collect-location-evidence": ("normalize-compartments",),
        "collect-reaction-location-evidence": ("collect-location-evidence",),
        "resolve-compartment-evidence": (
            "normalize-compartments",
            "collect-location-evidence",
            "collect-reaction-location-evidence",
        ),
        "infer-complex-and-isoenzyme-locations": (
            "resolve-compartment-evidence",
            "resolve-gprs",
        ),
        "generate-expansion-plan": ("infer-complex-and-isoenzyme-locations",),
        "apply-expansion-decisions": ("generate-expansion-plan",),
        "apply-expansion": ("apply-expansion-decisions",),
        "consolidate-expanded-model": ("apply-expansion",),
        "validate-beta2": ("consolidate-expanded-model",),
        "export-beta2": ("validate-beta2",),
    }
    return tuple(
        DetailedBeta2Stage(stage, dependencies[stage])
        for stage in DETAILED_BETA2_STAGE_IDS
    )
