"""Small registered workflows for model-changing scientific helpers."""

from __future__ import annotations

import csv
import html
import json
import shutil
from collections import defaultdict
from collections.abc import Mapping
from pathlib import Path
from statistics import mean, median
from typing import Any

from .hashing import sha256_file
from .stages import StageContext, StageResult, _dependency_path, _load_cobra_model


def _dump(path: Path, value: object) -> Path:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, default=str) + "\n")
    return path


def _jsonl(path: Path, rows: list[Mapping[str, object]]) -> Path:
    path.write_text(
        "".join(json.dumps(dict(row), sort_keys=True) + "\n" for row in rows)
    )
    return path


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _software() -> str:
    try:
        from thg_protocol import __version__

        return str(__version__)
    except ImportError:
        return "unknown"


def _task_results(model: Any, section: Mapping[str, object]) -> dict[str, object]:
    task_suite = section.get("task_suite")
    if not isinstance(task_suite, str):
        return {"status": "not-requested", "passed": None, "tasks": []}
    from thg_protocol.tasks import load_task_suite, run_task_suite

    return run_task_suite(model, load_task_suite(task_suite))


def _model_metrics(model: Any, *, profile: str) -> dict[str, object]:
    from thg_protocol.analysis.consistency import dead_end_metabolites
    from thg_protocol.analysis.network import find_network_components
    from thg_protocol.validation import validate_model

    validation = validate_model(model, profile)
    components = find_network_components(model)
    try:
        from thg_protocol.analysis.consistency import blocked_reactions

        blocked = blocked_reactions(model)
    except Exception:
        blocked = []
    return {
        "counts": {
            "reactions": len(model.reactions),
            "metabolites": len(model.metabolites),
            "genes": len(model.genes),
        },
        "blocked_reactions": blocked,
        "dead_end_metabolites": dead_end_metabolites(model),
        "network_components": components["component_info"],
        "validation": validation,
    }


def _render_report(
    report: Mapping[str, object], json_path: Path, html_path: Path, md_path: Path
) -> None:
    body = json.dumps(report, indent=2, sort_keys=True, default=str)
    json_path.write_text(body + "\n")
    html_path.write_text(
        "<html><body><pre>" + html.escape(body) + "</pre></body></html>\n"
    )
    md_path.write_text(
        "# THG validation report\n\n"
        f"- status: `{report.get('status', 'unknown')}`\n"
        f"- source reactions: `{report.get('source_reaction_count', 0)}`\n"
        f"- retained reactions: `{report.get('retained_reaction_count', 0)}`\n"
    )


