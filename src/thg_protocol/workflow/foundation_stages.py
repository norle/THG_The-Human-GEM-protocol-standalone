"""Offline miniature stages used to exercise the Phase 0 foundations.

These stages are orchestration fixtures, not THG scientific curation.  They
make the registry, provenance, proposal, and restart contracts executable
before β1/β2 scientific mutation stages are introduced.
"""

from __future__ import annotations

import json
import shutil
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .artifacts import ArtifactReference, upstream_fingerprint
from .config import WorkflowConfig
from .hashing import sha256_file, sha256_json
from .stages import StageContext, StageResult, _dependency_path


def _scientific_beta1_section(config: WorkflowConfig) -> Mapping[str, object] | None:
    section = config.sections.get("beta1")
    if not isinstance(section, Mapping) or "input_model" not in section:
        return None
    return section


class Beta1ScientificStage:
    """Offline β1 stage adapters used when a model input is configured.

    The six orchestration checkpoints remain stable for Phase 0 consumers;
    each checkpoint now performs the corresponding Phase 1 work and writes
    promoted artifacts under the resumable runner.
    """

    implementation_version = 2

    def __init__(
        self,
        stage_id: str,
        dependencies: tuple[str, ...] = (),
        *,
        output_role: str = "artifact",
        kind: str = "analysis",
    ) -> None:
        self.id = stage_id
        self.dependencies = dependencies
        self.output_role = output_role
        self.kind = kind

    def enabled(self, config: WorkflowConfig) -> bool:
        del config
        return True

    def _section(self, config: WorkflowConfig) -> Mapping[str, object]:
        section = _scientific_beta1_section(config)
        return section or {}

    def fingerprint_data(self, context: StageContext) -> Mapping[str, object]:
        if _scientific_beta1_section(context.config) is None:
            return FoundationStage(
                self.id, self.dependencies, output_role=self.output_role, kind=self.kind
            ).fingerprint_data(context)
        section = self._section(context.config)
        result: dict[str, object] = {
            "stage": self.id,
            "implementation_version": self.implementation_version,
            "configuration": dict(section),
            "dependencies": _dependency_hashes(context, self.dependencies),
        }
        source = section.get("input_model")
        if isinstance(source, str) and Path(source).is_file():
            from .hashing import sha256_file

            result["input_sha256"] = sha256_file(source)
        decision_file = section.get("decisions_file")
        if isinstance(decision_file, str):
            from .proposals import decisions_fingerprint

            result["decisions_sha256"] = decisions_fingerprint(decision_file)
        return result

    @staticmethod
    def _load(path: Path) -> Any:
        from .stages import _load_cobra_model

        return _load_cobra_model(path)

    @staticmethod
    def _save(model: Any, path: Path) -> None:
        from cobra.io import save_json_model, write_sbml_model

        if path.suffix.lower() == ".json":
            save_json_model(model, str(path))
        else:
            write_sbml_model(model, str(path))

    def run(self, context: StageContext, work_dir: Path) -> StageResult:
        if _scientific_beta1_section(context.config) is None:
            return FoundationStage(
                self.id, self.dependencies, output_role=self.output_role, kind=self.kind
            ).run(context, work_dir)
        from thg_protocol.curation.beta1 import (
            apply_model_proposals,
            audit_model,
            generate_balance_proposals,
            generate_curation_proposals,
            inventory_model,
        )

        from .proposals import read_decisions, read_proposals, write_proposals

        section = self._section(context.config)
        source = Path(str(section["input_model"]))
        if self.id.endswith("-input"):
            model = self._load(source)
            copied = work_dir / f"input-model{source.suffix.lower()}"
            shutil.copy2(source, copied)
            inventory = work_dir / "beta1-inventory.json"
            inventory.write_text(
                json.dumps(
                    inventory_model(model, input_path=source).to_dict(),
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
            return StageResult(
                (("model", copied), ("inventory", inventory)),
                {"scientific": True, "model_id": str(model.id)},
            )
        if self.id.endswith("-evidence"):
            model = self._load(_dependency_path(context, "beta1-input", "model"))
            payload = {
                "schema_version": 1,
                "source": str(source),
                "input_sha256": sha256_file(source),
                "inventory": inventory_model(model).to_dict(),
                "mode": "offline-normalized",
                "errors": [],
                "warnings": [],
            }
            output = work_dir / "beta1-evidence.json"
            output.write_text(
                json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
            return StageResult(
                (("evidence", output),),
                {"scientific": True, "objects": payload["inventory"]["counts"]},
            )
        if self.id.endswith("-proposals"):
            model = self._load(_dependency_path(context, "beta1-input", "model"))
            proposals = generate_curation_proposals(
                model,
                metabolite_identities=_resolution_mapping(
                    section.get("metabolite_identities")
                ),
                gene_mapping=_string_mapping(section.get("gene_mapping")) or {},
            )
            proposals += generate_balance_proposals(
                model,
                corrections=_mapping(section.get("corrections")),
                formula_corrections=_string_mapping(section.get("formula_corrections")),
                charge_corrections=_int_mapping(section.get("charge_corrections")),
                strategy=str(section.get("balance_strategy", "proton-water")),
            )
            output = work_dir / "beta1-proposals.jsonl"
            write_proposals(output, proposals)
            return StageResult(
                (("proposals", output),),
                {"scientific": True, "proposals": len(proposals)},
            )
        if self.id.endswith("-apply"):
            model = self._load(_dependency_path(context, "beta1-input", "model"))
            proposals = read_proposals(
                _dependency_path(context, "beta1-proposals", "proposals")
            )
            decisions_path = section.get("decisions_file")
            decisions = (
                read_decisions(str(decisions_path))
                if isinstance(decisions_path, str)
                else ()
            )
            curated, ledger = apply_model_proposals(
                model,
                proposals,
                mode=str(section.get("mode", "apply-all")),
                decisions=decisions,
            )
            output = work_dir / "beta1-applied.json"
            self._save(curated, output)
            ledger_path = work_dir / "beta1-change-ledger.jsonl"
            ledger_path.write_text(
                "\n".join(json.dumps(item, sort_keys=True) for item in ledger)
                + ("\n" if ledger else ""),
                encoding="utf-8",
            )
            return StageResult(
                (("model", output), ("ledger", ledger_path)),
                {
                    "scientific": True,
                    "applied": sum(item.get("status") == "applied" for item in ledger),
                },
            )
        if self.id.endswith("-validate"):
            model = self._load(_dependency_path(context, "beta1-apply", "model"))
            audits = audit_model(model)
            validation = {
                "schema_version": 1,
                "model_id": str(model.id),
                "unique_ids": len({item.id for item in model.metabolites})
                == len(model.metabolites)
                and len({item.id for item in model.reactions}) == len(model.reactions),
                "audits": [item.to_dict() for item in audits],
                "unresolved": [
                    item.to_dict()
                    for item in audits
                    if item.mass_status == "unbalanced"
                ],
            }
            output = work_dir / "beta1-validation.json"
            output.write_text(
                json.dumps(validation, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            return StageResult(
                (("validation", output),),
                {"scientific": True, "unresolved": len(validation["unresolved"])},
            )
        if self.id.endswith("-export"):
            model = self._load(_dependency_path(context, "beta1-apply", "model"))
            json_path = work_dir / "thg-beta1-candidate.json"
            xml_path = work_dir / "thg-beta1-candidate.xml"
            self._save(model, json_path)
            self._save(model, xml_path)
            from thg_protocol.analysis.model_signature import model_signature

            signature = work_dir / "beta1-signature.json"
            signature.write_text(
                json.dumps(model_signature(model), indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            validation = work_dir / "beta1-validation.json"
            shutil.copy2(
                _dependency_path(context, "beta1-validate", "validation"), validation
            )
            ledger = work_dir / "beta1-change-ledger.jsonl"
            shutil.copy2(_dependency_path(context, "beta1-apply", "ledger"), ledger)
            return StageResult(
                (
                    ("model", json_path),
                    ("sbml", xml_path),
                    ("signature", signature),
                    ("validation", validation),
                    ("ledger", ledger),
                ),
                {"scientific": True, "candidate": True},
            )
        raise ValueError(f"unknown β1 scientific stage: {self.id}")

    def validate(self, result: StageResult) -> None:
        if not result.outputs or any(not path.is_file() for _, path in result.outputs):
            raise ValueError(f"stage '{self.id}' did not produce complete artifacts")


def _mapping(value: object) -> Mapping[str, Mapping[str, float]] | None:
    if not isinstance(value, Mapping):
        return None
    return {
        str(key): {str(k): float(v) for k, v in item.items()}
        for key, item in value.items()
        if isinstance(item, Mapping)
    }


def _string_mapping(value: object) -> Mapping[str, str] | None:
    return (
        {str(key): str(item) for key, item in value.items()}
        if isinstance(value, Mapping)
        else None
    )


def _int_mapping(value: object) -> Mapping[str, int] | None:
    return (
        {str(key): int(item) for key, item in value.items()}
        if isinstance(value, Mapping)
        else None
    )


def _resolution_mapping(value: object) -> Mapping[str, Mapping[str, object]]:
    return (
        {
            str(key): dict(item)
            for key, item in value.items()
            if isinstance(item, Mapping)
        }
        if isinstance(value, Mapping)
        else {}
    )


def _dependency_hashes(
    context: StageContext, dependencies: tuple[str, ...]
) -> dict[str, object]:
    steps = context.manifest.get("steps")
    if not isinstance(steps, Mapping):
        return {}
    result: dict[str, object] = {}
    for stage_id in dependencies:
        entry = steps.get(stage_id)
        if isinstance(entry, Mapping):
            result[stage_id] = [
                item.get("sha256")
                for item in entry.get("outputs", [])
                if isinstance(item, Mapping)
            ]
    return result


class FoundationStage:
    """A deterministic, no-network stage with explicit artifact provenance."""

    implementation_version = 1

    def __init__(
        self,
        stage_id: str,
        dependencies: tuple[str, ...] = (),
        *,
        output_role: str = "artifact",
        kind: str = "analysis",
    ) -> None:
        self.id = stage_id
        self.dependencies = dependencies
        self.output_role = output_role
        self.kind = kind

    def enabled(self, config: WorkflowConfig) -> bool:
        del config
        return True

    def _section(self, config: WorkflowConfig) -> Mapping[str, object]:
        value = config.sections.get(config.workflow, {})
        return value if isinstance(value, Mapping) else {}

    def fingerprint_data(self, context: StageContext) -> Mapping[str, object]:
        section = self._section(context.config)
        decision_fingerprints = {}
        if self.kind in {"proposal", "mutation", "validation", "rendering"}:
            from .proposals import decisions_fingerprint

            for key, value in section.items():
                if key.endswith(("decision_file", "decisions_file")) and isinstance(
                    value, str
                ):
                    decision_fingerprints[key] = decisions_fingerprint(value)
        result: dict[str, object] = {
            "stage": self.id,
            "implementation_version": self.implementation_version,
            "workflow": context.config.workflow,
            "kind": self.kind,
            "configuration": {
                key: value for key, value in section.items() if key != "n_jobs"
            },
            "decision_files": decision_fingerprints,
            "dependencies": _dependency_hashes(context, self.dependencies),
        }
        references = section.get("upstream")
        if references is not None:
            try:
                if not isinstance(references, list) or not all(
                    isinstance(item, Mapping) for item in references
                ):
                    raise ValueError(
                        "workflow upstream must be a list of artifact references"
                    )
                result["upstream"] = upstream_fingerprint(
                    references,
                    base_dir=(
                        context.config.source_path.parent
                        if context.config.source_path is not None
                        else context.config.run.output_dir
                    ),
                )
            except Exception as error:
                # Let stage.run persist the actionable error instead of failing
                # before the runner can update the manifest.
                result["upstream_error"] = f"{type(error).__name__}: {error}"
        return result

    def run(self, context: StageContext, work_dir: Path) -> StageResult:
        section = self._section(context.config)
        provenance: dict[str, object] = {
            "workflow": context.config.workflow,
            "stage": self.id,
            "kind": self.kind,
            "configuration": section,
            "dependencies": _dependency_hashes(context, self.dependencies),
        }
        references = section.get("upstream")
        if references is not None:
            if not isinstance(references, list) or not all(
                isinstance(x, dict) for x in references
            ):
                raise ValueError(
                    "workflow upstream must be a list of artifact references"
                )
            resolved = upstream_fingerprint(
                [
                    ArtifactReference.from_mapping(
                        item,
                        base_dir=(
                            context.config.source_path.parent
                            if context.config.source_path is not None
                            else context.config.run.output_dir
                        ),
                    )
                    for item in references
                ]
            )
            provenance["upstream"] = resolved

        payload: dict[str, object] = {
            "schema_version": 1,
            "workflow": context.config.workflow,
            "stage": self.id,
            "kind": self.kind,
            "provenance": provenance,
            "content_fingerprint": sha256_json(provenance),
        }
        output = work_dir / f"{self.id}.json"
        output.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        return StageResult(((self.output_role, output),), {"kind": self.kind})

    def validate(self, result: StageResult) -> None:
        if len(result.outputs) != 1 or not result.outputs[0][1].is_file():
            raise ValueError(f"stage '{self.id}' did not produce one artifact")


class ValidationScientificStage:
    """Three checkpoint validation DAG with optional real MEMOTE execution."""

    implementation_version = 1

    def __init__(self, stage_id: str, dependencies: tuple[str, ...] = ()) -> None:
        self.id, self.dependencies = stage_id, dependencies
        self.output_role = "model" if stage_id == "validate-input" else "validation"
        self.kind = "collection" if stage_id == "validate-input" else "validation"

    def enabled(self, config: WorkflowConfig) -> bool:
        del config
        return True

    def fingerprint_data(self, context: StageContext) -> Mapping[str, object]:
        section = context.config.sections.get("validation", {})
        return {
            "stage": self.id,
            "version": self.implementation_version,
            "configuration": dict(section) if isinstance(section, Mapping) else {},
        }

    def run(self, context: StageContext, work_dir: Path) -> StageResult:
        from .stages import _load_cobra_model

        section = context.config.sections.get("validation", {})
        if not isinstance(section, Mapping):
            section = {}
        if self.id == "validate-input":
            source = Path(str(section["input_model"]))
            destination = work_dir / f"input-model{source.suffix.lower()}"
            shutil.copy2(source, destination)
            _load_cobra_model(destination)
            return StageResult(
                (("model", destination),), {"input_sha256": sha256_file(source)}
            )
        model = _load_cobra_model(_dependency_path(context, "validate-input", "model"))
        if self.id == "validate-checks":
            from thg_protocol.validation import validate_model

            report = validate_model(
                model,
                str(section.get("profile", "structural-fast")),
                run_solver=section.get("run_solver"),
            )
            output = work_dir / "validation.json"
            output.write_text(
                json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
            return StageResult((("validation", output),), report)
        from thg_protocol.memote import run_memote

        if bool(section.get("run_memote", False)):
            report = run_memote(
                _dependency_path(context, "validate-input", "model"),
                work_dir / "memote",
                command=tuple(section.get("memote_command", ["memote", "run"])),
                threshold=section.get("memote_threshold"),
            )
        else:
            report = {"status": "not-requested", "artifacts": {}}
        output = work_dir / "memote.json"
        output.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        return StageResult((("memote", output),), report)

    def validate(self, result: StageResult) -> None:
        if not result.outputs or any(not path.is_file() for _, path in result.outputs):
            raise ValueError(f"stage '{self.id}' did not produce complete artifacts")


def _stages(prefix: str) -> tuple[FoundationStage, ...]:
    if prefix == "beta1":
        stage_type = Beta1ScientificStage
    else:
        stage_type = FoundationStage
    return (
        stage_type(f"{prefix}-input", output_role="input", kind="collection"),
        stage_type(
            f"{prefix}-evidence",
            (f"{prefix}-input",),
            output_role="evidence",
            kind="normalization",
        ),
        stage_type(
            f"{prefix}-proposals",
            (f"{prefix}-evidence",),
            output_role="proposals",
            kind="proposal",
        ),
        stage_type(
            f"{prefix}-apply",
            (f"{prefix}-proposals",),
            output_role="artifact",
            kind="mutation",
        ),
        stage_type(
            f"{prefix}-validate",
            (f"{prefix}-apply",),
            output_role="validation",
            kind="validation",
        ),
        stage_type(
            f"{prefix}-export",
            (f"{prefix}-validate",),
            output_role="model",
            kind="rendering",
        ),
    )


def register_builtin_workflows(registry: Any) -> None:
    """Register the Phase 0 executable fixture DAGs exactly once."""
    from .registry import WorkflowDefinition, WorkflowRegistryError

    definitions = (
        WorkflowDefinition(
            "human-database",
            __import__(
                "thg_protocol.workflow.phase4_stages",
                fromlist=["human_database_stages"],
            ).human_database_stages(),
            frozenset({"human_database"}),
            "Offline-first Human Database reconstruction",
        ),
        WorkflowDefinition(
            "final-thg",
            __import__(
                "thg_protocol.workflow.phase4_stages", fromlist=["final_thg_stages"]
            ).final_thg_stages(),
            frozenset({"final_thg"}),
            "Semantic β2 and Human Database merge",
        ),
        WorkflowDefinition(
            "beta1",
            _stages("beta1"),
            frozenset({"beta1"}),
            "THGβ1 foundation fixture",
            scientific_stages=__import__(
                "thg_protocol.workflow.beta1_stages",
                fromlist=["detailed_beta1_stages"],
            ).detailed_beta1_stages(),
        ),
        WorkflowDefinition(
            "beta2",
            _stages("beta2"),
            frozenset({"beta2"}),
            "THGβ2 foundation fixture",
            scientific_stages=__import__(
                "thg_protocol.workflow.beta2_stages",
                fromlist=["detailed_beta2_stages"],
            ).detailed_beta2_stages(),
        ),
        WorkflowDefinition(
            "validate",
            _stages("validate"),
            frozenset({"validation"}),
            "Validation foundation fixture",
            scientific_stages=(
                ValidationScientificStage("validate-input"),
                ValidationScientificStage("validate-checks", ("validate-input",)),
                ValidationScientificStage("validate-memote", ("validate-checks",)),
            ),
        ),
        WorkflowDefinition(
            "compare",
            _stages("compare"),
            frozenset({"compare"}),
            "Comparison foundation fixture",
        ),
    )
    for definition in definitions:
        try:
            registry.register(definition)
        except WorkflowRegistryError as error:
            if "duplicate workflow ID" not in str(error):
                raise
