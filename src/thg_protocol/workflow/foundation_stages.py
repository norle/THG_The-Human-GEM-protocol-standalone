"""Offline miniature stages used to exercise the Phase 0 foundations.

These stages are orchestration fixtures, not THG scientific curation.  They
make the registry, provenance, proposal, and restart contracts executable
before β1/β2 scientific mutation stages are introduced.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .artifacts import ArtifactReference, upstream_fingerprint
from .config import WorkflowConfig
from .hashing import sha256_json
from .stages import StageContext, StageResult


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
        return {
            "stage": self.id,
            "implementation_version": self.implementation_version,
            "workflow": context.config.workflow,
            "kind": self.kind,
            "configuration": section,
            "decision_files": decision_fingerprints,
            "dependencies": _dependency_hashes(context, self.dependencies),
        }

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


def _stages(prefix: str) -> tuple[FoundationStage, ...]:
    return (
        FoundationStage(f"{prefix}-input", output_role="input", kind="collection"),
        FoundationStage(
            f"{prefix}-evidence",
            (f"{prefix}-input",),
            output_role="evidence",
            kind="normalization",
        ),
        FoundationStage(
            f"{prefix}-proposals",
            (f"{prefix}-evidence",),
            output_role="proposals",
            kind="proposal",
        ),
        FoundationStage(
            f"{prefix}-apply",
            (f"{prefix}-proposals",),
            output_role="artifact",
            kind="mutation",
        ),
        FoundationStage(
            f"{prefix}-validate",
            (f"{prefix}-apply",),
            output_role="validation",
            kind="validation",
        ),
        FoundationStage(
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
            "beta1", _stages("beta1"), frozenset({"beta1"}), "THGβ1 foundation fixture"
        ),
        WorkflowDefinition(
            "beta2", _stages("beta2"), frozenset({"beta2"}), "THGβ2 foundation fixture"
        ),
        WorkflowDefinition(
            "validate",
            _stages("validate"),
            frozenset({"validation"}),
            "Validation foundation fixture",
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