class CellSpecificStage:
    implementation_version = 1

    def __init__(self, stage_id: str, dependencies: tuple[str, ...] = ()) -> None:
        self.id, self.dependencies = stage_id, dependencies
        self.kind = (
            "mutation"
            if self.id in {"apply-reduction", "configure-context-exchanges"}
            else "analysis"
        )

    def enabled(self, config: Any) -> bool:
        del config
        return True

    def fingerprint_data(self, context: StageContext) -> Mapping[str, object]:
        section = context.config.sections.get("cell_specific", {})
        result: dict[str, object] = {
            "stage": self.id,
            "version": self.implementation_version,
            "configuration": dict(section) if isinstance(section, Mapping) else {},
            "dependencies": {
                dependency: [
                    item.get("sha256")
                    for item in context.manifest.get("steps", {})
                    .get(dependency, {})
                    .get("outputs", [])
                    if isinstance(item, Mapping)
                ]
                for dependency in self.dependencies
            },
        }
        if isinstance(section, Mapping):
            for key in ("input_model", "expression_file", "task_suite"):
                value = section.get(key)
                if isinstance(value, str) and Path(value).is_file():
                    result[f"{key}_sha256"] = sha256_file(value)
        return result

    def run(self, context: StageContext, work_dir: Path) -> StageResult:
        section = context.config.sections.get("cell_specific", {})
        if not isinstance(section, Mapping):
            raise ValueError("cell_specific section is required")
        if self.id == "load-source-model":
            source = Path(str(section["input_model"]))
            _load_cobra_model(source)
            destination = work_dir / f"source-model{source.suffix.lower()}"
            shutil.copy2(source, destination)
            provenance = _dump(
                work_dir / "source-provenance.json",
                {
                    "source_model": str(source),
                    "source_model_checksum": sha256_file(source),
                    "software": _software(),
                },
            )
            return StageResult((("model", destination), ("provenance", provenance)), {})

        if self.id == "collect-expression-evidence":
            source = Path(str(section["expression_file"]))
            rows: list[dict[str, object]] = []
            strategy = section.get(
                "reduction_strategy", section.get("activity_strategy", "gpr-threshold")
            )
            if strategy == "activity-matrix":
                raw = [
                    {
                        "gene_id": "__reaction_matrix__",
                        "value": 1.0,
                        "identifier_namespace": "reaction-order",
                        "units": "reaction-presence-matrix",
                    }
                ]
            elif source.suffix.lower() == ".csv":
                raw = list(csv.DictReader(source.open(newline="", encoding="utf-8")))
            elif source.suffix.lower() == ".jsonl":
                raw = [
                    json.loads(line)
                    for line in source.read_text(encoding="utf-8").splitlines()
                    if line.strip()
                ]
            else:
                payload = json.loads(source.read_text(encoding="utf-8"))
                raw = (
                    payload.get("records", [])
                    if isinstance(payload, Mapping)
                    else payload
                )
                if not isinstance(raw, list):
                    raise ValueError(
                        "expression data must be a list or an object with records"
                    )
            for item in raw:
                if not isinstance(item, Mapping):
                    raise ValueError("expression records must be objects")
                gene = item.get(
                    "gene_id", item.get("gene", item.get("gene_identifier"))
                )
                value = item.get("activity", item.get("expression", item.get("value")))
                if not isinstance(gene, str) or not gene.strip() or value is None:
                    raise ValueError("expression records require gene_id and value")
                sample_id = str(
                    item.get(
                        "sample_identifier",
                        item.get("sample_id", section.get("sample", "aggregate")),
                    )
                )
                if section.get("sample") is not None and sample_id != str(
                    section["sample"]
                ):
                    continue
                warnings = item.get("warnings", [])
                rows.append(
                    {
                        "gene_identifier": gene,
                        "identifier_namespace": str(
                            item.get(
                                "identifier_namespace",
                                section["gene_identifier_namespace"],
                            )
                        ),
                        "sample_identifier": sample_id,
                        "activity_value": float(value),
                        "units_or_transformation": str(
                            item.get(
                                "units_or_transformation",
                                item.get("units", "pre-normalized"),
                            )
                        ),
                        "source_file_checksum": sha256_file(source),
                        "mapping_status": "unmapped",
                        "warnings": (
                            list(warnings)
                            if isinstance(warnings, list)
                            else [str(warnings)]
                        ),
                    }
                )
            output = _jsonl(work_dir / "expression-evidence.jsonl", rows)
            return StageResult((("evidence", output),), {"records": len(rows)})

        if self.id == "normalize-gene-identifiers":
            mapping = section.get("gene_mapping", {})
            evidence = _read_jsonl(
                _dependency_path(context, "collect-expression-evidence", "evidence")
            )
            normalized: list[dict[str, object]] = []
            mapping_rows: list[dict[str, object]] = []
            for row in evidence:
                source_id = str(row["gene_identifier"])
                target = (
                    mapping.get(source_id) if isinstance(mapping, Mapping) else None
                )
                target_id = str(target or source_id)
                row = {
                    **row,
                    "gene_identifier": target_id,
                    "mapping_status": "mapped" if target else "identity",
                }
                normalized.append(row)
                mapping_rows.append(
                    {
                        "source_identifier": source_id,
                        "target_identifier": target_id,
                        "status": row["mapping_status"],
                    }
                )
            evidence_path = _jsonl(
                work_dir / "normalized-expression-evidence.jsonl", normalized
            )
            mapping_path = _jsonl(work_dir / "gene-mapping.jsonl", mapping_rows)
            return StageResult(
                (("evidence", evidence_path), ("mapping", mapping_path)),
                {"records": len(normalized)},
            )

        model = _load_cobra_model(
            _dependency_path(context, "load-source-model", "model")
        )
        if self.id == "map-expression-to-model":
            rows = _read_jsonl(
                _dependency_path(context, "normalize-gene-identifiers", "evidence")
            )
            values: defaultdict[str, list[float]] = defaultdict(list)
            for row in rows:
                values[str(row["gene_identifier"])].append(float(row["activity_value"]))
            aggregation = str(section.get("sample_aggregation", "mean"))
            activity: dict[str, float] = {}
            for gene in model.genes:
                data = values.get(gene.id, [])
                if data:
                    activity[gene.id] = {
                        "mean": mean,
                        "median": median,
                        "max": max,
                    }.get(aggregation, mean)(data)
            output = _dump(
                work_dir / "gene-activity.json",
                {"schema_version": 1, "activity": activity},
            )
            return StageResult((("activity", output),), {"mapped_genes": len(activity)})

        if self.id == "evaluate-gpr-activity":
            from thg_protocol.cell_specific import evaluate_gpr_activity

            if section.get(
                "reduction_strategy", section.get("activity_strategy")
            ) == "activity-matrix":
                import numpy as np

                source = Path(str(section["expression_file"]))
                if source.suffix.lower() == ".mat":
                    from scipy.io import loadmat

                    matrix = loadmat(source)[
                        str(section.get("matrix_key", "all_Solutions_matrix5"))
                    ]
                else:
                    matrix = np.loadtxt(source, delimiter=",", ndmin=2)
                if matrix.shape[0] != len(model.reactions):
                    raise ValueError("activity matrix rows must match model reactions")
                preserve = set(section.get("preserved_reactions", []))
                threshold = float(section.get("threshold", 0.0))
                rows = []
                for reaction, values in zip(model.reactions, matrix, strict=True):
                    presence = float(np.mean(values != 0))
                    retained = presence > threshold or reaction.id in preserve
                    rows.append(
                        {
                            "reaction_id": reaction.id,
                            "decision": "retain" if retained else "remove",
                            "evidence": {
                                "genes": [],
                                "activity": {"presence": presence},
                            },
                            "reason": (
                                "policy-preserved"
                                if reaction.id in preserve
                                else "evidence-supports-activity"
                                if retained
                                else "inactive-matrix"
                            ),
                            "uncertainty": [],
                        }
                    )
                output = _jsonl(work_dir / "reaction-activity.jsonl", rows)
                return StageResult(
                    (("activity", output),),
                    {"reactions": len(rows), "unknown_genes": []},
                )
            activity = json.loads(
                _dependency_path(
                    context, "map-expression-to-model", "activity"
                ).read_text()
            )["activity"]
            policy = str(section.get("unknown_gene_policy", "uncertain-retain"))
            rows = []
            for reaction in model.reactions:
                active, unknown = evaluate_gpr_activity(
                    str(reaction.gene_reaction_rule),
                    activity,
                    threshold=float(section.get("threshold", 0.0)),
                )
                if unknown and policy == "reject":
                    raise ValueError(
                        f"unknown genes in reaction {reaction.id}: {', '.join(unknown)}"
                    )
                retained = (
                    active
                    or bool(unknown and policy == "uncertain-retain")
                    or reaction.id in set(section.get("preserved_reactions", []))
                )
                rows.append(
                    {
                        "reaction_id": reaction.id,
                        "decision": "retain" if retained else "remove",
                        "evidence": {"genes": list(unknown), "activity": activity},
                        "reason": (
                            "policy-preserved"
                            if reaction.id
                            in set(section.get("preserved_reactions", []))
                            else (
                                "evidence-supports-activity"
                                if active
                                else "evidence-unknown" if unknown else "inactive-gpr"
                            )
                        ),
                        "uncertainty": list(unknown),
                    }
                )
            output = _jsonl(work_dir / "reaction-activity.jsonl", rows)
            return StageResult(
                (("activity", output),),
                {
                    "reactions": len(rows),
                    "unknown_genes": sorted(
                        {gene for row in rows for gene in row["uncertainty"]}
                    ),
                },
            )

        if self.id == "generate-reduction-plan":
            source = _dependency_path(context, "evaluate-gpr-activity", "activity")
            rows = _read_jsonl(source)
            output = _jsonl(work_dir / "reduction-plan.jsonl", rows)
            return StageResult((("plan", output),), {"proposals": len(rows)})

        if self.id == "apply-reduction-decisions":
            source = _dependency_path(context, "generate-reduction-plan", "plan")
            decisions = _read_jsonl(source)
            output = _jsonl(work_dir / "reduction-decisions.jsonl", decisions)
            return StageResult((("decisions", output),), {"decisions": len(decisions)})

        if self.id == "apply-reduction":
            from thg_protocol.analysis.model_signature import model_signature

            decisions = _read_jsonl(
                _dependency_path(context, "apply-reduction-decisions", "decisions")
            )
            remove = {
                str(row["reaction_id"])
                for row in decisions
                if row.get("decision") == "remove"
            }
            tailored = model.copy()
            tailored.remove_reactions(
                [reaction for reaction in tailored.reactions if reaction.id in remove]
            )
            orphan_metabolites = [
                item for item in tailored.metabolites if not item.reactions
            ]
            tailored.remove_metabolites(orphan_metabolites)
            orphan_genes = [item for item in tailored.genes if not item.reactions]
            for gene in orphan_genes:
                tailored.genes.remove(gene)
            from cobra.io import save_json_model

            model_path = work_dir / "reduced-model.json"
            save_json_model(tailored, str(model_path))
            ledger = _jsonl(
                work_dir / "change-ledger.jsonl",
                [
                    {
                        "reaction_id": row["reaction_id"],
                        "status": (
                            "removed" if row["reaction_id"] in remove else "retained"
                        ),
                        "reason": row["reason"],
                    }
                    for row in decisions
                ],
            )
            summary = _dump(
                work_dir / "reduction-summary.json",
                {
                    "source_reaction_count": len(model.reactions),
                    "retained_reaction_count": len(tailored.reactions),
                    "removed_reaction_count": len(remove),
                    "orphan_metabolites_removed": len(orphan_metabolites),
                    "orphan_genes_removed": len(orphan_genes),
                    "source_signature": model_signature(model),
                },
            )
            return StageResult(
                (("model", model_path), ("ledger", ledger), ("summary", summary)),
                {"removed": len(remove)},
            )

        if self.id == "configure-context-exchanges":
            configured = _load_cobra_model(
                _dependency_path(context, "apply-reduction", "model")
            )
            settings = section.get("exchange_settings", {})
            if isinstance(settings, Mapping):
                settings = [
                    {"reaction_id": key, "bounds": value}
                    for key, value in settings.items()
                ]
            if not isinstance(settings, list):
                raise ValueError("exchange_settings must be an object or list")
            applied = []
            for item in settings:
                if (
                    not isinstance(item, Mapping)
                    or not isinstance(item.get("bounds"), (list, tuple))
                    or len(item["bounds"]) != 2
                ):
                    raise ValueError(
                        "exchange settings require reaction_id and two bounds"
                    )
                reaction = configured.reactions.get_by_id(str(item["reaction_id"]))
                reaction.bounds = (float(item["bounds"][0]), float(item["bounds"][1]))
                applied.append(
                    {"reaction_id": reaction.id, "bounds": list(reaction.bounds)}
                )
            from cobra.io import save_json_model

            model_path = work_dir / "context-model.json"
            save_json_model(configured, str(model_path))
            settings_path = _dump(
                work_dir / "exchange-configuration.json", {"settings": applied}
            )
            return StageResult(
                (("model", model_path), ("exchanges", settings_path)),
                {"configured": len(applied)},
            )

        if self.id == "validate-cell-specific":
            before = _load_cobra_model(
                _dependency_path(context, "load-source-model", "model")
            )
            after = _load_cobra_model(
                _dependency_path(context, "configure-context-exchanges", "model")
            )
            profile = str(section.get("validation_profile", "structural-fast"))
            before_metrics = _model_metrics(before, profile=profile)
            after_metrics = _model_metrics(after, profile=profile)
            tasks = _task_results(after, section)
            report = {
                "schema_version": 1,
                "status": (
                    "passed" if after_metrics["validation"]["passed"] else "failed"
                ),
                "source_reaction_count": len(before.reactions),
                "retained_reaction_count": len(after.reactions),
                "removed_reaction_count": len(before.reactions) - len(after.reactions),
                "fraction_retained": (
                    len(after.reactions) / len(before.reactions)
                    if before.reactions
                    else 1.0
                ),
                "unknown_genes": self._unknown_genes(context),
                "uncertain_reactions": self._uncertain_reactions(context),
                "before": before_metrics,
                "after": after_metrics,
                "tasks": tasks,
                "exchange_configuration": section.get("exchange_settings", {}),
                "software": _software(),
            }
            output = _dump(work_dir / "validation-report.json", report)
            return StageResult((("validation", output),), report)

        if self.id == "export-cell-specific":
            model_path = _dependency_path(
                context, "configure-context-exchanges", "model"
            )
            model = _load_cobra_model(model_path)
            from cobra.io import save_json_model, write_sbml_model

            from thg_protocol.analysis.compare import compare_semantic_models

            json_model = work_dir / "cell-specific-model.json"
            xml_model = work_dir / "cell-specific-model.xml"
            save_json_model(model, str(json_model))
            write_sbml_model(model, str(xml_model))
            output_map = {"model": json_model, "sbml": xml_model}
            copies = {
                "expression-evidence": (
                    _dependency_path(context, "normalize-gene-identifiers", "evidence"),
                    "expression-evidence.jsonl",
                ),
                "gene-mapping": (
                    _dependency_path(context, "normalize-gene-identifiers", "mapping"),
                    "gene-mapping.jsonl",
                ),
                "reaction-activity": (
                    _dependency_path(context, "evaluate-gpr-activity", "activity"),
                    "reaction-activity.jsonl",
                ),
                "reduction-plan": (
                    _dependency_path(context, "generate-reduction-plan", "plan"),
                    "reduction-plan.jsonl",
                ),
                "reduction-decisions": (
                    _dependency_path(context, "apply-reduction-decisions", "decisions"),
                    "reduction-decisions.jsonl",
                ),
                "change-ledger": (
                    _dependency_path(context, "apply-reduction", "ledger"),
                    "change-ledger.jsonl",
                ),
                "validation": (
                    _dependency_path(context, "validate-cell-specific", "validation"),
                    "validation-report.json",
                ),
            }
            for role, (source, name) in copies.items():
                destination = work_dir / name
                shutil.copy2(source, destination)
                output_map[role] = destination
            validation = json.loads(output_map["validation"].read_text())
            diff = compare_semantic_models(
                _load_cobra_model(
                    _dependency_path(context, "load-source-model", "model")
                ),
                model,
            )
            output_map["model-diff"] = _dump(work_dir / "model-diff.json", diff)
            output_map["validation-html"] = work_dir / "validation-report.html"
            output_map["validation-html"].write_text(
                "<html><body><pre>"
                + html.escape(json.dumps(validation, indent=2, sort_keys=True))
                + "</pre></body></html>\n"
            )
            output_map["uncertainty"] = work_dir / "uncertainty.tsv"
            output_map["uncertainty"].write_text(
                "reaction_id\tuncertainty\n"
                + "\n".join(
                    f"{item}\tunknown-gene"
                    for item in validation["uncertain_reactions"]
                )
                + ("\n" if validation["uncertain_reactions"] else "")
            )
            source = Path(str(section["input_model"]))
            task_suite_version = None
            if isinstance(section.get("task_suite"), str):
                from thg_protocol.tasks import load_task_suite

                task_suite_version = load_task_suite(
                    str(section["task_suite"])
                ).version
            provenance = _dump(
                work_dir / "provenance.json",
                {
                    "source_model_checksum": sha256_file(source),
                    "expression_dataset_checksum": sha256_file(
                        str(section["expression_file"])
                    ),
                    "mapping_version": section.get("mapping_version", "1"),
                    "activity_strategy": section.get(
                        "activity_strategy", "gpr-threshold"
                    ),
                    "reduction_strategy": section.get(
                        "reduction_strategy",
                        section.get("activity_strategy", "gpr-threshold"),
                    ),
                    "threshold": section.get("threshold", 0.0),
                    "preserved_reactions": section.get("preserved_reactions", []),
                    "exchange_settings": section.get("exchange_settings", {}),
                    "task_suite": section.get("task_suite"),
                    "task_suite_version": task_suite_version,
                    "software": _software(),
                },
            )
            output_map["provenance"] = provenance
            roles = tuple((role, path) for role, path in output_map.items())
            return StageResult(
                roles,
                {"status": validation["status"], "reactions": len(model.reactions)},
            )

        raise ValueError(f"unknown cell-specific stage: {self.id}")

    def _unknown_genes(self, context: StageContext) -> list[str]:
        entry = context.manifest["steps"]["evaluate-gpr-activity"]
        return sorted(
            {
                gene
                for item in entry.get("outputs", [])
                if item.get("role") == "activity"
                for row in _read_jsonl(context.run_dir / item["path"])
                for gene in row.get("uncertainty", [])
            }
        )

    def _uncertain_reactions(self, context: StageContext) -> list[str]:
        entry = context.manifest["steps"]["evaluate-gpr-activity"]
        return sorted(
            row["reaction_id"]
            for item in entry.get("outputs", [])
            if item.get("role") == "activity"
            for row in _read_jsonl(context.run_dir / item["path"])
            if row.get("uncertainty")
        )

    def validate(self, result: StageResult) -> None:
        if not result.outputs or any(not path.is_file() for _, path in result.outputs):
            raise ValueError(f"stage '{self.id}' produced incomplete artifacts")


def cell_specific_stages() -> tuple[CellSpecificStage, ...]:
    ids = (
        ("load-source-model", ()),
        ("collect-expression-evidence", ("load-source-model",)),
        ("normalize-gene-identifiers", ("collect-expression-evidence",)),
        (
            "map-expression-to-model",
            ("load-source-model", "normalize-gene-identifiers"),
        ),
        ("evaluate-gpr-activity", ("load-source-model", "map-expression-to-model")),
        ("generate-reduction-plan", ("evaluate-gpr-activity",)),
        ("apply-reduction-decisions", ("generate-reduction-plan",)),
        ("apply-reduction", ("load-source-model", "apply-reduction-decisions")),
        ("configure-context-exchanges", ("apply-reduction",)),
        (
            "validate-cell-specific",
            (
                "load-source-model",
                "configure-context-exchanges",
                "evaluate-gpr-activity",
            ),
        ),
        (
            "export-cell-specific",
            (
                "load-source-model",
                "normalize-gene-identifiers",
                "evaluate-gpr-activity",
                "generate-reduction-plan",
                "apply-reduction-decisions",
                "apply-reduction",
                "validate-cell-specific",
                "configure-context-exchanges",
            ),
        ),
    )
    return tuple(
        CellSpecificStage(stage_id, dependencies) for stage_id, dependencies in ids
    )


class PathwayStage:
    implementation_version = 1

    def __init__(self, stage_id: str, dependencies: tuple[str, ...] = ()) -> None:
        self.id, self.dependencies = stage_id, dependencies

    def enabled(self, config: Any) -> bool:
        del config
        return True

    def fingerprint_data(self, context: StageContext) -> Mapping[str, object]:
        section = context.config.sections.get("pathway", {})
        result: dict[str, object] = {
            "stage": self.id,
            "version": self.implementation_version,
            "configuration": dict(section),
            "dependencies": self.dependencies,
        }
        if isinstance(section, Mapping):
            for key in ("input_model", "pathway_definition", "id_database"):
                value = section.get(key)
                if isinstance(value, str) and Path(value).is_file():
                    result[f"{key}_sha256"] = sha256_file(value)
        return result

    def run(self, context: StageContext, work_dir: Path) -> StageResult:
        section = context.config.sections["pathway"]
        if self.id == "load-model":
            source = Path(str(section["input_model"]))
            _load_cobra_model(source)
            output = work_dir / f"input-model{source.suffix.lower()}"
            shutil.copy2(source, output)
            return StageResult(
                (("model", output),), {"source_model_checksum": sha256_file(source)}
            )
        if self.id == "load-pathway-definition":
            outputs = []
            for key, role in (
                ("pathway_definition", "pathway"),
                ("id_database", "id-database"),
            ):
                source = Path(str(section[key]))
                output = work_dir / source.name
                shutil.copy2(source, output)
                outputs.append((role, output))
            return StageResult(tuple(outputs), {})
        if self.id == "resolve-pathway-identifiers":
            definition = _dependency_path(context, "load-pathway-definition", "pathway")
            payload = json.loads(definition.read_text())
            return StageResult(
                (("definition", _dump(work_dir / "resolved-pathway.json", payload)),),
                {"resolved": True},
            )
        if self.id == "generate-pathway-plan":
            config = json.loads(
                _dependency_path(
                    context, "resolve-pathway-identifiers", "definition"
                ).read_text()
            )
            return StageResult(
                (
                    (
                        "plan",
                        _dump(
                            work_dir / "pathway-plan.json",
                            {"schema_version": 1, "configuration": config},
                        ),
                    ),
                ),
                {},
            )
        if self.id == "apply-pathway":
            from cobra.io import model_to_dict

            from thg_protocol.pathway.workflow import implement_pathway

            model = model_to_dict(
                _load_cobra_model(
                    _dependency_path(context, "load-model", "model")
                )
            )
            config = json.loads(
                _dependency_path(context, "generate-pathway-plan", "plan").read_text()
            )["configuration"]
            database = json.loads(
                _dependency_path(
                    context, "load-pathway-definition", "id-database"
                ).read_text()
            )
            result = implement_pathway(model, config, database)
            if result["status"] == "failed":
                raise ValueError(
                    "pathway implementation failed: " + "; ".join(result["errors"])
                )
            return StageResult(
                (
                    ("model", _dump(work_dir / "pathway-model.json", result["model"])),
                    ("report", _dump(work_dir / "pathway-application.json", result)),
                ),
                result,
            )
        if self.id == "validate-pathway-model":
            model = _load_cobra_model(
                _dependency_path(context, "apply-pathway", "model")
            )
            from thg_protocol.validation import validate_model

            report = validate_model(
                model, str(section.get("validation_profile", "structural-fast"))
            )
            return StageResult(
                (("validation", _dump(work_dir / "validation-report.json", report)),),
                report,
            )
        if self.id == "export-pathway":
            model = _load_cobra_model(
                _dependency_path(context, "apply-pathway", "model")
            )
            from cobra.io import save_json_model, write_sbml_model

            json_model, xml_model = (
                work_dir / "pathway-model.json",
                work_dir / "pathway-model.xml",
            )
            save_json_model(model, str(json_model))
            write_sbml_model(model, str(xml_model))
            validation = work_dir / "validation-report.json"
            shutil.copy2(
                _dependency_path(context, "validate-pathway-model", "validation"),
                validation,
            )
            provenance = _dump(
                work_dir / "provenance.json",
                {
                    "source_model_checksum": sha256_file(str(section["input_model"])),
                    "pathway_definition_checksum": sha256_file(
                        str(section["pathway_definition"])
                    ),
                    "id_database_checksum": sha256_file(str(section["id_database"])),
                    "software": _software(),
                },
            )
            return StageResult(
                (
                    ("model", json_model),
                    ("sbml", xml_model),
                    ("validation", validation),
                    ("provenance", provenance),
                ),
                {},
            )
        raise ValueError(f"unknown pathway stage: {self.id}")

    def validate(self, result: StageResult) -> None:
        if not result.outputs or any(not path.is_file() for _, path in result.outputs):
            raise ValueError(f"stage '{self.id}' produced incomplete artifacts")


def pathway_stages() -> tuple[PathwayStage, ...]:
    ids = (
        ("load-model", ()),
        ("load-pathway-definition", ()),
        ("resolve-pathway-identifiers", ("load-pathway-definition",)),
        ("generate-pathway-plan", ("resolve-pathway-identifiers",)),
        (
            "apply-pathway",
            ("load-model", "load-pathway-definition", "generate-pathway-plan"),
        ),
        ("validate-pathway-model", ("apply-pathway",)),
        ("export-pathway", ("apply-pathway", "validate-pathway-model")),
    )
    return tuple(PathwayStage(stage_id, dependencies) for stage_id, dependencies in ids)


class CompareStage:
    implementation_version = 1

    def __init__(self, stage_id: str, dependencies: tuple[str, ...] = ()) -> None:
        self.id, self.dependencies = stage_id, dependencies

    def enabled(self, config: Any) -> bool:
        del config
        return True

    def fingerprint_data(self, context: StageContext) -> Mapping[str, object]:
        section = context.config.sections.get("compare", {})
        result: dict[str, object] = {
            "stage": self.id,
            "version": self.implementation_version,
            "configuration": dict(section),
        }
        if isinstance(section, Mapping):
            for key in ("left", "right"):
                value = section.get(key)
                if isinstance(value, str) and Path(value).is_file():
                    result[f"{key}_sha256"] = sha256_file(value)
        return result

    def run(self, context: StageContext, work_dir: Path) -> StageResult:
        section = context.config.sections["compare"]
        if self.id == "load-compare-inputs":
            outputs = []
            for key in ("left", "right"):
                source = Path(str(section[key]))
                _load_cobra_model(source)
                outputs.append((key, _copy(source, work_dir / f"{key}{source.suffix}")))
            return StageResult(tuple(outputs), {})
        if self.id == "compare-models":
            from thg_protocol.analysis.compare import compare_semantic_models

            left = _load_cobra_model(
                _dependency_path(context, "load-compare-inputs", "left")
            )
            right = _load_cobra_model(
                _dependency_path(context, "load-compare-inputs", "right")
            )
            report = compare_semantic_models(left, right)
            return StageResult(
                (("comparison", _dump(work_dir / "comparison.json", report)),),
                report,
            )
        source = _dependency_path(context, "compare-models", "comparison")
        return StageResult(
            (("comparison", _copy(source, work_dir / "comparison.json")),),
            {},
        )

    def validate(self, result: StageResult) -> None:
        if not result.outputs or any(not path.is_file() for _, path in result.outputs):
            raise ValueError(f"stage '{self.id}' produced incomplete artifacts")


def _copy(source: Path, destination: Path) -> Path:
    shutil.copy2(source, destination)
    return destination


def compare_stages() -> tuple[CompareStage, ...]:
    return (
        CompareStage("load-compare-inputs"),
        CompareStage("compare-models", ("load-compare-inputs",)),
        CompareStage("export-comparison", ("compare-models",)),
    )


__all__ = [
    "CellSpecificStage",
    "CompareStage",
    "PathwayStage",
    "cell_specific_stages",
    "compare_stages",
    "pathway_stages",
]
